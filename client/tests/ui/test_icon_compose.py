"""Unit-тесты icon_compose.render_overlay_image (Forest Phase E refactor).

Overlay теперь плоский (без градиента):
  - bg = palette["bg_primary"]  (или Forest light default)
  - border = palette["bg_tertiary"]
  - glyph = palette["text_primary"]
  - badge = palette["accent_brand"] (forest) / palette["accent_overdue"] (clay)
"""
import pytest
from PIL import Image

from client.ui.icon_compose import (
    render_overlay_image,
    _hex_to_rgb,
    FOREST_BG,
    FOREST_BADGE,
    FOREST_OVERDUE,
    FOREST_TEXT,
    OVERLAY_BLUE_BOTTOM,  # legacy export (backward compat)
    OVERLAY_RED_BOTTOM,   # legacy export (backward compat)
)


# ============ Forest-light palette for tests ============
# Соответствует PALETTES["forest_light"] из client/ui/themes.py.

FOREST_LIGHT = {
    "bg_primary": "#EEE9DC",
    "bg_secondary": "#F5F0E3",
    "bg_tertiary": "#E2E0D2",
    "text_primary": "#2E2B24",
    "text_tertiary": "#9A958A",
    "accent_brand": "#1E5239",
    "accent_brand_light": "#234E3A",
    "accent_overdue": "#9E6A5A",
}


# ============ Basic invariants ============

def test_returns_pil_image_correct_size():
    img = render_overlay_image(56, "default", palette=FOREST_LIGHT)
    assert isinstance(img, Image.Image)
    assert img.size == (56, 56)
    assert img.mode == "RGBA"


def test_corner_pixel_transparent_rounded_clip():
    """Углы (0,0) прозрачны из-за rounded corners."""
    img = render_overlay_image(56, "default", palette=FOREST_LIGHT)
    r, g, b, a = img.getpixel((0, 0))
    assert a == 0, f"Corner (0,0) должен быть прозрачным, получили alpha={a}"


def test_center_pixel_not_transparent():
    img = render_overlay_image(56, "default", palette=FOREST_LIGHT)
    r, g, b, a = img.getpixel((28, 28))
    assert a > 0


def test_tray_size_16_does_not_crash():
    img = render_overlay_image(16, "default", palette=FOREST_LIGHT)
    assert img.size == (16, 16)


# ============ Flat palette-driven rendering ============

def test_overlay_uses_palette_bg():
    """bg_primary из палитры = фон плашки (внутри rounded, вне badge/icon)."""
    img = render_overlay_image(56, "default", palette=FOREST_LIGHT)
    # (5, 28) — левый край, середина по высоте. Вне icon, вне badge.
    # Должен соответствовать bg_primary #EEE9DC = (238, 233, 220).
    r, g, b, a = img.getpixel((5, 28))
    expected = _hex_to_rgb(FOREST_LIGHT["bg_primary"], (0, 0, 0))
    # Допуск ±10 на супер-сэмплинг LANCZOS-даунскейл
    for ch, exp in zip((r, g, b), expected):
        assert abs(ch - exp) <= 10, (
            f"bg pixel ({r},{g},{b}) должен ≈ palette bg_primary {expected}"
        )


def test_overlay_badge_forest_default():
    """Default state: badge fill == palette['accent_brand'] (forest зелёный)."""
    img = render_overlay_image(56, "default", task_count=3, palette=FOREST_LIGHT)
    # (50, 8) — внутри badge ellipse в правом верхнем углу, вне текста цифры.
    r, g, b, a = img.getpixel((50, 8))
    expected = _hex_to_rgb(FOREST_LIGHT["accent_brand"], (0, 0, 0))  # #1E5239
    for ch, exp in zip((r, g, b), expected):
        assert abs(ch - exp) <= 15, (
            f"badge pixel ({r},{g},{b}) должен ≈ palette accent_brand {expected}"
        )


