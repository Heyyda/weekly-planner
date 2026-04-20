"""Unit-тесты ColorTween (Forest Phase G).

Покрывает:
- Корректность hex↔rgb helpers
- Интерполяция (edge cases t=0, t=1, середина)
- Easing функции возвращают [0..1] на границах
- Мгновенный путь (duration=0, from==to, невалидный hex)
- Superseding cancel (новый tween отменяет старый)
- Защита от destroyed widget (winfo_exists=False mid-animation)
- on_complete вызывается ровно один раз при успешном завершении
"""
from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from client.ui.color_tween import (
    ColorTween,
    interpolate_hex,
    _hex_to_rgb,
    _rgb_to_hex,
    _ease_linear,
    _ease_in_cubic,
    _ease_out_cubic,
    _ease_in_out_cubic,
)


# ---------- Hex/RGB helpers ----------

def test_hex_to_rgb_basic():
    assert _hex_to_rgb("#000000") == (0, 0, 0)
    assert _hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert _hex_to_rgb("#1E5239") == (30, 82, 57)  # forest brand


def test_hex_to_rgb_no_hash():
    assert _hex_to_rgb("1E5239") == (30, 82, 57)


def test_hex_to_rgb_invalid_length_raises():
    with pytest.raises(ValueError):
        _hex_to_rgb("#FFF")
    with pytest.raises(ValueError):
        _hex_to_rgb("#FFFFFFF")


def test_hex_to_rgb_invalid_chars_raises():
    with pytest.raises(ValueError):
        _hex_to_rgb("#ZZZZZZ")


def test_hex_to_rgb_none_raises():
    with pytest.raises(ValueError):
        _hex_to_rgb(None)  # type: ignore[arg-type]


def test_rgb_to_hex_basic():
    assert _rgb_to_hex(0, 0, 0) == "#000000"
    assert _rgb_to_hex(255, 255, 255) == "#ffffff"
    assert _rgb_to_hex(30, 82, 57) == "#1e5239"


def test_rgb_to_hex_clamps():
    # Overshoot на easing ease-in-out при отрицательных t не должен ломать
    assert _rgb_to_hex(-10, 300, 128) == "#00ff80"


# ---------- interpolate_hex ----------

def test_interpolate_hex_t0_returns_from():
    assert interpolate_hex("#1E5239", "#5E9E7A", 0.0) == "#1e5239"


def test_interpolate_hex_t1_returns_to():
    assert interpolate_hex("#1E5239", "#5E9E7A", 1.0) == "#5e9e7a"


def test_interpolate_hex_mid_is_average():
    result = interpolate_hex("#000000", "#ffffff", 0.5)
    # round(255 * 0.5) = 127 или 128 в зависимости от int-trunc; наша _rgb_to_hex int(x) без round
    # 0 + (255-0)*0.5 = 127.5 → int() = 127
    assert result == "#7f7f7f"


def test_interpolate_hex_clamps_negative_t():
    # t < 0 → clamp к 0 → from
    assert interpolate_hex("#000000", "#ffffff", -0.5) == "#000000"


def test_interpolate_hex_clamps_overshoot_t():
    # t > 1 → clamp к 1 → to
    assert interpolate_hex("#000000", "#ffffff", 1.5) == "#ffffff"


# ---------- Easing functions ----------

@pytest.mark.parametrize("fn", [_ease_linear, _ease_in_cubic, _ease_out_cubic, _ease_in_out_cubic])
def test_easing_endpoints(fn):
    assert abs(fn(0.0) - 0.0) < 1e-9
    assert abs(fn(1.0) - 1.0) < 1e-9


def test_ease_linear_is_identity():
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert abs(_ease_linear(t) - t) < 1e-9


def test_ease_out_ahead_of_linear_in_first_half():
    # ease-out должен «обогнать» linear в начале (производная на 0 большая)
    assert _ease_out_cubic(0.25) > _ease_linear(0.25)


def test_ease_in_behind_linear_in_first_half():
    # ease-in стартует медленно
    assert _ease_in_cubic(0.25) < _ease_linear(0.25)


# ---------- ColorTween: instant fast paths ----------

def test_tween_duration_zero_applies_instant(headless_tk):
    """duration_ms=0 → widget.configure вызван сразу, on_complete сразу."""
    w = tk.Frame(headless_tk)
    complete_mock = MagicMock()
    # Frame не имеет text_color, используем "bg"
    ColorTween.tween(
        w, "bg", "#000000", "#ffffff",
        duration_ms=0, easing="linear", on_complete=complete_mock,
    )
    # bg применён сразу = "#ffffff"
    assert w.cget("bg").lower() in ("#ffffff", "white")
    complete_mock.assert_called_once()
    w.destroy()


def test_tween_from_equals_to_applies_instant(headless_tk):
    w = tk.Frame(headless_tk)
    complete_mock = MagicMock()
    ColorTween.tween(
        w, "bg", "#123456", "#123456",
        duration_ms=500, on_complete=complete_mock,
    )
    assert w.cget("bg").lower() == "#123456"
    complete_mock.assert_called_once()
    w.destroy()


