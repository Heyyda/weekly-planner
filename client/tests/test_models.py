"""Unit-тесты client/core/models.py — UUID, wire-format, overdue logic."""
from datetime import date, timedelta
import uuid

from client.core.models import (
    AppState, DayPlan, Task, TaskChange, WeekPlan, utcnow_iso,
)


def test_task_id_is_uuid():
    """SYNC-06: Task.new генерирует UUID client-side (idempotent CREATE)."""
    t = Task.new(user_id="user-1", text="hello", day="2026-04-14")
    # uuid.UUID принимает только валидный UUID → raises иначе
    uuid.UUID(t.id)  # не упадёт = валидный UUID
    assert len(t.id) == 36  # стандартная длина UUID с дефисами
    assert t.user_id == "user-1"
    assert t.deleted_at is None
    assert t.done is False
    assert t.created_at.endswith("Z")
    assert t.updated_at == t.created_at  # при создании == created


def test_task_new_unique_ids():
    """Две подряд созданные задачи имеют разные UUID."""
    t1 = Task.new(user_id="u", text="a", day="2026-04-14")
    t2 = Task.new(user_id="u", text="b", day="2026-04-14")
    assert t1.id != t2.id


def test_task_is_alive_and_overdue():
    """is_alive учитывает deleted_at; is_overdue — done и дата."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    t = Task.new(user_id="u", text="x", day=yesterday)
    assert t.is_alive() is True
    assert t.is_overdue() is True
    # Tombstone → не overdue
    t.deleted_at = utcnow_iso()
    assert t.is_alive() is False
    assert t.is_overdue() is False


def test_utcnow_iso_format():
    """utcnow_iso заканчивается на Z (совместимо с server_timestamp)."""
    ts = utcnow_iso()
    assert ts.endswith("Z")
    assert "T" in ts
    assert "+00:00" not in ts


def test_task_change_to_wire_create():
    """CREATE включает все заполненные поля."""
    tc = TaskChange(op="create", task_id="uuid-1", text="купить молоко",
                    day="2026-04-14", done=False, position=0)
    wire = tc.to_wire()
    assert wire["op"] == "create"
    assert wire["task_id"] == "uuid-1"
    assert wire["text"] == "купить молоко"
    assert wire["day"] == "2026-04-14"
    assert wire["done"] is False
    assert wire["position"] == 0
    # change_id и ts НЕ попадают в wire
    assert "change_id" not in wire
    assert "ts" not in wire


def test_task_change_to_wire_update_partial():
    """UPDATE отправляет только не-None поля (partial update)."""
    tc = TaskChange(op="update", task_id="uuid-1", done=True)
    wire = tc.to_wire()
    assert wire == {"op": "update", "task_id": "uuid-1", "done": True}
    # text, day, position НЕ должны присутствовать
    assert "text" not in wire
    assert "day" not in wire


def test_task_change_to_wire_delete_minimal():
    """DELETE — только op + task_id."""
    tc = TaskChange(op="delete", task_id="uuid-1")
    wire = tc.to_wire()
    assert wire == {"op": "delete", "task_id": "uuid-1"}


def test_task_change_roundtrip_dict():
    """from_dict(to_dict(tc)) восстанавливает объект."""
    tc = TaskChange(op="create", task_id="uuid-1", text="hi", day="2026-04-14")
    restored = TaskChange.from_dict(tc.to_dict())
    assert restored.op == tc.op
    assert restored.task_id == tc.task_id
    assert restored.change_id == tc.change_id
    assert restored.ts == tc.ts


def test_day_plan_counts_alive_only():
    """DayPlan не считает tombstone-задачи."""
    t1 = Task.new(user_id="u", text="a", day="2026-04-14")
    t2 = Task.new(user_id="u", text="b", day="2026-04-14")
    t2.deleted_at = utcnow_iso()
    dp = DayPlan(day="2026-04-14", tasks=[t1, t2])
    assert dp.total == 1
    assert dp.done_count == 0


def test_week_plan_completion_pct_empty():
    """Пустая неделя = 100% completion (нет задач = всё сделано)."""
    wp = WeekPlan(week_start="2026-04-13", days=[])
    assert wp.completion_pct == 100


def test_app_state_defaults():
    """AppState имеет разумные дефолты (theme=dark, autostart=False)."""
    s = AppState()
    assert s.theme == "dark"
    assert s.autostart is False
    assert s.do_not_disturb is False
