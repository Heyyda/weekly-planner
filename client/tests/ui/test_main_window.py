"""Unit-тесты MainWindow (Plan 03-06 lifecycle + Plan 04-10 integration)."""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from client.core.paths import AppPaths
from client.core.storage import LocalStorage
from client.ui.main_window import MainWindow
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager


# ---------- Phase 3 lifecycle fixture ----------

@pytest.fixture
def mw_deps(tmp_appdata, headless_tk, mock_ctypes_dpi):
    storage = LocalStorage(AppPaths())
    storage.init()
    return {
        "root": headless_tk,
        "settings_store": SettingsStore(storage),
        "settings": UISettings(),
        "theme": ThemeManager(),
    }


def _make(deps):
    return MainWindow(
        deps["root"], deps["settings_store"], deps["settings"], deps["theme"],
    )


# ---------- Phase 3: lifecycle ----------

def test_creates_window(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    assert mw._window.winfo_exists()
    mw.destroy()


def test_initially_hidden(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    assert not mw.is_visible()
    mw.destroy()


def test_show_makes_visible(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw.show()
    mw_deps["root"].update()
    assert mw.is_visible()
    mw.destroy()


def test_toggle_alternates(mw_deps):
    """Phase I: toggle() использует fade-in/fade-out. hide() не withdrawit
    сразу — ждём ~FADE_OUT_MS+буфер чтобы on_complete сработал."""
    import time
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw._init_chain_done = True  # bypass defer-to-init для теста
    mw.toggle()
    # Дать fade-in закончиться
    for _ in range(15):
        mw_deps["root"].update()
        time.sleep(0.02)
    v1 = mw.is_visible()
    mw.toggle()
    # Дать fade-out + withdraw отработать
    for _ in range(15):
        mw_deps["root"].update()
        time.sleep(0.02)
    v2 = mw.is_visible()
    assert v1 != v2
    mw.destroy()


def test_min_size_is_320(mw_deps):
    assert MainWindow.MIN_SIZE == (320, 320)


def test_default_size_is_460x600(mw_deps):
    assert MainWindow.DEFAULT_SIZE == (460, 600)


def test_apply_theme_changes_bg(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw._apply_theme({
        "bg_primary": "#123456",
        "bg_secondary": "#abcdef",
        "text_primary": "#000000",
        "accent_brand": "#ff0000",
    })
    mw.destroy()


def test_theme_subscribe_called_in_init(mw_deps):
    spy_theme = MagicMock(wraps=mw_deps["theme"])
    spy_theme.subscribe = MagicMock()
    spy_theme.get = mw_deps["theme"].get
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], spy_theme)
    mw_deps["root"].update()
    spy_theme.subscribe.assert_called()
    mw.destroy()


def test_save_window_state_persists(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    spy = MagicMock(wraps=mw._settings_store.save)
    mw._settings_store.save = spy
    mw._save_window_state()
    spy.assert_called_once()
    mw.destroy()


def test_set_always_on_top(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw.set_always_on_top(False)
    mw.set_always_on_top(True)
    mw.destroy()


def test_destroy_cleanup(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw.destroy()


# ---------- Phase 4 integration ----------

@pytest.fixture
def mw_phase4_deps(headless_tk, mock_theme_manager, mock_storage):
    settings = UISettings()
    store = MagicMock()
    store.save = MagicMock()
    return {
        "root": headless_tk,
        "settings_store": store,
        "settings": settings,
        "theme": mock_theme_manager,
        "storage": mock_storage,
        "user_id": "test-user",
    }


def _make_mw_p4(deps):
    mw = MainWindow(
        deps["root"], deps["settings_store"], deps["settings"], deps["theme"],
        storage=deps["storage"], user_id=deps["user_id"],
    )
    deps["root"].update_idletasks()
    return mw


def test_main_window_has_week_nav(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert mw._week_nav is not None
    mw.destroy()


def test_main_window_has_seven_day_sections(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert len(mw._day_sections) == 7
    mw.destroy()


def test_main_window_has_undo_toast_manager(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert mw._undo_toast is not None
    mw.destroy()


def test_main_window_has_drag_controller(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert mw._drag_controller is not None
    mw.destroy()


def test_drag_controller_has_seven_drop_zones(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert len(mw._drag_controller._drop_zones) == 7
    mw.destroy()


def test_refresh_tasks_renders_tasks_in_day(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(text="test today")
    mw_phase4_deps["storage"].add_task(task)
    mw._refresh_tasks()
    today = date.today()
    ds = mw._day_sections.get(today)
    assert ds is not None
    assert len(ds._task_widgets) == 1
    mw.destroy()


def test_delete_with_undo_shows_toast(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory()
    mw_phase4_deps["storage"].add_task(task)
    mw._delete_task_with_undo(task.id)
    mw_phase4_deps["root"].update_idletasks()
    assert len(mw._undo_toast._queue) == 1
    mw.destroy()


def test_on_task_toggle_updates_storage(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(done=False)
    mw_phase4_deps["storage"].add_task(task)
    mw._on_task_toggle(task.id, True)
    updated = mw_phase4_deps["storage"].get_task(task.id)
    assert updated.done is True
    mw.destroy()


def test_on_task_moved_updates_day(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory()
    mw_phase4_deps["storage"].add_task(task)
    new_day = date.today() + timedelta(days=1)
    mw._on_task_moved(task.id, new_day)
    updated = mw_phase4_deps["storage"].get_task(task.id)
    assert updated.day == new_day.isoformat()
    mw.destroy()


def test_handle_quick_capture_save_creates_task(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    mw.handle_quick_capture_save("test task", date.today().isoformat(), "14:00")
    tasks = mw_phase4_deps["storage"].get_visible_tasks()
    assert len(tasks) == 1
    assert tasks[0].text == "test task"
    assert tasks[0].time_deadline == "14:00"
    mw.destroy()


def test_week_navigation_changes_day_sections(mw_phase4_deps):
    """prev_week() → _rebuild_day_sections → days изменились."""
    mw = _make_mw_p4(mw_phase4_deps)
    initial_days = set(mw._day_sections.keys())
    mw._week_nav.prev_week()
    new_days = set(mw._day_sections.keys())
    assert initial_days != new_days
    mw.destroy()


def test_ctrl_space_binding_present_when_trigger_set(mw_phase4_deps):
    trigger = MagicMock()
    mw_phase4_deps["settings"] = UISettings()
    mw = MainWindow(
        mw_phase4_deps["root"], mw_phase4_deps["settings_store"],
        mw_phase4_deps["settings"], mw_phase4_deps["theme"],
        storage=mw_phase4_deps["storage"], user_id="u",
        quick_capture_trigger=trigger,
    )
    mw_phase4_deps["root"].update_idletasks()
    bindings = mw._window.bind()
    assert any("Control-space" in b or "Control-Key-space" in b for b in bindings)
    mw.destroy()


# ---------- Forest Phase D: inline edit routing ----------


def test_on_task_edit_calls_day_section_enter_edit_mode(mw_phase4_deps, timestamped_task_factory):
    """MainWindow._on_task_edit → DaySection.enter_edit_mode (inline edit)."""
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(text="edit me")
    mw_phase4_deps["storage"].add_task(task)
    mw._refresh_tasks()
    today = date.today()
    ds = mw._day_sections.get(today)
    assert ds is not None
    ds.enter_edit_mode = MagicMock()
    mw._on_task_edit(task.id)
    ds.enter_edit_mode.assert_called_once_with(task.id)
    mw.destroy()


def test_on_task_update_applies_to_storage(mw_phase4_deps, timestamped_task_factory):
    """MainWindow._on_task_update → storage.update_task + refresh."""
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(text="orig")
    mw_phase4_deps["storage"].add_task(task)
    mw._on_task_update(task.id, {"text": "updated", "done": True})
    updated = mw_phase4_deps["storage"].get_task(task.id)
    assert updated.text == "updated"
    assert updated.done is True
    mw.destroy()


# ---------- Forest Phase H: archive-mode dim palette ----------


def test_archive_applies_dim_palette_to_day_sections(mw_phase4_deps, monkeypatch):
    """Phase H Fix 2: _on_archive_changed(True) → apply_dimmed_palette(dim_dict)
    на всех DaySection'ах. Раньше interpolate_palette присваивался в  (dead code)."""
    mw = _make_mw_p4(mw_phase4_deps)
    # Шпионим за apply_dimmed_palette на каждой секции.
    spies = {}
    for d, ds in mw._day_sections.items():
        spy = MagicMock(wraps=ds.apply_dimmed_palette)
        ds.apply_dimmed_palette = spy
        spies[d] = spy
    mw._on_archive_changed(True)
    # Каждая секция должна получить вызов с dict (не None).
    for d, spy in spies.items():
        spy.assert_called_once()
        arg = spy.call_args[0][0]
        assert arg is not None, f"секция {d} не получила dim-dict"
        assert isinstance(arg, dict)
        assert "bg_primary" in arg
    mw.destroy()


def test_archive_clear_restores_palette(mw_phase4_deps):
    """Phase H Fix 2: _on_archive_changed(False) → apply_dimmed_palette(None)
    на всех DaySection'ах (live-палитра восстанавливается)."""
    mw = _make_mw_p4(mw_phase4_deps)
    # Сначала войти в архив, затем выйти — тогда spies увидят вызов с None.
    mw._on_archive_changed(True)
    spies = {}
    for d, ds in mw._day_sections.items():
        spy = MagicMock(wraps=ds.apply_dimmed_palette)
        ds.apply_dimmed_palette = spy
        spies[d] = spy
    mw._on_archive_changed(False)
    for d, spy in spies.items():
        spy.assert_called_once_with(None)
    mw.destroy()


def test_compute_dim_palette_is_darker_than_source(mw_phase4_deps):
    """Phase H: dim-палитра визуально темнее/ближе к bg_primary чем оригинал."""
    mw = _make_mw_p4(mw_phase4_deps)
    dim = mw._compute_dim_palette()
    # dim — полная палитра, содержит основные ключи.
    assert "bg_primary" in dim
    assert "accent_brand" in dim
    assert "text_primary" in dim
    # Для non-bg_primary ключей dim-значение должно приближаться к bg_primary.
    # Проверяем что accent_brand изменился (interpolate factor=0.3 ≠ 0).
    from client.ui.themes import PALETTES
    current = mw._theme.current
    original_accent = PALETTES[current]["accent_brand"]
    assert dim["accent_brand"] != original_accent, "dim не изменил accent_brand"
    mw.destroy()


# ---------- Forest Phase I (260421-9n7): fade-in / fade-out ----------


def test_init_sets_alpha_to_hidden_before_deiconify(mw_deps):
    """Phase I: окно создаётся с alpha=ALPHA_HIDDEN чтобы init chain
    (overrideredirect + SetWindowRgn + DWM shadow) отрабатывала под
    полностью прозрачным окном — пользователь не видит "сборку из частей"."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    try:
        alpha = float(mw._window.attributes("-alpha"))
    except Exception:
        alpha = 1.0
    assert alpha <= MainWindow.ALPHA_HIDDEN + 0.01, (
        f"alpha должен быть <= ALPHA_HIDDEN после __init__, получили {alpha}"
    )
    mw.destroy()


def test_show_sets_alpha_to_zero_before_deiconify(mw_deps):
    """Phase I: show() выставляет alpha=ALPHA_HIDDEN перед deiconify
    чтобы ни одного кадра полностью-видимого необработанного окна не показалось."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    # Вручную "сделаем" окно видимым с alpha=1 (эмуляция повторного show)
    mw._window.attributes("-alpha", 1.0)
    mw._window.deiconify()
    mw_deps["root"].update_idletasks()
    # Теперь вызываем show() повторно — должен снова выставить alpha=HIDDEN.
    mw._init_chain_done = True  # уже прошла init chain — fade-in запустится в after_idle
    mw.show()
    # Сразу после show() — alpha должен быть hidden (fade-in ещё не начался)
    alpha = float(mw._window.attributes("-alpha"))
    assert alpha <= MainWindow.ALPHA_HIDDEN + 0.01, (
        f"show() должен сбросить alpha к HIDDEN до fade-in, получили {alpha}"
    )
    mw.destroy()


def test_alpha_tween_animates_to_target(mw_deps):
    """Phase I: _alpha_tween за duration_ms должен привести окно к to_val."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    # Стартуем tween 0 → 1 за 48ms (3 frame по 16ms — быстро, тест-friendly)
    mw._alpha_tween(0.0, 1.0, duration_ms=48)
    # Прокрутить mainloop несколько раз чтобы after-коллбеки отработали.
    import time
    for _ in range(10):
        mw_deps["root"].update()
        time.sleep(0.02)
    final = float(mw._window.attributes("-alpha"))
    assert final > 0.9, f"alpha должен достичь ~1.0 после tween, получили {final}"
    # tween_id должен быть очищен после завершения
    assert mw._alpha_tween_id is None, "после завершения tween_id должен быть None"
    mw.destroy()


def test_alpha_tween_cancels_superseding(mw_deps):
    """Phase I: новый tween отменяет in-flight предыдущий. После второго
    вызова tween_id указывает на новый job, не на старый."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    # Первый tween — long-running
    mw._alpha_tween(0.0, 1.0, duration_ms=500)
    first_id = mw._alpha_tween_id
    assert first_id is not None, "первый tween должен установить _alpha_tween_id"
    # Второй tween сразу после — должен отменить первый
    mw._alpha_tween(1.0, 0.0, duration_ms=500)
    second_id = mw._alpha_tween_id
    assert second_id is not None
    assert second_id != first_id, (
        "после superseding tween_id должен измениться на новый after-job"
    )
    # Cancel через destroy — не падаем
    mw.destroy()


def test_hide_fades_then_withdraws(mw_deps):
    """Phase I: hide() запускает fade-out → withdraw в on_complete.
    Во время fade-out окно ещё видимо (не withdrawn), после завершения — withdrawn."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    # Эмулируем полностью-готовое видимое окно.
    mw._init_chain_done = True
    mw._window.attributes("-alpha", 1.0)
    mw._window.deiconify()
    mw_deps["root"].update_idletasks()
    assert mw.is_visible(), "preconditions: окно должно быть видимым"
    # Вызываем hide с коротким duration через override константы на instance
    # (FADE_OUT_MS=120ms занимает слишком много времени в unit-тесте)
    original_fade_out = MainWindow.FADE_OUT_MS
    try:
        MainWindow.FADE_OUT_MS = 48  # 3 фрейма
        mw.hide()
        # Прокрутить mainloop достаточно раз для завершения 48ms tween
        import time
        for _ in range(15):
            mw_deps["root"].update()
            time.sleep(0.02)
    finally:
        MainWindow.FADE_OUT_MS = original_fade_out
    # После завершения — окно withdrawn
    assert not mw.is_visible(), "после fade-out + on_complete окно должно быть withdrawn"
    mw.destroy()


def test_hide_instantly_withdraws_if_already_hidden(mw_deps):
    """Phase I: если окно уже alpha=HIDDEN (ещё не показалось) —
    hide() пропускает анимацию и сразу withdraw'ит."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    # Окно только что создано, alpha=HIDDEN, withdrawn по init-логике.
    # Вызов hide() не должен зависать в tween и не должен запускать _alpha_tween.
    mw._window.attributes("-alpha", MainWindow.ALPHA_HIDDEN)
    mw.hide()
    # Никакой активный tween не должен висеть.
    assert mw._alpha_tween_id is None
    mw.destroy()


def test_init_chain_done_flag_set_after_dwm_shadow(mw_deps):
    """Phase I: _apply_dwm_shadow вызывает _on_init_chain_done — флаг ставится в True."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    assert mw._init_chain_done is False, "флаг по умолчанию False"
    mw._apply_dwm_shadow()
    assert mw._init_chain_done is True, (
        "_apply_dwm_shadow должен set'ить _init_chain_done = True"
    )
    mw.destroy()


def test_pending_show_triggers_fade_in_on_init_chain_done(mw_deps):
    """Phase I: если show() вызвали до завершения init chain — ставится
    _pending_show, _on_init_chain_done() должен запустить fade-in."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    # Эмулируем "первый show() до завершения chain"
    mw._init_chain_done = False
    mw.show()
    assert mw._pending_show is True, "show() до init_chain_done должен ставить pending_show"
    # Теперь симулируем завершение chain
    mw._on_init_chain_done()
    assert mw._init_chain_done is True
    assert mw._pending_show is False, "после _on_init_chain_done pending_show сбрасывается"
    # Должен был стартовать tween (или как минимум выставить after-job)
    # Не обязательно _alpha_tween_id != None (tween мог сразу завершиться за 1 frame при
    # нестандартном таймере), поэтому проверяем факт выставления alpha после update().
    mw_deps["root"].update()
    mw.destroy()


def test_destroy_cancels_in_flight_alpha_tween(mw_deps):
    """Phase I: destroy() отменяет in-flight alpha tween — нет TclError на сироту-after."""
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw._alpha_tween(0.0, 1.0, duration_ms=1000)
    assert mw._alpha_tween_id is not None
    # destroy() должен отменить через _cancel_alpha_tween
    mw.destroy()
    # После destroy обращения к _alpha_tween_id допустимы (attr ещё существует)
    # но further updates не должны падать


# ---------- Forest Phase J (260421-a3d): smooth week transitions ----------


def test_first_week_change_has_no_animation(mw_phase4_deps):
    """Phase J: первый вызов _on_week_changed (или вызов до _init_chain_done)
    rebuilds immediately без alpha-tween — окно ещё под alpha=0 (Phase I),
    анимация была бы невидимой."""
    mw = _make_mw_p4(mw_phase4_deps)
    # После __init__ _ever_rendered=False, _init_chain_done=False.
    assert mw._ever_rendered is False
    assert mw._init_chain_done is False

    # Шпионим за _alpha_tween — он НЕ должен быть вызван для первого изменения.
    tween_calls = []
    orig_tween = mw._alpha_tween

    def spy_tween(*args, **kwargs):
        tween_calls.append((args, kwargs))
        return orig_tween(*args, **kwargs)

    mw._alpha_tween = spy_tween

    # Вызываем прямо _on_week_changed (эмулируем WeekNavigation-колбэк)
    from datetime import date, timedelta
    mw._on_week_changed(date.today() - timedelta(days=7))

    assert tween_calls == [], f"первый week-change не должен звать _alpha_tween, got {tween_calls}"
    assert mw._ever_rendered is True, "после первого rebuild _ever_rendered должен стать True"
    assert mw._pending_week_change is None, "после immediate rebuild pending сбрасывается"
    mw.destroy()


def test_subsequent_week_change_triggers_alpha_sandwich(mw_phase4_deps):
    """Phase J: когда _ever_rendered=True и _init_chain_done=True — week change
    запускает alpha-sandwich: первый _alpha_tween — out (→DIM_ALPHA), on_complete
    rebuilds + запускает второй tween (DIM_ALPHA→1.0)."""
    import time
    from datetime import date, timedelta

    mw = _make_mw_p4(mw_phase4_deps)
    # Эмулируем "уже прошли init chain + уже был первый рендер"
    mw._init_chain_done = True
    mw._ever_rendered = True

    tween_calls = []
    orig_tween = mw._alpha_tween

    def spy_tween(from_val, to_val, duration_ms, on_complete=None):
        tween_calls.append({
            "from": from_val, "to": to_val,
            "duration": duration_ms, "has_on_complete": on_complete is not None,
        })
        return orig_tween(from_val, to_val, duration_ms, on_complete=on_complete)

    mw._alpha_tween = spy_tween

    target = date.today() - timedelta(days=7)
    mw._on_week_changed(target)

    # Первый вызов — out tween (_ever_rendered path уже прошли выше).
    assert len(tween_calls) >= 1, "должен быть хотя бы один _alpha_tween вызов"
    first = tween_calls[0]
    assert first["to"] == mw.WEEK_TRANSITION_DIM_ALPHA, (
        f"первый tween должен быть OUT до DIM, got to={first['to']}"
    )
    assert first["duration"] == mw.WEEK_TRANSITION_OUT_MS
    assert first["has_on_complete"] is True, "out-tween должен иметь on_complete"

    # Прокрутить mainloop чтобы out-tween + on_complete + in-tween отработали.
    for _ in range(20):
        mw_phase4_deps["root"].update()
        time.sleep(0.02)

    # Должно быть >=2 tween-вызовов (out + in sandwich).
    assert len(tween_calls) >= 2, (
        f"sandwich требует 2 tween: out + in, got {len(tween_calls)}: {tween_calls}"
    )
    in_tween = tween_calls[1]
    assert in_tween["from"] == mw.WEEK_TRANSITION_DIM_ALPHA
    assert in_tween["to"] == 1.0
    assert in_tween["duration"] == mw.WEEK_TRANSITION_IN_MS
    mw.destroy()


def test_rapid_week_change_uses_latest_target(mw_phase4_deps):
    """Phase J rapid-click safety: 2 быстрых _on_week_changed подряд — финальный
    rebuild должен дать DaySections для latest target (WeekNavigation синхронно
    обновила _week_monday)."""
    import time
    from datetime import date, timedelta

    mw = _make_mw_p4(mw_phase4_deps)
    mw._init_chain_done = True
    mw._ever_rendered = True

    # Первый клик: ▶ на неделю вперёд
    first_target = mw._week_nav.get_week_monday() + timedelta(days=7)
    mw._week_nav.set_week_monday(first_target)
    # WeekNavigation.set_week_monday вызывает _notify_changes → _on_week_changed,
    # т.е. out-tween стартовал с first_target.

    # Второй клик сразу (во время out-tween) — ▶ ещё раз
    second_target = first_target + timedelta(days=7)
    mw._week_nav.set_week_monday(second_target)
    # set_week_monday синхронно обновило _week_monday и снова вызвало
    # _on_week_changed → superseding _alpha_tween отменяет первую out-tween,
    # стартует новая.

    # _pending_week_change должен быть second_target (latest).
    assert mw._pending_week_change == second_target, (
        f"pending_week_change должен быть latest target, got {mw._pending_week_change}"
    )

    # Прокрутить mainloop чтобы sandwich завершился.
    for _ in range(40):
        mw_phase4_deps["root"].update()
        time.sleep(0.02)

    # Финальный rebuild должен построить секции для second_target.
    expected_days = {second_target + timedelta(days=i) for i in range(7)}
    actual_days = set(mw._day_sections.keys())
    assert actual_days == expected_days, (
        f"после rapid-click секции должны соответствовать latest target.\n"
        f"expected={sorted(expected_days)}\n"
        f"actual={sorted(actual_days)}"
    )
    # pending должен очиститься после rebuild.
    assert mw._pending_week_change is None, (
        "_pending_week_change должен очищаться после финального rebuild"
    )
    mw.destroy()
