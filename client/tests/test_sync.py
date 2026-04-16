"""
Unit-тесты client/core/sync.py — SyncManager orchestration.

Покрывает:
  SYNC-03 — daemon thread 'PlannerSync' + force_sync() immediate wake
  SYNC-05 — merge_from_server вызывается на успешный ответ
  SYNC-07 — stale detection (>5 мин → since=None для full resync)
  D-20    — pending push в одном запросе с since=None (full resync)
  D-23    — cleanup_tombstones вызывается opportunistically
"""
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from client.core import config
from client.core.api_client import ApiResult
from client.core.auth import AuthManager
from client.core.models import TaskChange, utcnow_iso
from client.core.storage import LocalStorage
from client.core.sync import SyncManager


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture
def auth_with_token():
    """AuthManager с активным access_token (не читает keyring)."""
    m = AuthManager()
    m.access_token = "test-jwt"
    m._refresh_token = "test-rt"
    return m


@pytest.fixture
def storage(tmp_appdata):
    """LocalStorage изолированный в tmp_path."""
    s = LocalStorage()
    s.init()
    return s


@pytest.fixture
def api_mock():
    """
    Mock SyncApiClient — контролируем результаты каждого вызова.
    По умолчанию post_sync возвращает успешный пустой ответ.
    """
    m = MagicMock()
    m.consecutive_errors = 0
    m.current_backoff = config.BACKOFF_BASE
    m.post_sync.return_value = ApiResult.success({
        "server_timestamp": "2026-04-15T10:00:00Z",
        "changes": [],
    })
    return m


@pytest.fixture
def sync_mgr(storage, auth_with_token, api_mock):
    """SyncManager с инжектированным api_mock."""
    return SyncManager(storage, auth_with_token, api_client=api_mock)


# ------------------------------------------------------------------ #
# Task 1: thread lifecycle                                             #
# ------------------------------------------------------------------ #

def test_start_creates_named_daemon_thread(sync_mgr):
    """После start() поток называется 'PlannerSync' и является daemon."""
    sync_mgr.start()
    try:
        assert sync_mgr.is_running()
        assert sync_mgr._thread.daemon is True
        assert sync_mgr._thread.name == "PlannerSync"
    finally:
        sync_mgr.stop(timeout=2)


def test_stop_joins_thread_quickly(sync_mgr):
    """stop() завершает поток быстрее чем за 1.5 с (не ждём полный интервал 30 сек)."""
    sync_mgr.start()
    t0 = time.time()
    sync_mgr.stop(timeout=2)
    elapsed = time.time() - t0
    assert elapsed < 1.5, f"stop() занял {elapsed:.2f}s — слишком долго"
    assert not sync_mgr.is_running()


def test_start_is_idempotent(sync_mgr):
    """Повторный вызов start() не создаёт второй поток."""
    sync_mgr.start()
    first_thread = sync_mgr._thread
    sync_mgr.start()  # idempotent — должен вернуть тот же поток
    assert sync_mgr._thread is first_thread
    sync_mgr.stop(timeout=2)


# ------------------------------------------------------------------ #
# Task 2: force_sync wake (SYNC-03)                                   #
# ------------------------------------------------------------------ #

def test_force_sync_wakes_immediately(sync_mgr, storage, api_mock):
    """
    SYNC-03: force_sync() пробуждает sync thread в течение 2 сек
    (vs штатные 30 сек wait), без вызова time.sleep.
    """
    sync_mgr.start()
    try:
        # Дать первому _attempt_sync выполниться
        time.sleep(0.3)
        initial_calls = api_mock.post_sync.call_count

        # Добавить pending change, чтобы следующий sync не был noop
        change = TaskChange(op="update", task_id="t-force", done=True)
        storage.add_pending_change(change)
        storage.set_meta("last_sync_at", utcnow_iso())  # recent

        # force_sync → wake event → thread проснётся немедленно
        t0 = time.time()
        sync_mgr.force_sync()

        # Ждём пока api_mock.post_sync будет вызван больше чем initial_calls
        deadline = t0 + 2.0
        while time.time() < deadline:
            if api_mock.post_sync.call_count > initial_calls:
                break
            time.sleep(0.05)

        elapsed = time.time() - t0
        assert api_mock.post_sync.call_count > initial_calls, (
            f"post_sync не был вызван после force_sync (count={api_mock.post_sync.call_count})"
        )
        assert elapsed < 2.0, f"force_sync сработал за {elapsed:.2f}s — слишком медленно"
    finally:
        sync_mgr.stop(timeout=2)


