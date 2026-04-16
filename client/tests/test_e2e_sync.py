"""
End-to-end интеграционные тесты Phase 2.

Все компоненты реальные (AuthManager + LocalStorage + SyncApiClient + SyncManager).
Только сервер замокан через requests-mock — он эмулирует stateful behavior
(хранит tasks, возвращает delta, отдаёт server_timestamp).

Покрывает все Success Criteria из ROADMAP Phase 2:
  1. Offline → online: задача доходит до сервера
  2. 50 offline tasks: без потерь
  3. Tombstone: не воссоздаётся
  4. threading.Lock: race-free (повторяет stress test из test_storage)

Также покрывает SYNC-01..08:
  SYNC-01: init_creates_dirs → implicit через authed_setup
  SYNC-02: optimistic UI → add_task → sync → на сервере
  SYNC-03: force_sync в running thread < 3s
  SYNC-04: concurrent UI writes → все changes доходят
  SYNC-05: server wins на conflict
  SYNC-06: task_id стабилен (UUID клиент) → no duplicates
  SYNC-07: stale last_sync_at → full resync (since=None)
  SYNC-08: tombstone не воссоздаётся на другом устройстве
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from client.core import config
from client.core.api_client import SyncApiClient
from client.core.auth import AuthManager
from client.core.models import Task, utcnow_iso
from client.core.paths import AppPaths
from client.core.storage import LocalStorage
from client.core.sync import SyncManager


# ---------------------------------------------------------------------------
# Вспомогательный класс: stateful mock-сервер
# ---------------------------------------------------------------------------

class FakeServer:
    """
    Stateful mock сервера. Хранит tasks в памяти, отвечает на /api/sync.
    Эмулирует delta по since, поддерживает tombstone, server-wins.
    """

    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self.online: bool = True

    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def handle_sync(self, request, context):
        """
        Обработчик для requests-mock callback.
        При online=False возвращает 503 (имитация offline сервера).
        """
        if not self.online:
            context.status_code = 503
            return {"error": {"code": "OFFLINE", "message": "server down"}}

        body = request.json()
        since = body.get("since")
        changes = body.get("changes", []) or []

        # Применить changes клиента к "БД"
        for ch in changes:
            op = ch["op"]
            tid = ch["task_id"]
            if op in ("create", "update"):
                if tid not in self.tasks:
                    self.tasks[tid] = {
                        "task_id": tid,
                        "text": "",
                        "day": "",
                        "time_deadline": None,
                        "done": False,
                        "position": 0,
                        "created_at": self.now(),
                        "updated_at": self.now(),
                        "deleted_at": None,
                        "user_id": "",
                    }
                for k in ("text", "day", "time_deadline", "done", "position"):
                    if k in ch:
                        self.tasks[tid][k] = ch[k]
                self.tasks[tid]["updated_at"] = self.now()
            elif op == "delete":
                if tid in self.tasks:
                    self.tasks[tid]["deleted_at"] = self.now()
                    self.tasks[tid]["updated_at"] = self.now()

        # Delta: задачи с updated_at > since (если since задан)
        if since:
            returned = [t for t in self.tasks.values() if t["updated_at"] > since]
        else:
            returned = list(self.tasks.values())  # full resync

        return {
            "server_timestamp": self.now(),
            "changes": returned,
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_keyring(monkeypatch):
    """In-memory keyring — изолирует от реального Windows Credential Manager."""
    store: dict[tuple, str] = {}
    import keyring as kr
    monkeypatch.setattr(kr, "get_password", lambda s, n: store.get((s, n)))
    monkeypatch.setattr(kr, "set_password", lambda s, n, v: store.__setitem__((s, n), v))

    def delete(s, n):
        if (s, n) in store:
            del store[(s, n)]

    monkeypatch.setattr(kr, "delete_password", delete)
    return store


@pytest.fixture
def fake_server():
    """Свежий FakeServer для каждого теста."""
    return FakeServer()


@pytest.fixture
def authed_setup(tmp_appdata, fake_keyring, fake_server, mock_api, api_base):
    """
    Готовый setup: AuthManager logged-in, LocalStorage инициализирован,
    SyncApiClient и SyncManager созданы (но НЕ запущены — тесты управляют lifecycle).

    Fixture автоматически регистрирует mock-endpoints:
      POST /auth/request-code → {request_id, expires_in}
      POST /auth/verify       → {access_token, refresh_token, ...}
      POST /sync              → делегируется FakeServer.handle_sync
    """
    # Регистрируем auth endpoints
    mock_api.post(
        f"{api_base}/auth/request-code",
        json={"request_id": "rid-e2e-1", "expires_in": 300},
        status_code=200,
    )
    mock_api.post(
        f"{api_base}/auth/verify",
        json={
            "access_token": "e2e-access-token",
            "refresh_token": "e2e-refresh-token",
            "expires_in": 900,
            "user_id": "user-e2e-1",
            "token_type": "bearer",
        },
        status_code=200,
    )
    # Sync endpoint — делегируем stateful FakeServer
    mock_api.post(f"{api_base}/sync", json=fake_server.handle_sync)

    # Полный auth flow
    auth = AuthManager()
    rid = auth.request_code(username="nikita", hostname="WORK-PC")
    auth.verify_code(request_id=rid, code="123456", device_name="WORK-PC")

    assert auth.get_access_token() == "e2e-access-token"
    assert auth.user_id == "user-e2e-1"

    storage = LocalStorage()
    storage.init()
    api_client = SyncApiClient(auth)
    sync = SyncManager(storage, auth, api_client=api_client)

    return {
        "auth": auth,
        "storage": storage,
        "api_client": api_client,
        "sync": sync,
        "server": fake_server,
    }


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------

def test_full_happy_path(authed_setup):
    """
    SC-1 / SYNC-02: добавить задачу → sync → задача на сервере.

    Проверяет весь chain: LocalStorage.add_task (optimistic) →
    SyncManager._attempt_sync → POST /api/sync → FakeServer хранит задачу.
    """
    ctx = authed_setup
    storage, sync, server = ctx["storage"], ctx["sync"], ctx["server"]

    t = Task.new(user_id="user-e2e-1", text="купить молоко", day="2026-04-14")
    storage.add_task(t)

    # Прямой вызов _attempt_sync (без потока)
    result = sync._attempt_sync()

    assert result.ok is True
    # Задача появилась на сервере
    assert t.id in server.tasks
    assert server.tasks[t.id]["text"] == "купить молоко"
    # Pending очищен
    assert storage.pending_count() == 0


def test_offline_50_tasks_no_loss_after_reconnect(authed_setup):
    """
    SC-2 / SYNC-06: 50 offline tasks → reconnect → все 50 на сервере без потерь и дубликатов.

    Сервер "выключен" (503), создаём 50 задач, несколько неуспешных sync attempts,
    потом сервер "ожил" → один sync → все 50 task_id на сервере, никаких дубликатов.
    """
    ctx = authed_setup
    storage, sync, server, api_client = (
        ctx["storage"], ctx["sync"], ctx["server"], ctx["api_client"]
    )

    # Сервер "выключен"
    server.online = False
    task_ids = []
    for i in range(50):
        t = Task.new(user_id="user-e2e-1", text=f"offline task {i}", day="2026-04-14",
                     position=i)
        storage.add_task(t)
        task_ids.append(t.id)

    # Несколько неуспешных sync attempts (сервер 503)
    for _ in range(3):
        result = sync._attempt_sync()
        assert result.ok is False

    # Все 50 changes по-прежнему в очереди
    assert storage.pending_count() >= 50
    assert len(server.tasks) == 0

    # Сервер "ожил"
    server.online = True
    # Сбросить backoff чтобы _attempt_sync не игнорировал
    api_client.reset_backoff()

    # Один sync — все changes отправлены
    result = sync._attempt_sync()
    assert result.ok is True

    # Все 50 на сервере
    assert len(server.tasks) == 50
    # UUID стабильны — no duplicates (SYNC-06)
    assert set(server.tasks.keys()) == set(task_ids)


def test_tombstone_not_recreated_on_other_device(authed_setup):
    """
    SC-3 / SYNC-08: device A удалил задачу → синхронизация → device B (новый storage)
    видит deleted_at != None и НЕ воссоздаёт. get_visible_tasks() == [].
    """
    ctx = authed_setup
    storage_a, sync_a, server = ctx["storage"], ctx["sync"], ctx["server"]
    auth = ctx["auth"]

    # Device A: создать задачу и отправить на сервер
    t = Task.new(user_id="user-e2e-1", text="to delete", day="2026-04-14")
    storage_a.add_task(t)
    sync_a._attempt_sync()
    assert t.id in server.tasks
    assert server.tasks[t.id]["deleted_at"] is None

    # Device A: мягкое удаление + синхронизация → tombstone на сервере
    storage_a.soft_delete_task(t.id)
    sync_a._attempt_sync()
    assert server.tasks[t.id]["deleted_at"] is not None

    # Device B: чистый storage, тот же auth — эмулируем новым AppPaths
    device_b_root = storage_a.paths.base_dir.parent / "device_b"
    device_b_root.mkdir(exist_ok=True)
    original_appdata = os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(device_b_root)
    try:
        paths_b = AppPaths()
        storage_b = LocalStorage(paths=paths_b)
        storage_b.init()
        sync_b = SyncManager(storage_b, auth, api_client=ctx["api_client"])

        # Первый sync на device B — должен получить tombstone с сервера
        sync_b._attempt_sync()

        # Живых задач нет
        assert storage_b.get_visible_tasks() == []
        # Tombstone присутствует в get_all_tasks
        all_b = storage_b.get_all_tasks()
        assert any(task.id == t.id and task.deleted_at is not None for task in all_b), \
            "Tombstone должен присутствовать в storage_b"
    finally:
        if original_appdata is not None:
            os.environ["APPDATA"] = original_appdata
        else:
            os.environ.pop("APPDATA", None)


def test_server_wins_on_conflict(authed_setup):
    """
    SYNC-05: сервер прислал более свежий updated_at → перезаписал локальную копию (silent).

    Симулируем "другое устройство": после push обновляем server.tasks напрямую
    с новым updated_at. Следующий sync с since=None (stale) → full resync →
    client получает server-версию.
    """
    ctx = authed_setup
    storage, sync, server = ctx["storage"], ctx["sync"], ctx["server"]

    # Создать и отправить на сервер
    t = Task.new(user_id="user-e2e-1", text="local version", day="2026-04-14")
    storage.add_task(t)
    sync._attempt_sync()
    assert server.tasks[t.id]["text"] == "local version"

    # "Другое устройство" обновило задачу на сервере — мутируем server state напрямую
    time.sleep(0.01)  # гарантируем разницу в updated_at
    server.tasks[t.id]["text"] = "remote version (newer)"
    server.tasks[t.id]["updated_at"] = server.now()

    # Локальная копия ещё со старым текстом
    local = storage.get_task(t.id)
    assert local is not None
    assert local.text == "local version"

    # Чтобы _attempt_sync не пропустил (skip-условие: нет pending + не stale + last_sync_at есть),
    # устанавливаем last_sync_at > STALE_THRESHOLD_SECONDS назад → full resync (since=None)
    old_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=config.STALE_THRESHOLD_SECONDS + 60)
    ).isoformat().replace("+00:00", "Z")
    storage.set_meta("last_sync_at", old_ts)

    # Второй sync — full resync (since=None), server-wins (D-16)
    result = sync._attempt_sync()
    assert result.ok is True

    local = storage.get_task(t.id)
    assert local is not None
    assert local.text == "remote version (newer)"


def test_full_resync_after_long_offline(authed_setup):
    """
    SYNC-07: long offline (>5 мин → last_sync_at устаревший) → следующий sync
    отправляет since=None → full resync → получает все задачи с сервера.
    """
    ctx = authed_setup
    storage, sync, server = ctx["storage"], ctx["sync"], ctx["server"]

    # Установить last_sync_at "очень давно" (> STALE_THRESHOLD_SECONDS)
    old = (
        datetime.now(timezone.utc) - timedelta(seconds=config.STALE_THRESHOLD_SECONDS + 60)
    ).isoformat().replace("+00:00", "Z")
    storage.set_meta("last_sync_at", old)

    # На сервере уже есть задача (как будто другое устройство добавило)
    remote_tid = "t-remote-e2e-xyz"
    server.tasks[remote_tid] = {
        "task_id": remote_tid,
        "text": "from another device",
        "day": "2026-04-14",
        "time_deadline": None,
        "done": False,
        "position": 0,
        "created_at": server.now(),
        "updated_at": server.now(),
        "deleted_at": None,
        "user_id": "user-e2e-1",
    }

    # Sync — должен послать since=None (full resync) и получить t-remote
    result = sync._attempt_sync()
    assert result.ok is True

    visible = storage.get_visible_tasks()
    assert any(t.id == remote_tid for t in visible), \
        f"t-remote должен появиться после full resync. Visible: {[t.id for t in visible]}"


def test_force_sync_in_running_thread(authed_setup):
    """
    SYNC-03: SyncManager started → force_sync() → задача на сервере < 3 секунд.

    Проверяет что wake Event работает в реальном потоке (не только в unit-mock тестах).
    """
    ctx = authed_setup
    storage, sync, server = ctx["storage"], ctx["sync"], ctx["server"]

    # Установить recent last_sync_at чтобы первый автоцикл не сработал сразу
    storage.set_meta("last_sync_at", utcnow_iso())

    sync.start()
    try:
        time.sleep(0.2)  # дать потоку запуститься
        t = Task.new(user_id="user-e2e-1", text="urgent task", day="2026-04-14")
        storage.add_task(t)
        sync.force_sync()

        # Ждём не более 3 секунд
        t0 = time.time()
        while time.time() - t0 < 3.0:
            if t.id in server.tasks:
                break
            time.sleep(0.05)

        assert t.id in server.tasks, f"force_sync не сработал за 3 секунды"
    finally:
        sync.stop(timeout=3)


def test_concurrent_ui_writes_during_sync(authed_setup):
    """
    SYNC-04 в реальном flow: UI thread добавляет tasks пока SyncManager одновременно
    делает _attempt_sync. threading.Lock защищает pending_changes — потери недопустимы.
    """
    ctx = authed_setup
    storage, sync, server = ctx["storage"], ctx["sync"], ctx["server"]

    N_ADDS = 30
    added_ids: list[str] = []
    added_lock = threading.Lock()

    def ui_writer():
        """Симуляция UI thread: N добавлений с паузами."""
        for i in range(N_ADDS):
            t = Task.new(
                user_id="user-e2e-1",
                text=f"concurrent task {i}",
                day="2026-04-14",
            )
            storage.add_task(t)
            with added_lock:
                added_ids.append(t.id)
            time.sleep(0.005)  # имитация UI events

    sync.start()
    try:
        writer = threading.Thread(target=ui_writer, daemon=True)
        writer.start()
        writer.join(timeout=10)

        # Дать sync thread время обработать оставшееся
        time.sleep(1.0)
        sync.force_sync()
        time.sleep(2.0)

        # Все N добавленных задач должны быть на сервере
        missing = set(added_ids) - set(server.tasks.keys())
        assert not missing, f"Потеряны при concurrent write: {len(missing)} задач"
        assert len(server.tasks) == N_ADDS
    finally:
        sync.stop(timeout=3)
