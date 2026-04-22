"""
Маркер-тест: проверка что Wave 0 fixtures работают.
Эти тесты должны проходить ДО реализации LocalStorage/SyncManager/AuthManager.
"""
import os
import requests


def test_tmp_appdata_isolates_path(tmp_appdata):
    """tmp_appdata подменяет APPDATA на tmp_path (изоляция от реальной AppData)."""
    assert os.environ["APPDATA"] == str(tmp_appdata)
    assert "ЛичныйЕженедельник" not in os.environ["APPDATA"]  # ещё не создана subdir


def test_mock_api_intercepts_request(mock_api, api_base):
    """mock_api перехватывает реальный requests.get — никаких живых HTTP в тестах."""
    mock_api.get(f"{api_base}/health", json={"status": "ok"}, status_code=200)
    resp = requests.get(f"{api_base}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_base_constant(api_base):
    """api_base указывает на production-домен (совпадает с AuthManager/SyncManager константами)."""
    assert api_base == "https://planner.heyda.ru/api"


# ---------- Phase 4 fixtures verification ----------

def test_timestamped_task_factory_default(timestamped_task_factory):
    """Factory без аргументов → Task today, not done, no time."""
    from datetime import date
    task = timestamped_task_factory()
    assert task.text == "Test task"
    assert task.day == date.today().isoformat()
    assert task.time_deadline is None
    assert task.done is False
    assert task.id  # UUID валиден


def test_timestamped_task_factory_past_day(timestamped_task_factory):
    """day_offset=-1 → task на вчера, is_overdue=True."""
    from datetime import date, timedelta
    task = timestamped_task_factory(day_offset=-1)
    assert task.day == (date.today() - timedelta(days=1)).isoformat()
    assert task.is_overdue() is True


def test_timestamped_task_factory_future_with_time(timestamped_task_factory):
    """day_offset=2 + time='14:30' → task послезавтра с time_deadline."""
    task = timestamped_task_factory(day_offset=2, time="14:30")
    assert task.time_deadline == "14:30"
    assert task.is_overdue() is False


def test_timestamped_task_factory_done(timestamped_task_factory):
    """done=True → task.done = True."""
    task = timestamped_task_factory(done=True)
    assert task.done is True


def test_timestamped_task_factory_cyrillic(timestamped_task_factory):
    """Кириллический текст сохраняется без mangling."""
    task = timestamped_task_factory(text="позвонить Иванову")
    assert task.text == "позвонить Иванову"


def test_mock_storage_empty_initially(mock_storage):
    """Свежий mock_storage — get_visible_tasks() = []."""
    assert mock_storage.get_visible_tasks() == []


def test_mock_storage_accepts_tasks(mock_storage, timestamped_task_factory):
    """mock_storage работает с add_task."""
    task = timestamped_task_factory(text="sanity")
    mock_storage.add_task(task)
    visible = mock_storage.get_visible_tasks()
    assert len(visible) == 1
    assert visible[0].text == "sanity"


def test_mock_theme_manager_light(mock_theme_manager):
    """mock_theme_manager('light') → accent_brand из light палитры."""
    assert mock_theme_manager.current == "light"
    assert mock_theme_manager.get("accent_brand") == "#7A9B6B"
    assert mock_theme_manager.get("bg_primary") == "#F5EFE6"


def test_dnd_event_simulator_with_coords(dnd_event_simulator):
    """dnd_event_simulator задаёт x_root/y_root/x/y."""
    ev = dnd_event_simulator(x_root=100, y_root=200, x=5, y=6)
    assert ev.x_root == 100
    assert ev.y_root == 200
    assert ev.x == 5
    assert ev.y == 6


def test_dnd_event_simulator_defaults(dnd_event_simulator):
    """Без аргументов — координаты 0."""
    ev = dnd_event_simulator()
    assert ev.x_root == 0
    assert ev.y_root == 0
    assert ev.x == 0
    assert ev.y == 0
