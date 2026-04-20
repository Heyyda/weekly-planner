"""
Unit-тесты NotificationManager (Plan 03-08). Covers NOTIF-01..04.

Требования:
  NOTIF-01: 3 режима — sound_pulse / pulse_only / silent
  NOTIF-02: winotify через daemon thread
  NOTIF-03: deadline detection в окне [-5min, 0]
  NOTIF-04: silent блокирует toast полностью

Fixtures:
  mock_winotify — из conftest.py (патчит winotify.Notification → FakeNotification)
"""
import inspect
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

from client.utils.notifications import (
    APPROACHING_WINDOW_MIN,
    VALID_MODES,
    NotificationManager,
)


# ---------- FakeTask (без зависимости от models.py) ----------


@dataclass
class FakeTask:
    id: str
    text: str
    time_deadline: Optional[str]
    done: bool = False
    deleted_at: Optional[str] = None


def _iso(dt: datetime) -> str:
    """datetime → ISO 8601 строка в UTC с 'Z' суффиксом."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------- Test 1: default mode ----------


def test_default_mode_sound_pulse():
    """NotificationManager создаётся с mode='sound_pulse' по умолчанию (NOTIF-01)."""
    n = NotificationManager()
    assert n.mode == "sound_pulse"


# ---------- Test 2: set_mode valid ----------


def test_set_mode_valid():
    """set_mode('silent') устанавливает режим (NOTIF-01)."""
    n = NotificationManager()
    n.set_mode("silent")
    assert n.mode == "silent"


def test_set_mode_all_valid():
    """Все 3 режима валидны."""
    n = NotificationManager()
    for m in ("sound_pulse", "pulse_only", "silent"):
        n.set_mode(m)
        assert n.mode == m


# ---------- Test 3: set_mode invalid ignored ----------


def test_set_mode_invalid_ignored():
    """Неизвестный режим игнорируется — mode не меняется (NOTIF-01)."""
    n = NotificationManager()
    n.set_mode("loud")
    assert n.mode == "sound_pulse"


def test_set_mode_invalid_after_valid():
    """Неизвестный режим не сбрасывает ранее установленный валидный."""
    n = NotificationManager()
    n.set_mode("pulse_only")
    n.set_mode("??")
    assert n.mode == "pulse_only"


# ---------- Test 4: send_toast silent blocks ----------


def test_send_toast_silent_blocks(mock_winotify):
    """Mode 'silent' → send_toast возвращает False, winotify НЕ вызывается (NOTIF-04)."""
    n = NotificationManager(mode="silent")
    result = n.send_toast("тест", "тело")
    assert result is False
    # Дождаться возможного daemon thread (не должен запуститься)
    time.sleep(0.1)
    assert len(mock_winotify) == 0, "toast не должен был вызваться в режиме silent"


# ---------- Test 5: send_toast pulse_only blocks ----------


def test_send_toast_pulse_only_blocks(mock_winotify):
    """Mode 'pulse_only' → send_toast возвращает False, winotify НЕ вызывается (NOTIF-01)."""
    n = NotificationManager(mode="pulse_only")
    result = n.send_toast("тест", "тело")
    assert result is False
    time.sleep(0.1)
    assert len(mock_winotify) == 0, "toast не должен был вызваться в режиме pulse_only"


# ---------- Test 6: send_toast sound_pulse fires ----------


def test_send_toast_sound_pulse_fires(mock_winotify):
    """Mode 'sound_pulse' → send_toast возвращает True, winotify.show вызван (NOTIF-02)."""
    n = NotificationManager(mode="sound_pulse")
    result = n.send_toast("привет", "тело уведомления")
    assert result is True
    # Ждём daemon thread
    for _ in range(30):
        if mock_winotify:
            break
        time.sleep(0.05)
    assert len(mock_winotify) == 1, "winotify.Notification.show() должен был вызваться"
    assert mock_winotify[0]["title"] == "привет"
    assert mock_winotify[0]["msg"] == "тело уведомления"


# ---------- Test 7: no icon_path — no crash ----------


def test_send_toast_without_icon_no_crash(mock_winotify):
    """Без icon_path toast работает корректно, icon=None в kwargs (NOTIF-02)."""
    n = NotificationManager(mode="sound_pulse")
    assert n._icon_path is None
    n.send_toast("t", "b")
    time.sleep(0.15)
    assert len(mock_winotify) == 1
    # icon должен быть None (не передавался в Notification)
    assert mock_winotify[0].get("icon") is None


# ---------- Test 8: set_icon absolute path (PITFALL 7) ----------


def test_set_icon_resolves_absolute(tmp_path):
    """set_icon() сохраняет АБСОЛЮТНЫЙ путь (PITFALL 7)."""
    icon_file = tmp_path / "icon.png"
    icon_file.write_bytes(b"fake-png-data")
    n = NotificationManager()
    n.set_icon(str(icon_file))
    assert n._icon_path is not None
    assert Path(n._icon_path).is_absolute(), "icon_path должен быть абсолютным"


def test_set_icon_nonexistent_becomes_none(tmp_path):
    """Несуществующий файл → icon_path = None (безопасно, без crash)."""
    n = NotificationManager()
    n.set_icon(str(tmp_path / "does-not-exist.ico"))
    assert n._icon_path is None


# ---------- Test 9: check_deadlines approaching ----------


def test_check_deadlines_approaching_detected():
    """Задача через 3 минуты → kind='approaching' (NOTIF-03)."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="Позвонить", time_deadline=_iso(now + timedelta(minutes=3)))
    n = NotificationManager()
    results = n.check_deadlines([task])
    assert len(results) == 1
    assert results[0]["kind"] == "approaching"
    assert results[0]["task_id"] == "t1"
    assert "Позвонить" in results[0]["body"]


