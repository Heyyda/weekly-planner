"""Unit-тесты client/core/storage.py — atomic write, Lock, drain, merge, tombstones."""
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from client.core import config
from client.core.models import Task, TaskChange, utcnow_iso
from client.core.storage import LocalStorage


@pytest.fixture
def storage(tmp_appdata):
    s = LocalStorage()
    s.init()
    return s


# ---- lifecycle ----

def test_init_creates_dirs(tmp_appdata):
    s = LocalStorage()
    s.init()
    assert s.paths.base_dir.is_dir()
    assert s.paths.logs_dir.is_dir()


def test_init_no_cache_returns_empty(storage):
    assert storage.get_all_tasks() == []
    assert storage.pending_count() == 0
    assert storage.get_meta("last_sync_at") is None


def test_save_and_load_roundtrip(tmp_appdata):
    s1 = LocalStorage(); s1.init()
    t = Task.new(user_id="u-1", text="hello", day="2026-04-14")
    s1.add_task(t)
    # Создать новый storage — читаем тот же файл
    s2 = LocalStorage(); s2.init()
    tasks = s2.get_visible_tasks()
    assert len(tasks) == 1
    assert tasks[0].text == "hello"
    assert s2.pending_count() == 1


def test_corrupted_cache_recovery(tmp_appdata):
    s = LocalStorage()
    s.paths.ensure()
    s.paths.cache_file.write_text("{ это не JSON }}}", encoding="utf-8")
    s.init()  # не должен крашить
    assert s.get_all_tasks() == []


def test_atomic_write_creates_tmp_then_replaces(storage, monkeypatch):
    """_save_locked использует .tmp + os.replace."""
    seen = []
    original_replace = os.replace

    def spy(src, dst):
        seen.append((str(src), str(dst)))
        return original_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    # Хотя бы один os.replace c .tmp в src
    assert any(s.endswith(".tmp") for s, d in seen)
    assert any(d.endswith("cache.json") for s, d in seen)


# ---- task mutations ----

def test_add_task_is_optimistic_and_queues_change(storage):
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    # in-memory сразу видна
    visible = storage.get_visible_tasks()
    assert len(visible) == 1
    # pending очередь содержит CREATE
    assert storage.pending_count() == 1


def test_add_pending_change_persisted(storage):
    c = TaskChange(op="update", task_id="t-1", done=True)
    storage.add_pending_change(c)
    assert storage.pending_count() == 1
    # перезагрузка
    s2 = LocalStorage(); s2.init()
    assert s2.pending_count() == 1


def test_update_task_partial_fields(storage):
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    ok = storage.update_task(t.id, done=True)
    assert ok is True
    # 2 changes: CREATE + UPDATE
    drained = storage.drain_pending_changes()
    assert len(drained) == 2
    update_change = drained[1]
    wire = update_change.to_wire()
    assert wire["op"] == "update"
    assert wire["done"] is True
    # text НЕ должен присутствовать (partial)
    assert "text" not in wire


def test_update_task_unknown_field_raises(storage):
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    with pytest.raises(ValueError):
        storage.update_task(t.id, banana=42)


def test_update_task_missing_returns_false(storage):
    ok = storage.update_task("no-such-id", done=True)
    assert ok is False


def test_soft_delete_sets_tombstone(storage):
    """SYNC-08: deleted_at установлен, задача НЕ удалена из tasks."""
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    storage.drain_pending_changes()  # очистить CREATE для чистоты
    ok = storage.soft_delete_task(t.id)
    assert ok is True
    # из get_all_tasks по-прежнему виден
    all_tasks = storage.get_all_tasks()
    assert len(all_tasks) == 1
    assert all_tasks[0].deleted_at is not None
    # из visible — нет
    assert storage.get_visible_tasks() == []
    # pending содержит DELETE
    drained = storage.drain_pending_changes()
    assert len(drained) == 1
    assert drained[0].op == "delete"
    assert drained[0].task_id == t.id


def test_soft_delete_already_deleted_returns_false(storage):
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    storage.soft_delete_task(t.id)
    assert storage.soft_delete_task(t.id) is False


# ---- drain / restore (SYNC-04) ----

