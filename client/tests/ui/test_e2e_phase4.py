"""
E2E integration тесты Phase 4.

Покрывает все 13 REQ-IDs через реальный MainWindow + Phase 4 компоненты + mock_storage.
"""
from datetime import date, timedelta

import pytest

from client.core.models import Task
from client.ui.main_window import MainWindow
from client.ui.settings import SettingsStore, UISettings


@pytest.fixture
def e2e_app(headless_tk, mock_theme_manager, mock_storage, tmp_appdata):
    settings = UISettings()
    settings_store = SettingsStore(mock_storage)
    mw = MainWindow(
        headless_tk, settings_store, settings, mock_theme_manager,
        storage=mock_storage, user_id="e2e-user",
    )
    headless_tk.update_idletasks()
    yield {
        "root": headless_tk,
        "mw": mw,
        "storage": mock_storage,
        "theme": mock_theme_manager,
    }
    try:
        mw.destroy()
    except Exception:
        pass


# ---------- Add → Toggle → Edit → Delete → Undo ----------

def test_e2e_add_via_quick_capture_save(e2e_app):
    """WEEK-01, TASK-01: quick capture save → Task в нужной DaySection."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    # Выбираем день в текущей неделе (tomorrow может выпасть на след. неделю если сегодня воскресенье)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    target_day = monday + timedelta(days=(today.weekday() + 1) % 7 if today.weekday() < 6 else 0)
    target_iso = target_day.isoformat()
    mw.handle_quick_capture_save("встреча", target_iso, "14:00")

    tasks = storage.get_visible_tasks()
    assert len(tasks) == 1
    assert tasks[0].text == "встреча"
    assert tasks[0].day == target_iso
    assert tasks[0].time_deadline == "14:00"

    mw._refresh_tasks()
    ds = mw._day_sections.get(target_day)
    assert ds is not None
    assert len(ds._task_widgets) == 1


def test_e2e_toggle_done_updates_storage(e2e_app):
    """TASK-02: checkbox click → update_task(done=True)."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    today_iso = date.today().isoformat()
    mw.handle_quick_capture_save("task", today_iso, None)
    task_id = storage.get_visible_tasks()[0].id

    mw._on_task_toggle(task_id, True)

    assert storage.get_task(task_id).done is True


def test_e2e_edit_dialog_saves_changes(e2e_app):
    """TASK-03: _on_edit_save → update_task с новыми text/day/time."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    mw.handle_quick_capture_save("original", date.today().isoformat(), None)
    task_id = storage.get_visible_tasks()[0].id

    updated_task = storage.get_task(task_id)
    updated_task.text = "edited"
    updated_task.time_deadline = "10:30"
    mw._on_edit_save(updated_task)

    final = storage.get_task(task_id)
    assert final.text == "edited"
    assert final.time_deadline == "10:30"


def test_e2e_delete_shows_undo_toast(e2e_app):
    """TASK-04: _delete_task_with_undo → soft_delete + undo_toast."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    mw.handle_quick_capture_save("to delete", date.today().isoformat(), None)
    task_id = storage.get_visible_tasks()[0].id

    mw._delete_task_with_undo(task_id)

    assert len(storage.get_visible_tasks()) == 0
    assert len(mw._undo_toast._queue) == 1


def test_e2e_undo_restores_task(e2e_app):
    """TASK-04: click Отменить → deleted_at = None → task visible again."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    mw.handle_quick_capture_save("to restore", date.today().isoformat(), None)
    task_id = storage.get_visible_tasks()[0].id

    mw._delete_task_with_undo(task_id)
    assert len(storage.get_visible_tasks()) == 0

    mw._undo_toast._undo(task_id)

    assert len(storage.get_visible_tasks()) == 1


# ---------- Drag-and-Drop (TASK-05, TASK-06) ----------

def test_e2e_move_task_between_days(e2e_app):
    """TASK-05: _on_task_moved → storage.update_task(day=new_day)."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    today = date.today()
    tomorrow = today + timedelta(days=1)
    mw.handle_quick_capture_save("moving", today.isoformat(), None)
    task_id = storage.get_visible_tasks()[0].id

    mw._on_task_moved(task_id, tomorrow)

    assert storage.get_task(task_id).day == tomorrow.isoformat()


