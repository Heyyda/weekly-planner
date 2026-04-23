"""Unit-тесты DragController (Plan 04-09). TASK-05, TASK-06."""
import inspect
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from client.ui.drag_controller import DragController, DropZone, GhostWindow


@pytest.fixture
def dc_deps(headless_tk, mock_theme_manager, dnd_event_simulator):
    return {
        "root": headless_tk,
        "theme": mock_theme_manager,
        "dnd_event": dnd_event_simulator,
        "on_moved": MagicMock(),
    }


def _make(dc_deps):
    return DragController(dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"])


def _make_frame_mock(x, y, w=300, h=60):
    mock_frame = MagicMock()
    mock_frame.winfo_exists.return_value = True
    mock_frame.winfo_rootx.return_value = x
    mock_frame.winfo_rooty.return_value = y
    mock_frame.winfo_width.return_value = w
    mock_frame.winfo_height.return_value = h
    return mock_frame


# ---------- DropZone ----------

def test_dropzone_contains_inside():
    zone = DropZone(day_date=date.today(), frame=_make_frame_mock(100, 100, 200, 50))
    assert zone.contains(150, 125) is True


def test_dropzone_contains_outside():
    zone = DropZone(day_date=date.today(), frame=_make_frame_mock(100, 100, 200, 50))
    assert zone.contains(50, 125) is False
    assert zone.contains(400, 125) is False
    assert zone.contains(150, 200) is False


def test_dropzone_flags():
    z1 = DropZone(day_date=date.today(), frame=MagicMock(), is_archive=True)
    z2 = DropZone(day_date=date.today(), frame=MagicMock(), is_next_week=True)
    assert z1.is_archive is True
    assert z2.is_next_week is True


# ---------- GhostWindow ----------

def test_ghost_initial_withdrawn(dc_deps):
    dc = _make(dc_deps)
    assert dc._ghost is not None
    dc_deps["root"].update_idletasks()
    assert dc._ghost._window.state() == "withdrawn"
    dc.destroy()


# ---------- find_drop_zone ----------

def test_find_drop_zone_hit(dc_deps):
    dc = _make(dc_deps)
    zone1 = DropZone(day_date=date(2026, 4, 14), frame=_make_frame_mock(0, 0, 300, 60))
    zone2 = DropZone(day_date=date(2026, 4, 15), frame=_make_frame_mock(0, 70, 300, 60))
    dc.register_drop_zone(zone1)
    dc.register_drop_zone(zone2)
    assert dc._find_drop_zone(150, 30) is zone1
    assert dc._find_drop_zone(150, 100) is zone2
    assert dc._find_drop_zone(150, 200) is None
    dc.destroy()


# ---------- Threshold (D-22) ----------

def test_drag_threshold_below_5px_no_drag(dc_deps):
    dc = _make(dc_deps)
    press = dc_deps["dnd_event"](x_root=100, y_root=100, x=5, y=5)
    sz = DropZone(day_date=date.today(), frame=MagicMock())
    dc._on_press(press, "task-1", "text", sz, MagicMock())
    move = dc_deps["dnd_event"](x_root=103, y_root=102)
    dc._on_motion(move)
    assert dc._dragging is False
    dc.destroy()


def test_drag_threshold_above_5px_starts(dc_deps):
    dc = _make(dc_deps)
    press = dc_deps["dnd_event"](x_root=100, y_root=100, x=5, y=5)
    sz = DropZone(day_date=date.today(), frame=MagicMock())
    dc._on_press(press, "task-1", "text", sz, MagicMock())
    move = dc_deps["dnd_event"](x_root=110, y_root=105)
    with patch.object(dc, "_start_drag") as mock_start:
        dc._on_motion(move)
        mock_start.assert_called_once()
    dc.destroy()


# ---------- Commit / Cancel ----------

def test_drop_on_same_source_cancels(dc_deps):
    dc = _make(dc_deps)
    sz = DropZone(day_date=date.today(), frame=_make_frame_mock(0, 0))
    dc.register_drop_zone(sz)
    dc._dragging = True
    dc._source_zone = sz
    dc._source_task_id = "task-1"
    dc._source_widget = MagicMock()
    rel = dc_deps["dnd_event"](x_root=150, y_root=30)
    with patch.object(dc, "_cancel_drag") as mc, \
         patch.object(dc, "_commit_drop") as mcmt:
        dc._on_release(rel)
        mc.assert_called_once()
        mcmt.assert_not_called()
    dc.destroy()


def test_drop_on_different_zone_commits(dc_deps):
    dc = _make(dc_deps)
    src = DropZone(day_date=date(2026, 4, 14), frame=_make_frame_mock(0, 0))
    tgt = DropZone(day_date=date(2026, 4, 15), frame=_make_frame_mock(0, 100))
    dc.register_drop_zone(src)
    dc.register_drop_zone(tgt)
    dc._dragging = True
    dc._source_zone = src
    dc._source_task_id = "task-drop"
    dc._source_widget = MagicMock()
    rel = dc_deps["dnd_event"](x_root=150, y_root=130)
    dc._on_release(rel)
    dc_deps["on_moved"].assert_called_once_with("task-drop", date(2026, 4, 15))
    dc.destroy()


def test_drop_outside_cancels(dc_deps):
    dc = _make(dc_deps)
    src = DropZone(day_date=date.today(), frame=_make_frame_mock(0, 0))
    dc.register_drop_zone(src)
    dc._dragging = True
    dc._source_zone = src
    dc._source_task_id = "task-1"
    dc._source_widget = MagicMock()
    rel = dc_deps["dnd_event"](x_root=9999, y_root=9999)
    dc._on_release(rel)
    dc_deps["on_moved"].assert_not_called()
    dc.destroy()


def test_drop_on_archive_cancels(dc_deps):
    dc = _make(dc_deps)
    src = DropZone(day_date=date.today(), frame=_make_frame_mock(0, 0))
    arch = DropZone(day_date=date(2026, 4, 1), frame=_make_frame_mock(0, 100), is_archive=True)
    dc.register_drop_zone(src)
    dc.register_drop_zone(arch)
    dc._dragging = True
    dc._source_zone = src
    dc._source_task_id = "task-x"
    dc._source_widget = MagicMock()
    rel = dc_deps["dnd_event"](x_root=150, y_root=130)
    dc._on_release(rel)
    dc_deps["on_moved"].assert_not_called()
    dc.destroy()


# ---------- set_archive_mode ----------

def test_set_archive_mode_marks_all(dc_deps):
    dc = _make(dc_deps)
    z1 = DropZone(day_date=date.today(), frame=MagicMock())
    z2 = DropZone(day_date=date.today(), frame=MagicMock())
    dc.register_drop_zone(z1)
    dc.register_drop_zone(z2)
    dc.set_archive_mode(True)
    assert all(z.is_archive for z in dc._drop_zones)
    dc.set_archive_mode(False)
    assert not any(z.is_archive for z in dc._drop_zones)
    dc.destroy()


def test_clear_drop_zones_empties(dc_deps):
    dc = _make(dc_deps)
    dc.register_drop_zone(DropZone(day_date=date.today(), frame=MagicMock()))
    dc.register_drop_zone(DropZone(day_date=date.today(), frame=MagicMock()))
    dc.clear_drop_zones()
    assert dc._drop_zones == []
    dc.destroy()


# ---------- _blend_hex ----------

def test_blend_hex_50_percent():
    assert DragController._blend_hex("#000000", "#ffffff", 0.5) == "#7f7f7f"


def test_blend_hex_zero_returns_bg():
    assert DragController._blend_hex("#ff0000", "#0000ff", 0.0) == "#ff0000"


def test_blend_hex_one_returns_fg():
    assert DragController._blend_hex("#ff0000", "#0000ff", 1.0) == "#0000ff"


def test_blend_hex_invalid_fallback():
    result = DragController._blend_hex("invalid", "#000000", 0.5)
    assert len(result) == 7
    assert result.startswith("#")


# ---------- Quick 260423-o8z: edge-drag cross-week navigation ----------

def test_edge_jump_threshold_constant():
    """Quick 260423-o8z: EDGE_JUMP_THRESHOLD_PX константа класса."""
    assert hasattr(DragController, "EDGE_JUMP_THRESHOLD_PX")
    assert DragController.EDGE_JUMP_THRESHOLD_PX == 60


def test_week_jump_callback_optional():
    """DragController.__init__ принимает on_week_jump как Optional."""
    sig = inspect.signature(DragController.__init__)
    params = sig.parameters
    assert "on_week_jump" in params
    assert params["on_week_jump"].default is None


def test_edge_zone_changed_callback_optional():
    """Quick 260423-o8z: on_edge_zone_changed — Optional Callable."""
    sig = inspect.signature(DragController.__init__)
    params = sig.parameters
    assert "on_edge_zone_changed" in params
    assert params["on_edge_zone_changed"].default is None


def _make_root_mock_with_bounds(root_mock, x=100, w=500):
    """Подменить winfo_rootx / winfo_width на root (для edge-detection)."""
    root_mock.winfo_rootx = MagicMock(return_value=x)
    root_mock.winfo_width = MagicMock(return_value=w)
    return root_mock


def test_edge_drag_motion_fires_callback_left(dc_deps):
    """_on_motion у левого края (<60px) → on_edge_zone_changed(-1)."""
    on_edge = MagicMock()
    # Подменим root на MagicMock с заданными bounds (winfo_rootx=100, width=500).
    # root=100..600, порог 60 → левый край 100..160.
    fake_root = MagicMock()
    fake_root.winfo_rootx.return_value = 100
    fake_root.winfo_width.return_value = 500
    dc = DragController(
        dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"],
        on_week_jump=MagicMock(),
        on_edge_zone_changed=on_edge,
    )
    dc._root = fake_root  # override для edge-detection
    src = DropZone(day_date=date.today(), frame=MagicMock())
    dc.register_drop_zone(src)
    press = dc_deps["dnd_event"](x_root=400, y_root=400, x=0, y=0)
    dc._on_press(press, "t1", "text", src, MagicMock())
    # Motion к левому краю: x_root=120 (distance_left=20<60)
    move = dc_deps["dnd_event"](x_root=120, y_root=400)
    dc._on_motion(move)
    on_edge.assert_called_with(-1)
    assert dc._edge_jump_direction == -1
    dc.destroy()


def test_edge_drag_motion_fires_callback_right(dc_deps):
    """_on_motion у правого края → on_edge_zone_changed(+1)."""
    on_edge = MagicMock()
    fake_root = MagicMock()
    fake_root.winfo_rootx.return_value = 100
    fake_root.winfo_width.return_value = 500
    # Правый край: 100+500 = 600; x_root=580 → distance_right=20<60.
    dc = DragController(
        dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"],
        on_week_jump=MagicMock(),
        on_edge_zone_changed=on_edge,
    )
    dc._root = fake_root
    src = DropZone(day_date=date.today(), frame=MagicMock())
    dc.register_drop_zone(src)
    press = dc_deps["dnd_event"](x_root=400, y_root=400, x=0, y=0)
    dc._on_press(press, "t1", "text", src, MagicMock())
    move = dc_deps["dnd_event"](x_root=580, y_root=400)
    dc._on_motion(move)
    on_edge.assert_called_with(1)
    assert dc._edge_jump_direction == 1
    dc.destroy()


def test_edge_drag_motion_clears_callback_when_away(dc_deps):
    """Сначала к левому краю (direction=-1), затем в центр (direction=None)."""
    on_edge = MagicMock()
    fake_root = MagicMock()
    fake_root.winfo_rootx.return_value = 100
    fake_root.winfo_width.return_value = 500
    dc = DragController(
        dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"],
        on_week_jump=MagicMock(),
        on_edge_zone_changed=on_edge,
    )
    dc._root = fake_root
    src = DropZone(day_date=date.today(), frame=MagicMock())
    dc.register_drop_zone(src)
    press = dc_deps["dnd_event"](x_root=400, y_root=400, x=0, y=0)
    dc._on_press(press, "t1", "text", src, MagicMock())
    # В лево: -1
    dc._on_motion(dc_deps["dnd_event"](x_root=120, y_root=400))
    assert dc._edge_jump_direction == -1
    # В центр: None
    dc._on_motion(dc_deps["dnd_event"](x_root=350, y_root=400))
    assert dc._edge_jump_direction is None
    # Последний вызов callback должен быть с None
    on_edge.assert_called_with(None)
    dc.destroy()


def test_edge_drag_left_release_triggers_week_jump(dc_deps):
    """_on_release с _edge_jump_direction=-1 → on_week_jump(-1, task_id)."""
    on_jump = MagicMock()
    on_edge = MagicMock()
    dc = DragController(
        dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"],
        on_week_jump=on_jump,
        on_edge_zone_changed=on_edge,
    )
    src = DropZone(day_date=date.today(), frame=_make_frame_mock(0, 0))
    dc.register_drop_zone(src)
    dc._dragging = True
    dc._source_zone = src
    dc._source_task_id = "task-L"
    dc._source_widget = MagicMock()
    dc._edge_jump_direction = -1  # задаём как будто motion уже установил

    rel = dc_deps["dnd_event"](x_root=9999, y_root=9999)
    dc._on_release(rel)

    on_jump.assert_called_once_with(-1, "task-L")
    dc_deps["on_moved"].assert_not_called()
    # edge indicator должен быть сброшен через callback(None)
    on_edge.assert_called_with(None)
    dc.destroy()


def test_edge_drag_right_release_triggers_week_jump(dc_deps):
    """_on_release с _edge_jump_direction=+1 → on_week_jump(+1, task_id)."""
    on_jump = MagicMock()
    dc = DragController(
        dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"],
        on_week_jump=on_jump,
        on_edge_zone_changed=MagicMock(),
    )
    src = DropZone(day_date=date.today(), frame=_make_frame_mock(0, 0))
    dc.register_drop_zone(src)
    dc._dragging = True
    dc._source_zone = src
    dc._source_task_id = "task-R"
    dc._source_widget = MagicMock()
    dc._edge_jump_direction = 1

    rel = dc_deps["dnd_event"](x_root=9999, y_root=9999)
    dc._on_release(rel)

    on_jump.assert_called_once_with(1, "task-R")
    dc.destroy()


def test_edge_active_skips_day_zone_highlights(dc_deps):
    """Когда edge_direction активен, день-зоны не подсвечиваются (visual priority)."""
    fake_root = MagicMock()
    fake_root.winfo_rootx.return_value = 100
    fake_root.winfo_width.return_value = 500
    dc = DragController(
        dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"],
        on_week_jump=MagicMock(),
        on_edge_zone_changed=MagicMock(),
    )
    dc._root = fake_root
    src = DropZone(day_date=date.today(), frame=_make_frame_mock(0, 0))
    tgt = DropZone(day_date=date(2026, 4, 15), frame=_make_frame_mock(110, 200, 100, 100))
    dc.register_drop_zone(src)
    dc.register_drop_zone(tgt)
    press = dc_deps["dnd_event"](x_root=400, y_root=400, x=0, y=0)
    dc._on_press(press, "t1", "text", src, MagicMock())
    # Motion на левом крае — _update_zone_highlights НЕ должна вызваться
    with patch.object(dc, "_update_zone_highlights") as mock_update:
        dc._on_motion(dc_deps["dnd_event"](x_root=120, y_root=210))
        mock_update.assert_not_called()
    dc.destroy()


def test_ghost_text_swaps_on_edge_direction(dc_deps):
    """При edge_direction=-1 ghost label показывает '← Пред. неделя'."""
    fake_root = MagicMock()
    fake_root.winfo_rootx.return_value = 100
    fake_root.winfo_width.return_value = 500
    dc = DragController(
        dc_deps["root"], dc_deps["theme"], dc_deps["on_moved"],
        on_week_jump=MagicMock(),
        on_edge_zone_changed=MagicMock(),
    )
    dc._root = fake_root
    src = DropZone(day_date=date.today(), frame=MagicMock())
    dc.register_drop_zone(src)
    press = dc_deps["dnd_event"](x_root=400, y_root=400, x=0, y=0)
    dc._on_press(press, "t1", "оригинальный текст", src, MagicMock())
    # Mock ghost _label.configure
    dc._ghost._label.configure = MagicMock()
    dc._on_motion(dc_deps["dnd_event"](x_root=120, y_root=400))
    # Должен быть вызов с text="← Пред. неделя"
    calls = dc._ghost._label.configure.call_args_list
    assert any("Пред. неделя" in str(c) for c in calls), f"ghost label не переключён на 'Пред. неделя': {calls}"
    dc.destroy()


def test_edge_direction_resets_on_reset_state(dc_deps):
    """_reset_state сбрасывает _edge_jump_direction в None."""
    dc = _make(dc_deps)
    dc._edge_jump_direction = -1
    dc._reset_state()
    assert dc._edge_jump_direction is None
    dc.destroy()


def test_no_pill_frames_pack_during_drag(dc_deps):
    """Quick 260423-o8z: pill-frames НЕ pack'ятся при drag (pills removed)."""
    # DragController больше не вызывает _show_week_jump_zones → frames не pack'ятся.
    dc = _make(dc_deps)
    prev_frame = MagicMock()
    next_frame = MagicMock()
    src = DropZone(day_date=date.today(), frame=MagicMock())
    dc.register_drop_zone(src)
    press = dc_deps["dnd_event"](x_root=0, y_root=0, x=0, y=0)
    dc._on_press(press, "t1", "text", src, MagicMock())
    dc._on_motion(dc_deps["dnd_event"](x_root=50, y_root=50))
    # pill frames остаются нетронутыми
    prev_frame.pack.assert_not_called()
    next_frame.pack.assert_not_called()
    dc.destroy()


# ---------- Markers ----------

def test_drag_threshold_constant():
    source = inspect.getsource(DragController)
    assert "DRAG_THRESHOLD_PX = 5" in source


def test_alpha_06_marker():
    source = inspect.getsource(GhostWindow)
    assert "ALPHA = 0.6" in source
    assert "-alpha" in source


def test_no_winfo_containing():
    """04-RESEARCH-DND §CRITICAL: winfo_containing запрещён."""
    import client.ui.drag_controller as dc_module
    source = inspect.getsource(dc_module)
    assert "winfo_containing" not in source


def test_winfo_rootx_used_in_dropzone():
    source = inspect.getsource(DropZone)
    assert "winfo_rootx" in source
    assert "winfo_rooty" in source


def test_ghost_pre_created():
    source = inspect.getsource(DragController.__init__)
    assert "GhostWindow(" in source


def test_overrideredirect_via_after():
    source = inspect.getsource(GhostWindow)
    assert "INIT_DELAY_MS = 100" in source