def test_overlay_badge_clay_on_overdue():
    """Overdue state: badge fill == palette['accent_overdue'] (clay)."""
    img = render_overlay_image(56, "overdue", overdue_count=2, palette=FOREST_LIGHT)
    r, g, b, a = img.getpixel((50, 8))
    expected = _hex_to_rgb(FOREST_LIGHT["accent_overdue"], (0, 0, 0))  # #9E6A5A
    for ch, exp in zip((r, g, b), expected):
        assert abs(ch - exp) <= 15, (
            f"badge pixel ({r},{g},{b}) должен ≈ palette accent_overdue {expected}"
        )


def test_overlay_no_gradient_in_new_mode():
    """Forest flat: фон НЕ gradient → top и bottom строки bg-зоны ≈ одного цвета."""
    img = render_overlay_image(56, "default", palette=FOREST_LIGHT)
    # Две bg-точки: верх-лево, низ-лево (внутри rounded, вне icon/badge).
    # Координаты подобраны чтобы точно попасть в bg.
    top_bg = img.getpixel((5, 10))
    bot_bg = img.getpixel((5, 45))
    # При flat-рендере разница по каждому каналу ≤ 5 (шум от anti-aliasing на границе)
    for ch_top, ch_bot in zip(top_bg[:3], bot_bg[:3]):
        assert abs(ch_top - ch_bot) <= 5, (
            f"Flat фон: top {top_bg} должен ≈ bot {bot_bg}, нет градиента"
        )


def test_default_palette_is_forest_light_when_none():
    """palette=None → Forest-light defaults (не синий/красный)."""
    img = render_overlay_image(56, "default")  # no palette
    r, g, b, a = img.getpixel((5, 28))
    # Должно быть ≈ FOREST_BG (#F2EDE0)
    for ch, exp in zip((r, g, b), FOREST_BG):
        assert abs(ch - exp) <= 10, (
            f"Default (no palette) bg pixel ({r},{g},{b}) должен ≈ FOREST_BG {FOREST_BG}, "
            "НЕ синий и НЕ красный"
        )


def test_default_palette_badge_is_forest_when_none():
    """palette=None → badge = FOREST_BADGE (не синий)."""
    img = render_overlay_image(56, "default", task_count=1)
    r, g, b, a = img.getpixel((50, 8))
    for ch, exp in zip((r, g, b), FOREST_BADGE):
        assert abs(ch - exp) <= 15, (
            f"Default badge ({r},{g},{b}) должен ≈ FOREST_BADGE {FOREST_BADGE}"
        )


def test_default_palette_badge_clay_on_overdue_when_none():
    """palette=None + overdue → badge = FOREST_OVERDUE (clay)."""
    img = render_overlay_image(56, "overdue", overdue_count=1)
    r, g, b, a = img.getpixel((50, 8))
    for ch, exp in zip((r, g, b), FOREST_OVERDUE):
        assert abs(ch - exp) <= 15, (
            f"Overdue badge ({r},{g},{b}) должен ≈ FOREST_OVERDUE {FOREST_OVERDUE}"
        )


# ============ Badge visibility conditions ============

def test_no_badge_when_count_zero():
    """task_count=0 → no badge. Пиксель в badge-зоне должен быть ≈ bg, не accent."""
    img = render_overlay_image(56, "default", task_count=0, palette=FOREST_LIGHT)
    r, g, b, a = img.getpixel((50, 8))
    # accent_brand #1E5239 = (30, 82, 57). bg_primary (238, 233, 220). Разница огромна.
    accent = _hex_to_rgb(FOREST_LIGHT["accent_brand"], (0, 0, 0))
    diff = sum(abs(c - a_) for c, a_ in zip((r, g, b), accent))
    assert diff > 100, f"При task_count=0 в badge-зоне не должен быть accent"