def test_drain_returns_and_clears(storage):
    c1 = TaskChange(op="create", task_id="t-1", text="a", day="2026-04-14")
    c2 = TaskChange(op="update", task_id="t-1", done=True)
    storage.add_pending_change(c1)
    storage.add_pending_change(c2)
    drained = storage.drain_pending_changes()
    assert len(drained) == 2
    assert storage.pending_count() == 0


def test_restore_pending_returns_to_front(storage):
    c1 = TaskChange(op="create", task_id="t-1", text="a", day="2026-04-14")
    storage.add_pending_change(c1)
    drained = storage.drain_pending_changes()
    # после drain — пустая
    assert storage.pending_count() == 0
    # ставим новую
    c2 = TaskChange(op="update", task_id="t-2", done=True)
    storage.add_pending_change(c2)
    # restore drained — должен встать ПЕРЕД c2
    storage.restore_pending_changes(drained)
    all_drained = storage.drain_pending_changes()
    assert len(all_drained) == 2
    assert all_drained[0].task_id == "t-1"
    assert all_drained[1].task_id == "t-2"


def test_get_visible_filters_tombstones(storage):
    t1 = Task.new(user_id="u", text="alive", day="2026-04-14")
    t2 = Task.new(user_id="u", text="dead", day="2026-04-14")
    storage.add_task(t1)
    storage.add_task(t2)
    storage.soft_delete_task(t2.id)
    visible = storage.get_visible_tasks()
    assert len(visible) == 1
    assert visible[0].text == "alive"


# ---- merge_from_server (SYNC-05) ----

def test_merge_applies_new_task(storage):
    result = storage.merge_from_server(
        server_changes=[{
            "task_id": "t-server-1",
            "text": "from server",
            "day": "2026-04-15",
            "time_deadline": None,
            "done": False,
            "position": 0,
            "created_at": "2026-04-15T10:00:00Z",
            "updated_at": "2026-04-15T10:00:00Z",
            "deleted_at": None,
        }],
        server_timestamp="2026-04-15T10:00:01Z",
    )
    assert result["applied"] == 1
    assert storage.get_meta("last_sync_at") == "2026-04-15T10:00:01Z"
    visible = storage.get_visible_tasks()
    assert len(visible) == 1
    assert visible[0].id == "t-server-1"


def test_merge_server_wins_on_conflict(storage):
    """Server updated_at новее → перезаписывает локальную."""
    local = Task(
        id="t-1", user_id="u", text="local version", day="2026-04-14",
        done=False, position=0,
        created_at="2026-04-15T09:00:00Z",
        updated_at="2026-04-15T09:00:00Z",
    )
    storage.add_task(local)
    storage.drain_pending_changes()
    # Сервер прислал более свежую версию
    storage.merge_from_server(
        server_changes=[{
            "task_id": "t-1",
            "text": "server wins",
            "day": "2026-04-14",
            "time_deadline": None,
            "done": True,
            "position": 0,
            "created_at": "2026-04-15T09:00:00Z",
            "updated_at": "2026-04-15T10:00:00Z",  # позже local 09:00
            "deleted_at": None,
        }],
        server_timestamp="2026-04-15T10:00:01Z",
    )
    result = storage.get_visible_tasks()
    assert result[0].text == "server wins"
    assert result[0].done is True


def test_merge_logs_conflict_with_pending(storage, caplog):
    """RESEARCH Pitfall 5: если task в pending — log warning при перезаписи."""
    local = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(local)  # CREATE в pending
    with caplog.at_level("WARNING", logger="client.core.storage"):
        storage.merge_from_server(
            server_changes=[{
                "task_id": local.id,
                "text": "server",
                "day": "2026-04-14",
                "time_deadline": None,
                "done": False,
                "position": 0,
                "created_at": "2026-04-15T10:00:00Z",
                "updated_at": "2026-04-15T10:00:00Z",
                "deleted_at": None,
            }],
            server_timestamp="2026-04-15T10:00:01Z",
        )
    assert any("Конфликт" in rec.message for rec in caplog.records)