def test_tween_invalid_from_hex_fallback_instant(headless_tk):
    """Невалидный hex → мгновенный set to_hex + on_complete."""
    w = tk.Frame(headless_tk)
    complete_mock = MagicMock()
    ColorTween.tween(
        w, "bg", "not-a-hex", "#abcdef",
        duration_ms=500, on_complete=complete_mock,
    )
    assert w.cget("bg").lower() == "#abcdef"
    complete_mock.assert_called_once()
    w.destroy()


def test_tween_on_destroyed_widget_is_silent(headless_tk):
    w = tk.Frame(headless_tk)
    w.destroy()
    # После destroy winfo_exists()=False — tween должен silent-no-op
    ColorTween.tween(w, "bg", "#000000", "#ffffff", duration_ms=100)


def test_tween_none_widget_is_silent():
    """None widget → no crash."""
    ColorTween.tween(None, "bg", "#000000", "#ffffff", duration_ms=100)


# ---------- ColorTween: progressive animation ----------

def test_tween_completes_by_pumping_updates(headless_tk):
    """Настоящий tween с духаленной анимацией (150ms) завершается → финальный
    цвет = to_hex + on_complete вызван."""
    w = tk.Frame(headless_tk)
    complete_mock = MagicMock()
    ColorTween.tween(
        w, "bg", "#000000", "#ffffff",
        duration_ms=80,  # короткий для быстрого теста
        easing="linear",
        on_complete=complete_mock,
    )
    # Pump event loop — после-вызовы отработают
    import time
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        headless_tk.update()
        if complete_mock.called:
            break
    assert complete_mock.called, "on_complete should fire after tween duration"
    # Финальный цвет = to_hex
    assert w.cget("bg").lower() == "#ffffff"
    w.destroy()


def test_superseding_tween_cancels_old(headless_tk):
    """Новый tween на той же (widget, property) отменяет старый — on_complete
    первого НЕ вызывается, on_complete второго вызывается."""
    w = tk.Frame(headless_tk)
    first_complete = MagicMock()
    second_complete = MagicMock()

    ColorTween.tween(
        w, "bg", "#000000", "#ff0000",
        duration_ms=500, easing="linear",
        on_complete=first_complete,
    )
    # Сразу запустить новый — первый должен быть cancelled
    ColorTween.tween(
        w, "bg", "#000000", "#00ff00",
        duration_ms=80, easing="linear",
        on_complete=second_complete,
    )

    import time
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        headless_tk.update()
        if second_complete.called:
            break

    assert second_complete.called
    assert not first_complete.called
    # Финальный цвет — зелёный, не красный
    assert w.cget("bg").lower() == "#00ff00"
    w.destroy()


def test_cancel_stops_tween(headless_tk):
    """ColorTween.cancel() останавливает tween — on_complete не вызывается."""
    w = tk.Frame(headless_tk)
    complete_mock = MagicMock()
    ColorTween.tween(
        w, "bg", "#000000", "#ffffff",
        duration_ms=500, on_complete=complete_mock,
    )
    cancelled = ColorTween.cancel(w, "bg")
    assert cancelled is True
    # Второй cancel вернёт False (нет активного tween)
    assert ColorTween.cancel(w, "bg") is False

    # Pump event loop чуть — on_complete не должен вызваться
    import time
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        headless_tk.update()

    assert not complete_mock.called
    w.destroy()


def test_cancel_all_clears_multiple_properties(headless_tk):
    """cancel_all() отменяет все твины на widget (разные property_name)."""
    w = tk.Frame(headless_tk)
    # bg и highlightbackground — два property
    ColorTween.tween(w, "bg", "#000000", "#ffffff", duration_ms=500)
    ColorTween.tween(w, "highlightbackground", "#111111", "#eeeeee", duration_ms=500)

    ColorTween.cancel_all(w)

    # Оба ключа удалены из _active
    assert (id(w), "bg") not in ColorTween._active
    assert (id(w), "highlightbackground") not in ColorTween._active
    w.destroy()


def test_tween_destroyed_mid_animation_no_crash(headless_tk):
    """Widget.destroy() во время анимации → tween silent-exits без TclError."""
    w = tk.Frame(headless_tk)
    complete_mock = MagicMock()
    ColorTween.tween(
        w, "bg", "#000000", "#ffffff",
        duration_ms=200, on_complete=complete_mock,
    )
    # Pump один кадр чтобы tween начался
    headless_tk.update()
    # Destroy mid-animation
    w.destroy()
    # Продолжаем pump — не должно быть исключений
    import time
    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        headless_tk.update()
    # on_complete не должен был вызваться (widget destroyed)
    assert not complete_mock.called


def test_tween_registry_cleans_up_after_completion(headless_tk):
    """После успешного завершения _active не держит ссылку на виджет."""
    w = tk.Frame(headless_tk)
    ColorTween.tween(
        w, "bg", "#000000", "#ffffff",
        duration_ms=80, easing="linear",
    )
    key = (id(w), "bg")
    assert key in ColorTween._active

    import time
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        headless_tk.update()
        if key not in ColorTween._active:
            break
    assert key not in ColorTween._active, "registry should be cleaned after completion"
    w.destroy()