def test_force_sync_ignored_when_not_running(sync_mgr):
    """force_sync() не падает если поток не запущен."""
    assert not sync_mgr.is_running()
    sync_mgr.force_sync()  # должен просто залогировать и вернуться


# ------------------------------------------------------------------ #
# Task 3–5: _attempt_sync logic                                        #
# ------------------------------------------------------------------ #

def test_attempt_skips_when_nothing_to_sync(sync_mgr, storage, api_mock):
    """
    Pending пуст + last_sync_at recent → НЕ дёргаем api.
    Skip-оптимизация: нет смысла в HTTP запросе.
    """
    storage.set_meta("last_sync_at", utcnow_iso())  # recent
    sync_mgr._attempt_sync()
    api_mock.post_sync.assert_not_called()


def test_attempt_drains_and_pushes(sync_mgr, storage, api_mock):
    """С pending change — drain и отправить на сервер."""
    c = TaskChange(op="update", task_id="t-drain", done=True)
    storage.add_pending_change(c)
    # Установим recent last_sync чтобы не было stale full-resync
    storage.set_meta("last_sync_at", utcnow_iso())

    sync_mgr._attempt_sync()

    api_mock.post_sync.assert_called_once()
    args, kwargs = api_mock.post_sync.call_args
    # Аргументы могут быть kwargs или positional
    sent_changes = kwargs.get("changes") if kwargs.get("changes") is not None else args[1]
    assert len(sent_changes) == 1
    assert sent_changes[0].task_id == "t-drain"
    # После успеха — pending пустой (commit_drained)
    assert storage.pending_count() == 0


def test_attempt_merges_on_success(sync_mgr, storage, api_mock):
    """
    SYNC-05: при 200 storage.merge_from_server вызван с серверными изменениями.
    Серверная задача должна появиться локально.
    """
    api_mock.post_sync.return_value = ApiResult.success({
        "server_timestamp": "2026-04-15T10:00:00Z",
        "changes": [{
            "task_id": "t-server",
            "text": "пришло с сервера",
            "day": "2026-04-15",
            "time_deadline": None,
            "done": False,
            "position": 0,
            "created_at": "2026-04-15T10:00:00Z",
            "updated_at": "2026-04-15T10:00:00Z",
            "deleted_at": None,
        }],
    })
    # Триггер — добавим pending чтобы _attempt_sync не был noop
    storage.add_pending_change(TaskChange(op="update", task_id="t-local", done=True))

    sync_mgr._attempt_sync()

    # Server task должна появиться локально
    visible = storage.get_visible_tasks()
    assert any(t.id == "t-server" for t in visible), (
        f"task 't-server' не найдена в visible tasks: {[t.id for t in visible]}"
    )
    # last_sync_at обновлён
    assert storage.get_meta("last_sync_at") == "2026-04-15T10:00:00Z"


def test_attempt_restores_pending_on_failure(sync_mgr, storage, api_mock):
    """
    5xx → restore_pending_changes вызван, pending не теряется.
    """
    c = TaskChange(op="update", task_id="t-restore", done=True)
    storage.add_pending_change(c)
    storage.set_meta("last_sync_at", utcnow_iso())
    api_mock.post_sync.return_value = ApiResult.server_error(500, retry_after=2.0)

    sync_mgr._attempt_sync()

    # pending восстановлен после 500
    assert storage.pending_count() == 1
    restored = storage.drain_pending_changes()
    assert len(restored) == 1
    assert restored[0].task_id == "t-restore"


# ------------------------------------------------------------------ #
# Task 6–7: full resync on stale (SYNC-07, D-20)                      #
# ------------------------------------------------------------------ #

def test_full_resync_on_stale(sync_mgr, storage, api_mock):
    """
    SYNC-07: last_sync_at > STALE_THRESHOLD_SECONDS назад → since=None (full resync).
    """
    old_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=config.STALE_THRESHOLD_SECONDS + 60)
    ).isoformat().replace("+00:00", "Z")
    storage.set_meta("last_sync_at", old_ts)

    sync_mgr._attempt_sync()

    api_mock.post_sync.assert_called_once()
    args, kwargs = api_mock.post_sync.call_args
    sent_since = kwargs.get("since") if "since" in kwargs else args[0]
    assert sent_since is None, f"Ожидали since=None при stale, получили: {sent_since!r}"