def test_no_badge_on_small_icon():
    """size=16 + task_count=5 → no badge (badge только для size >= 32)."""
    img = render_overlay_image(16, "default", task_count=5, palette=FOREST_LIGHT)
    # (14, 1) — right-top corner at 16px. Должен быть bg или transparent, не badge.
    r, g, b, a = img.getpixel((14, 1))
    accent = _hex_to_rgb(FOREST_LIGHT["accent_brand"], (0, 0, 0))
    if a > 0:
        diff = sum(abs(c - a_) for c, a_ in zip((r, g, b), accent))
        assert diff > 50


# ============ Robustness ============

def test_robust_against_pulse_t_out_of_range():
    """Не крэшит при pulse_t вне [0,1]."""
    img = render_overlay_image(56, "overdue", overdue_count=1, pulse_t=1.5, palette=FOREST_LIGHT)
    assert img.size == (56, 56)
    img2 = render_overlay_image(56, "overdue", overdue_count=1, pulse_t=-0.3, palette=FOREST_LIGHT)
    assert img2.size == (56, 56)


def test_robust_against_missing_palette_keys():
    """Если palette неполный — fallback на Forest defaults, не crash."""
    partial_palette = {"bg_primary": "#FF00FF"}  # magenta для видимости; остальные ключи отсутствуют
    img = render_overlay_image(56, "default", task_count=1, palette=partial_palette)
    assert img.size == (56, 56)
    # bg должен быть magenta (задан), badge должен быть FOREST_BADGE (fallback)
    r, g, b, a = img.getpixel((5, 28))
    # Допуск большой т.к. border/supersampling blend
    assert r > 200 and b > 200, f"bg с заданным magenta ожидается, got ({r},{g},{b})"


def test_empty_state_draws_plus_not_checkmark():
    """state='empty' → плюс в центре (а не галочка)."""
    img_empty = render_overlay_image(56, "empty", palette=FOREST_LIGHT)
    img_default = render_overlay_image(56, "default", palette=FOREST_LIGHT)
    # Центр (28, 28) — у плюса пересечение линий (glyph color); у галочки между штрихами — bg
    center_empty = img_empty.getpixel((28, 28))
    center_default = img_default.getpixel((28, 28))
    # Оба — glyph-color (text_primary) потому что галочка и плюс оба проходят через центр
    # Отличие проверяется на другой точке — (18, 18): у плюса это bg, у галочки часть штриха
    point_empty = img_empty.getpixel((18, 18))
    point_default = img_default.getpixel((18, 18))
    # Обе рендерятся — main invariant: одна из двух точек должна отличаться
    all_same = point_empty == point_default and center_empty == center_default
    assert not all_same, "empty и default стат должны выглядеть по-разному"


# ============ Legacy compatibility ============

def test_legacy_constants_still_exported():
    """Старые OVERLAY_BLUE_BOTTOM / OVERLAY_RED_BOTTOM остаются доступны для импорта."""
    # Импорт на уровне модуля уже сработал; просто проверяем типы
    assert isinstance(OVERLAY_BLUE_BOTTOM, tuple) and len(OVERLAY_BLUE_BOTTOM) == 3
    assert isinstance(OVERLAY_RED_BOTTOM, tuple) and len(OVERLAY_RED_BOTTOM) == 3


# ============ Helpers ============

def test_hex_to_rgb_valid():
    assert _hex_to_rgb("#1E5239", (0, 0, 0)) == (30, 82, 57)
    assert _hex_to_rgb("1E5239", (0, 0, 0)) == (30, 82, 57)  # без #


def test_hex_to_rgb_fallback_on_bad_input():
    assert _hex_to_rgb(None, (1, 2, 3)) == (1, 2, 3)
    assert _hex_to_rgb("", (1, 2, 3)) == (1, 2, 3)
    assert _hex_to_rgb("#xyz", (1, 2, 3)) == (1, 2, 3)
    assert _hex_to_rgb("#12345", (1, 2, 3)) == (1, 2, 3)  # слишком короткий