def test_server_tombstone_not_recreated(storage):
    """SYNC-08: tombstone от сервера → задача помечена deleted_at, не 'воссоздаётся'."""
    # Локально задачи нет; сервер прислал tombstone
    storage.merge_from_server(
        server_changes=[{
            "task_id": "t-deleted",
            "text": "deleted on other device",
            "day": "2026-04-14",
            "time_deadline": None,
            "done": False,
            "position": 0,
            "created_at": "2026-04-15T09:00:00Z",
            "updated_at": "2026-04-15T10:00:00Z",
            "deleted_at": "2026-04-15T10:00:00Z",
        }],
        server_timestamp="2026-04-15T10:00:01Z",
    )
    # В visible — пусто
    assert storage.get_visible_tasks() == []
    # Но задача присутствует с tombstone — для idempotency
    all_tasks = storage.get_all_tasks()
    assert len(all_tasks) == 1
    assert all_tasks[0].deleted_at is not None


# ---- cleanup_tombstones (D-23, D-24) ----

def test_cleanup_skips_tombstones_with_pending(storage):
    """D-23: НЕ удаляем tombstone пока DELETE в pending (не подтверждён push)."""
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    storage.soft_delete_task(t.id)  # ставит pending DELETE
    # Сделаем deleted_at старым
    with storage._lock:
        storage._data["tasks"][0]["deleted_at"] = "2020-01-01T00:00:00Z"
    removed = storage.cleanup_tombstones(min_age_seconds=0)
    assert removed == 0  # pending DELETE есть → не трогаем


def test_cleanup_removes_old_tombstones_no_pending(storage):
    """D-23: удаляем tombstone если pending пустой и age > threshold."""
    t = Task.new(user_id="u", text="x", day="2026-04-14")
    storage.add_task(t)
    storage.soft_delete_task(t.id)
    storage.drain_pending_changes()  # подтвердили push (очередь пустая)
    # Делаем старым
    with storage._lock:
        storage._data["tasks"][0]["deleted_at"] = "2020-01-01T00:00:00Z"
        storage._save_locked()
    removed = storage.cleanup_tombstones(min_age_seconds=60)
    assert removed == 1
    assert storage.get_all_tasks() == []


# ---- meta + settings ----

def test_meta_get_set(storage):
    storage.set_meta("last_sync_at", "2026-04-15T10:00:00Z")
    assert storage.get_meta("last_sync_at") == "2026-04-15T10:00:00Z"


def test_settings_save_and_load(storage):
    storage.save_settings({"theme": "dark", "hotkey": "win+q"})
    loaded = storage.load_settings()
    assert loaded == {"theme": "dark", "hotkey": "win+q"}


# ---- D-12 race condition stress (SYNC-04) ----

def test_concurrent_add_and_drain_is_race_free(storage):
    """
    D-12 / SYNC-04: 50 потоков по 100 add_pending_change + 50 потоков по 100 drain.
    Сумма всех drained changes должна быть == 5000 (50 потоков × 100 add).
    Никаких потерь, никаких exceptions.
    """
    ADD_THREADS = 50
    ADDS_PER_THREAD = 100
    DRAIN_THREADS = 50

    all_drained: list = []
    all_drained_lock = threading.Lock()
    errors: list = []
    stop_event = threading.Event()

    def adder(tid: int):
        try:
            for i in range(ADDS_PER_THREAD):
                c = TaskChange(op="update", task_id=f"t-{tid}-{i}", done=True)
                storage.add_pending_change(c)
        except Exception as e:
            errors.append(e)

    def drainer():
        try:
            while not stop_event.is_set():
                drained = storage.drain_pending_changes()
                if drained:
                    with all_drained_lock:
                        all_drained.extend(drained)
                else:
                    time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    adders = [threading.Thread(target=adder, args=(tid,)) for tid in range(ADD_THREADS)]
    drainers = [threading.Thread(target=drainer) for _ in range(DRAIN_THREADS)]
    for t in adders + drainers:
        t.start()
    for t in adders:
        t.join(timeout=30)
    # Финальный drain — забрать остатки
    time.sleep(0.1)
    stop_event.set()
    for t in drainers:
        t.join(timeout=5)
    # Финальный синхронный drain — собрать что могло остаться
    final = storage.drain_pending_changes()
    all_drained.extend(final)

    assert errors == [], f"Concurrent errors: {errors}"
    total = ADD_THREADS * ADDS_PER_THREAD
    assert len(all_drained) == total, (
        f"Lost changes: ожидалось {total}, получено {len(all_drained)}"
    )
    # Проверяем уникальность task_id'шек
    unique_ids = {c.task_id for c in all_drained}
    assert len(unique_ids) == total, "Найдены дубликаты"