def test_check_deadlines_approaching_boundary_5min():
    """Ровно 5 минут → detecting (граница включена)."""
    now = datetime.now(timezone.utc)
    task = FakeTask(
        id="t2", text="X",
        time_deadline=_iso(now + timedelta(minutes=APPROACHING_WINDOW_MIN))
    )
    n = NotificationManager()
    results = n.check_deadlines([task])
    assert len(results) == 1
    assert results[0]["kind"] == "approaching"


def test_check_deadlines_approaching_zero_delta():
    """deadline=now (delta=0) → approaching (граница включена)."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t3", text="X", time_deadline=_iso(now))
    n = NotificationManager()
    results = n.check_deadlines([task])
    assert len(results) == 1
    assert results[0]["kind"] == "approaching"


# ---------- Test 10: check_deadlines overdue ----------


def test_check_deadlines_overdue_detected():
    """Задача 30 секунд назад → kind='overdue' (NOTIF-03)."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="X", time_deadline=_iso(now - timedelta(seconds=30)))
    n = NotificationManager()
    results = n.check_deadlines([task])
    assert len(results) == 1
    assert results[0]["kind"] == "overdue"
    assert results[0]["task_id"] == "t1"


# ---------- Test 11: done task skipped ----------


def test_check_deadlines_done_task_skipped():
    """Выполненная задача (done=True) → пропускается (NOTIF-03)."""
    now = datetime.now(timezone.utc)
    task = FakeTask(
        id="t1", text="X",
        time_deadline=_iso(now + timedelta(minutes=2)),
        done=True,
    )
    n = NotificationManager()
    assert n.check_deadlines([task]) == []


# ---------- Test 12: no time_deadline skipped ----------


def test_check_deadlines_task_without_deadline_skipped():
    """Задача без time_deadline → пропускается."""
    task = FakeTask(id="t1", text="X", time_deadline=None)
    n = NotificationManager()
    assert n.check_deadlines([task]) == []


def test_check_deadlines_deleted_task_skipped():
    """Удалённая задача (deleted_at!=None) → пропускается."""
    now = datetime.now(timezone.utc)
    task = FakeTask(
        id="t1", text="X",
        time_deadline=_iso(now + timedelta(minutes=2)),
        deleted_at=_iso(now),
    )
    n = NotificationManager()
    assert n.check_deadlines([task]) == []


def test_check_deadlines_far_future_skipped():
    """Задача через 10 минут → вне окна → не детектируется."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="X", time_deadline=_iso(now + timedelta(minutes=10)))
    n = NotificationManager()
    assert n.check_deadlines([task]) == []


def test_check_deadlines_long_overdue_skipped():
    """Задача 10 минут назад → за пределами OVERDUE_WINDOW_MIN → не детектируется."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="X", time_deadline=_iso(now - timedelta(minutes=10)))
    n = NotificationManager()
    assert n.check_deadlines([task]) == []


