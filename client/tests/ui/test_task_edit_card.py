"""Unit-тесты TaskEditCard (Forest Phase D, Plan 260421-183).

Покрытие: build, pills, time, shortcuts, callbacks, palette switch.
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from client.ui.task_edit_card import TaskEditCard


@pytest.fixture
def tec_deps(headless_tk, mock_theme_manager, timestamped_task_factory):
    return {
        "parent": headless_tk,
        "theme": mock_theme_manager,
        "factory": timestamped_task_factory,
        "on_save": MagicMock(),
        "on_cancel": MagicMock(),
        "on_delete": MagicMock(),
    }


def _monday_of_today() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def _make(deps, task=None, week_monday=None) -> TaskEditCard:
    if task is None:
        task = deps["factory"](text="my task")
    if week_monday is None:
        week_monday = _monday_of_today()
    card = TaskEditCard(
        deps["parent"], task, week_monday, deps["theme"],
        on_save=deps["on_save"],
        on_cancel=deps["on_cancel"],
        on_delete=deps["on_delete"],
    )
    card.pack(fill="x")
    deps["parent"].update_idletasks()
    return card


# ---------- Build ----------

def test_card_builds_without_errors(tec_deps):
    card = _make(tec_deps)
    assert card.frame.winfo_exists()
    assert card._textbox is not None
    assert card._hh_entry is not None and card._mm_entry is not None
    assert card._done_var is not None
    card.destroy()


# ---------- Day pills ----------

def test_day_pills_show_7_days_from_week_monday(tec_deps):
    """7 pill'ов для дней недели + 2 (Сегодня/Завтра) = минимум 7 уникальных
    ISO-дат из week_monday..+6."""
    week_monday = _monday_of_today()
    card = _make(tec_deps, week_monday=week_monday)
    week_isos = {(week_monday + timedelta(days=i)).isoformat() for i in range(7)}
    registered_isos = {iso for iso, _btn in card._pills}
    # Все 7 дней недели представлены.
    assert week_isos.issubset(registered_isos)
    card.destroy()


def test_active_day_pill_matches_task_day(tec_deps):
    """selected_day инициализирован из task.day."""
    today_iso = date.today().isoformat()
    task = tec_deps["factory"](text="x")  # day_offset=0 → today
    assert task.day == today_iso
    card = _make(tec_deps, task=task)
    assert card._selected_day == today_iso
    card.destroy()


# ---------- Time ----------

def test_time_pre_populated_from_task(tec_deps):
    task = tec_deps["factory"](text="x", time="14:30")
    card = _make(tec_deps, task=task)
    assert card._hh_entry.get() == "14"
    assert card._mm_entry.get() == "30"
    card.destroy()


def test_clear_time_button_sets_time_to_none(tec_deps):
    task = tec_deps["factory"](text="x", time="09:15")
    card = _make(tec_deps, task=task)
    card._clear_time()
    card._on_save()
    tec_deps["on_save"].assert_called_once()
    fields = tec_deps["on_save"].call_args[0][0]
    assert fields["time_deadline"] is None
    card.destroy()


# ---------- Shortcuts / callbacks ----------

def test_escape_cancels(tec_deps):
    card = _make(tec_deps)
    # Имитируем Esc-биндинг напрямую (как в test_edit_dialog.py — тест вызывает
    # _cancel() а не event_generate).
    card._on_cancel_event(None)
    tec_deps["on_cancel"].assert_called_once()
    tec_deps["on_save"].assert_not_called()
    card.destroy()


def test_ctrl_enter_saves(tec_deps):
    card = _make(tec_deps)
    card._on_save_event(None)
    tec_deps["on_save"].assert_called_once()
    tec_deps["on_cancel"].assert_not_called()
    card.destroy()


def test_save_emits_on_save_with_updated_fields(tec_deps):
    task = tec_deps["factory"](text="orig", time="10:00")
    card = _make(tec_deps, task=task)
    # Отредактируем textbox
    card._textbox.delete("1.0", "end")
    card._textbox.insert("1.0", "new text")
    card._done_var.set(True)
    card._on_save()
    tec_deps["on_save"].assert_called_once()
    fields = tec_deps["on_save"].call_args[0][0]
    assert fields["text"] == "new text"
    assert fields["done"] is True
    assert fields["time_deadline"] == "10:00"
    assert fields["day"] == task.day
    card.destroy()


def test_delete_emits_on_delete(tec_deps):
    task = tec_deps["factory"](text="x")
    card = _make(tec_deps, task=task)
    card._on_delete()
    tec_deps["on_delete"].assert_called_once()
    card.destroy()


# ---------- Palette switch ----------

def test_palette_switch_updates_colors(tec_deps):
    """_apply_theme(palette) не падает и применяет новые цвета."""
    card = _make(tec_deps)
    from client.ui.themes import PALETTES
    card._apply_theme(PALETTES["dark"])
    # Border должен обновиться на accent_brand из dark-палитры.
    expected_border = PALETTES["dark"]["accent_brand"]
    assert card.frame.cget("border_color") == expected_border
    # Сам фрейм тоже обновился.
    assert card.frame.cget("fg_color") == PALETTES["dark"]["bg_secondary"]
    card.destroy()


# ---------- collect_fields safety ----------

def test_collect_fields_returns_none_for_empty_text(tec_deps):
    card = _make(tec_deps)
    card._textbox.delete("1.0", "end")
    fields = card.collect_fields()
    assert fields is None
    card.destroy()


# ---------- Forest Phase H: 3px left strip instead of full border ----------


def test_3px_accent_strip_exists(tec_deps):
    """Phase H Fix 3: карточка имеет отдельный 3px strip слева (composite HBox)
    вместо полной рамки border_width=2. _strip — CTkFrame с width=3 и
    fg_color=accent_brand."""
    card = _make(tec_deps)
    assert card._strip is not None
    assert card._strip.winfo_exists()
    # Width фиксирован 3px.
    assert int(card._strip.cget("width")) == 3
    # Цвет = accent_brand из текущей палитры.
    expected = tec_deps["theme"].get("accent_brand")
    assert card._strip.cget("fg_color") == expected
    card.destroy()


def test_frame_border_width_is_zero(tec_deps):
    """Phase H Fix 3: полная рамка убрана (BORDER_WIDTH=0) — визуально остаётся
    только 3px strip слева. Совпадает с forest-preview.html (edit-card::before
    absolute 3px, без border на контейнере в full-sense)."""
    card = _make(tec_deps)
    from client.ui.task_edit_card import TaskEditCard
    assert TaskEditCard.BORDER_WIDTH == 0
    # На живом виджете — тоже 0.
    assert int(card.frame.cget("border_width")) == 0
    card.destroy()


# ---------- Forest Phase K: instant open, no expand animation ----------


def test_pack_renders_card_immediately(tec_deps):
    """Phase K: карточка получает реальную высоту за один кадр — никакого
    shrink-to-1-then-grow. После pack() + update_idletasks reqheight должен
    отражать полный контент (textbox 56px + pills + time + buttons ≫ 40px),
    что невозможно если бы мы выставили height=1 через pack_propagate(False)."""
    card = _make(tec_deps)
    tec_deps["parent"].update_idletasks()
    # Реальная высота карточки — сумма textbox + 2 pill rows + time row + checkbox
    # + divider + buttons + padding. Минимум намного больше 40px.
    assert card.frame.winfo_reqheight() > 40, (
        f"Card rendered with height {card.frame.winfo_reqheight()} — "
        "expected full-content height, got shrunk frame (expand-anim regression?)"
    )
    card.destroy()


def test_no_expand_after_ids_scheduled_on_pack(tec_deps):
    """Phase K: pack() не должен планировать expand-step через frame.after
    или frame.after_idle. Проверяем патчем: ни один after-вызов не должен
    уходить с callable, имя которого содержит 'expand' или 'animate'."""
    task = tec_deps["factory"](text="my task")
    card = TaskEditCard(
        tec_deps["parent"], task, _monday_of_today(), tec_deps["theme"],
        on_save=tec_deps["on_save"],
        on_cancel=tec_deps["on_cancel"],
        on_delete=tec_deps["on_delete"],
    )

    # Собираем все callback'и, прошедшие через after / after_idle, ПОСЛЕ построения
    # карточки (build сам может легитимно использовать after — нас интересует ТОЛЬКО
    # то что добавляет pack()).
    real_after = card.frame.after
    real_after_idle = card.frame.after_idle
    after_calls: list[object] = []
    after_idle_calls: list[object] = []

    def spy_after(ms, func=None, *args):
        after_calls.append(func)
        return real_after(ms, func, *args) if func is not None else real_after(ms)

    def spy_after_idle(func, *args):
        after_idle_calls.append(func)
        return real_after_idle(func, *args)

    with patch.object(card.frame, "after", side_effect=spy_after), \
         patch.object(card.frame, "after_idle", side_effect=spy_after_idle):
        card.pack(fill="x")
        tec_deps["parent"].update_idletasks()

    def _is_anim_callback(cb) -> bool:
        if cb is None:
            return False
        name = getattr(cb, "__name__", "") or ""
        return (
            "expand" in name.lower()
            or "animate" in name.lower()
        )

    anim_after = [c for c in after_calls if _is_anim_callback(c)]
    anim_after_idle = [c for c in after_idle_calls if _is_anim_callback(c)]

    assert not anim_after, f"pack() scheduled expand/animate via after: {anim_after}"
    assert not anim_after_idle, (
        f"pack() scheduled expand/animate via after_idle: {anim_after_idle}"
    )
    # И класса у TaskEditCard нет animate_in / _expand_* методов (guard от регрессии).
    assert not hasattr(card, "animate_in"), (
        "TaskEditCard.animate_in должен быть удалён в Phase K"
    )
    assert not hasattr(card, "_expand_step"), (
        "TaskEditCard._expand_step должен быть удалён в Phase K"
    )
    assert not hasattr(card, "_expand_finish"), (
        "TaskEditCard._expand_finish должен быть удалён в Phase K"
    )
    assert not hasattr(TaskEditCard, "EXPAND_DURATION_MS"), (
        "TaskEditCard.EXPAND_DURATION_MS должен быть удалён в Phase K"
    )

    card.destroy()