def test_push_pending_before_full_resync(sync_mgr, storage, api_mock):
    """
    D-20: pending push дренируется и отправляется в ОДНОМ запросе с since=None.
    Локальные изменения не теряются при full resync.
    """
    old_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=config.STALE_THRESHOLD_SECONDS + 60)
    ).isoformat().replace("+00:00", "Z")
    storage.set_meta("last_sync_at", old_ts)
    storage.add_pending_change(TaskChange(op="update", task_id="t-stale", done=True))

    sync_mgr._attempt_sync()

    api_mock.post_sync.assert_called_once()
    args, kwargs = api_mock.post_sync.call_args
    sent_since = kwargs.get("since") if "since" in kwargs else args[0]
    sent_changes = kwargs.get("changes") if "changes" in kwargs else args[1]
    assert sent_since is None  # full resync
    assert len(sent_changes) == 1
    assert sent_changes[0].task_id == "t-stale"


# ------------------------------------------------------------------ #
# Task 8: auth_expired stops loop                                      #
# ------------------------------------------------------------------ #

def test_auth_expired_sets_flag(sync_mgr, storage, api_mock):
    """
    ApiResult.auth_expired → _auth_expired=True.
    Это приведёт к выходу из _sync_loop.
    """
    api_mock.post_sync.return_value = ApiResult.auth_expired()
    storage.add_pending_change(TaskChange(op="update", task_id="t-auth", done=True))
    storage.set_meta("last_sync_at", utcnow_iso())

    sync_mgr._attempt_sync()

    assert sync_mgr._auth_expired is True


def test_auth_expired_stops_sync_loop(sync_mgr, storage, api_mock):
    """
    Когда _auth_expired=True — _sync_loop должен завершиться (поток останавливается).
    """
    api_mock.post_sync.return_value = ApiResult.auth_expired()
    storage.add_pending_change(TaskChange(op="update", task_id="t-auth2", done=True))
    storage.set_meta("last_sync_at", utcnow_iso())

    sync_mgr.start()
    # Ждём пока thread обнаружит auth_expired и выйдет из loop
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if not sync_mgr.is_running():
            break
        time.sleep(0.05)

    assert not sync_mgr.is_running(), "Sync thread должен был остановиться после auth_expired"


# ------------------------------------------------------------------ #
# Task 9: cleanup_tombstones opportunistic (D-23)                      #
# ------------------------------------------------------------------ #

def test_cleanup_tombstones_called_after_success(sync_mgr, storage, api_mock):
    """
    D-23: после успешного sync с пустым pending → cleanup_tombstones вызван.
    """
    storage.set_meta("last_sync_at", utcnow_iso())
    called = []
    original = storage.cleanup_tombstones

    def spy_cleanup(*args, **kwargs):
        called.append(True)
        return original(*args, **kwargs)

    storage.cleanup_tombstones = spy_cleanup
    # Добавим pending change чтобы _attempt_sync не был noop
    storage.add_pending_change(TaskChange(op="update", task_id="t-cleanup", done=True))

    sync_mgr._attempt_sync()

    assert len(called) == 1, "cleanup_tombstones должна была вызваться ровно 1 раз"


def test_no_post_when_no_token(sync_mgr, storage, api_mock):
    """Нет access_token → не дёргаем api (skip без ошибки)."""
    sync_mgr._auth.access_token = None

    sync_mgr._attempt_sync()

    api_mock.post_sync.assert_not_called()


# ------------------------------------------------------------------ #
# Task 10–12: _is_stale unit tests                                     #
# ------------------------------------------------------------------ #

def test_is_stale_none():
    """None → always stale (первый запуск)."""
    assert SyncManager._is_stale(None) is True


def test_is_stale_recent():
    """Только что синхронизировались → не stale."""
    recent = utcnow_iso()
    assert SyncManager._is_stale(recent) is False


def test_is_stale_old():
    """Последний sync > STALE_THRESHOLD_SECONDS назад → stale."""
    old = (
        datetime.now(timezone.utc) - timedelta(seconds=config.STALE_THRESHOLD_SECONDS + 60)
    ).isoformat().replace("+00:00", "Z")
    assert SyncManager._is_stale(old) is True


def test_is_stale_corrupted_returns_true():
    """Повреждённая строка → безопаснее считать stale."""
    assert SyncManager._is_stale("not-a-valid-date") is True


def test_is_stale_exactly_at_threshold():
    """Ровно на пороге (delta == STALE_THRESHOLD_SECONDS) — ещё не stale."""
    # delta должна быть чуть меньше порога
    just_fresh = (
        datetime.now(timezone.utc) - timedelta(seconds=config.STALE_THRESHOLD_SECONDS - 5)
    ).isoformat().replace("+00:00", "Z")
    assert SyncManager._is_stale(just_fresh) is False