def test_e2e_move_to_next_week(e2e_app):
    """TASK-06: drop на next-week zone → task.day = next_week_monday."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    today = date.today()
    next_monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    mw.handle_quick_capture_save("next week task", today.isoformat(), None)
    task_id = storage.get_visible_tasks()[0].id

    mw._on_task_moved(task_id, next_monday)

    assert storage.get_task(task_id).day == next_monday.isoformat()


# ---------- Week navigation ----------

def test_e2e_navigate_prev_week(e2e_app):
    """WEEK-02: prev_week → _week_monday shifts -7; day_sections перестроены."""
    mw = e2e_app["mw"]
    initial_days = set(mw._day_sections.keys())
    mw._week_nav.prev_week()
    new_days = set(mw._day_sections.keys())
    assert initial_days != new_days


def test_e2e_today_button_returns(e2e_app):
    """WEEK-03: today() после prev возвращает к current week."""
    mw = e2e_app["mw"]
    from client.ui.week_navigation import get_current_week_monday
    mw._week_nav.prev_week()
    mw._week_nav.prev_week()
    mw._week_nav.today()
    assert mw._week_nav.get_week_monday() == get_current_week_monday()


def test_e2e_archive_mode_activates_on_past(e2e_app):
    """WEEK-06: prev_week → on_archive_changed(True) → DaySections.set_archive_mode."""
    mw = e2e_app["mw"]
    mw.handle_quick_capture_save("today task", date.today().isoformat(), None)
    mw._week_nav.prev_week()
    for ds in mw._day_sections.values():
        assert ds._is_archive is True


def test_e2e_archive_mode_deactivates_on_today(e2e_app):
    """WEEK-06: today() → on_archive_changed(False) → editing re-enabled."""
    mw = e2e_app["mw"]
    mw._week_nav.prev_week()
    mw._week_nav.today()
    for ds in mw._day_sections.values():
        assert ds._is_archive is False


# ---------- Position sorting (TASK-07) ----------

def test_e2e_position_sort_preserved(e2e_app):
    """TASK-07: tasks рендерятся в порядке position ASC."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    today_iso = date.today().isoformat()
    t1 = Task.new(user_id="u", text="second", day=today_iso, position=2)
    t2 = Task.new(user_id="u", text="first", day=today_iso, position=0)
    t3 = Task.new(user_id="u", text="middle", day=today_iso, position=1)
    storage.add_task(t1)
    storage.add_task(t2)
    storage.add_task(t3)

    mw._refresh_tasks()
    today = date.today()
    ds = mw._day_sections.get(today)
    positions = [t.position for t in ds._tasks]
    assert positions == [0, 1, 2]


# ---------- Multiple-days rendering (WEEK-01) ----------

def test_e2e_tasks_distributed_to_correct_days(e2e_app):
    """WEEK-01: задачи рендерятся в свои DaySections (по task.day)."""
    mw = e2e_app["mw"]

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    for i in range(3):
        d = monday + timedelta(days=i)
        mw.handle_quick_capture_save(f"task-{i}", d.isoformat(), None)
    mw._refresh_tasks()

    for i in range(3):
        d = monday + timedelta(days=i)
        ds = mw._day_sections.get(d)
        assert ds is not None
        assert len(ds._task_widgets) == 1


# ---------- Overdue detection (WEEK-04) ----------

def test_e2e_overdue_task_rendered(e2e_app, timestamped_task_factory):
    """WEEK-04: overdue task — is_overdue=True."""
    mw = e2e_app["mw"]
    storage = e2e_app["storage"]

    overdue_task = timestamped_task_factory(text="overdue", day_offset=-1)
    storage.add_task(overdue_task)
    mw._week_nav.prev_week()
    mw._refresh_tasks()

    assert overdue_task.is_overdue() is True


# ---------- Empty day → "+" (D-33) ----------

def test_e2e_empty_day_shows_plus(e2e_app):
    """D-33 (WEEK-01): day без задач → "+" placeholder visible."""
    mw = e2e_app["mw"]
    today = date.today()
    ds = mw._day_sections[today]
    assert ds._plus_label is not None
    e2e_app["root"].update_idletasks()


# ---------- Task style switch (WEEK-05) ----------

def test_e2e_task_style_switch_rebuilds(e2e_app):
    """WEEK-05: handle_task_style_changed → rebuild day_sections."""
    mw = e2e_app["mw"]
    mw.handle_quick_capture_save("task", date.today().isoformat(), None)
    mw._refresh_tasks()
    mw.handle_task_style_changed("line")
    assert mw._day_sections
    today = date.today()
    ds = mw._day_sections[today]
    assert len(ds._task_widgets) >= 1