# ---------- Test 13: fire_scheduled_toasts calls send_toast ----------


def test_fire_scheduled_toasts(mock_winotify):
    """fire_scheduled_toasts отправляет toast для найденных задач (NOTIF-03)."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="Позвонить Иванову", time_deadline=_iso(now + timedelta(minutes=2)))
    n = NotificationManager(mode="sound_pulse")
    n.fire_scheduled_toasts([task])
    # Daemon thread должен сработать
    for _ in range(30):
        if mock_winotify:
            break
        time.sleep(0.05)
    assert len(mock_winotify) == 1
    assert "Позвонить Иванову" in mock_winotify[0]["msg"]


def test_fire_scheduled_toasts_silent_mode_no_toast(mock_winotify):
    """fire_scheduled_toasts в silent mode → winotify НЕ вызывается (NOTIF-04)."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="X", time_deadline=_iso(now + timedelta(minutes=2)))
    n = NotificationManager(mode="silent")
    n.fire_scheduled_toasts([task])
    time.sleep(0.1)
    assert len(mock_winotify) == 0


# ---------- Test 14: dedup ----------


def test_check_deadlines_dedup_same_kind():
    """Повторный вызов check_deadlines с той же задачей не дублирует результат."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="X", time_deadline=_iso(now + timedelta(minutes=3)))
    n = NotificationManager()
    first = n.check_deadlines([task])
    second = n.check_deadlines([task])
    assert len(first) == 1, "первый вызов должен вернуть задачу"
    assert len(second) == 0, "повторный вызов должен быть dedup'нут"


def test_fire_scheduled_toasts_dedup(mock_winotify):
    """Два fire_scheduled_toasts подряд — toast отправляется только один раз."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="Y", time_deadline=_iso(now + timedelta(minutes=2)))
    n = NotificationManager(mode="sound_pulse")
    n.fire_scheduled_toasts([task])
    time.sleep(0.15)
    n.fire_scheduled_toasts([task])
    time.sleep(0.15)
    assert len(mock_winotify) == 1, "повторный toast не должен дублироваться"


# ---------- Test: reset_dedup ----------


def test_reset_dedup():
    """reset_dedup() очищает dedup — задача детектируется снова."""
    now = datetime.now(timezone.utc)
    task = FakeTask(id="t1", text="X", time_deadline=_iso(now + timedelta(minutes=3)))
    n = NotificationManager()
    n.check_deadlines([task])   # попадает в _sent
    n.reset_dedup()             # очищаем
    results = n.check_deadlines([task])
    assert len(results) == 1, "после reset_dedup задача должна детектироваться снова"


# ---------- Test 15: daemon=True (PITFALL 3) ----------


def test_daemon_thread_used_not_blocking_caller(mock_winotify):
    """PITFALL 3: send_toast не блокирует caller (возвращается немедленно)."""
    n = NotificationManager(mode="sound_pulse")
    start = time.monotonic()
    n.send_toast("x", "y")
    elapsed = time.monotonic() - start
    assert elapsed < 0.2, f"send_toast заблокировал caller на {elapsed:.3f}s — PITFALL 3!"
    time.sleep(0.1)  # дать daemon thread закончить


def test_source_uses_daemon_thread():
    """Структурный тест: исходный код содержит daemon=True (PITFALL 3 marker)."""
    import client.utils.notifications as module
    source = inspect.getsource(module)
    assert "daemon=True" in source, "PITFALL 3: daemon=True обязателен в threading.Thread"
    assert "threading.Thread" in source, "threading.Thread должен использоваться"


# ---------- Test 16: .resolve() absolute path (PITFALL 7) ----------


def test_source_resolves_path_absolute():
    """Структурный тест: исходный код использует Path().resolve() (PITFALL 7 marker)."""
    import client.utils.notifications as module
    source = inspect.getsource(module)
    assert ".resolve()" in source or "resolve()" in source, (
        "PITFALL 7: Path.resolve() обязателен для абсолютного icon path"
    )
