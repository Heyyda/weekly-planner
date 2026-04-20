"""
Pillow-композитор иконки overlay/tray.

Используется:
  - Plan 03-04 OverlayManager (статичная отрисовка 56x56 canvas image)
  - Plan 03-05 PulseAnimator (60fps перерисовка с pulse_t 0..1)
  - Plan 03-07 TrayManager (16/32px tray icon)

Forest Phase E (260421-1jo):
  render_overlay_image теперь palette-aware. Если palette передана — цвета
  берутся оттуда (бэк, галочка, бейдж). Если None — Forest-light defaults.
  Gradient-ветка рендеринга убрана из default/overdue path (осталась как
  legacy helper для возможных будущих тем). Pulse на overdue — теперь
  solid clay badge (никакого blending main square).
"""
from __future__ import annotations

from typing import Optional

from PIL import Image, ImageDraw

# ---- Legacy gradient-константы (для старых blue-gradient icon tray-use cases).
# В Forest-рендере НЕ используются, но экспортируются для backward compatibility.

OVERLAY_BLUE_TOP    = (78, 161, 255)   # #4EA1FF (gradient top)
OVERLAY_BLUE_BOTTOM = (30, 115, 232)   # #1E73E8 (gradient bottom / tray solid)
OVERLAY_RED_TOP     = (232, 90, 90)    # #E85A5A (overdue top)
OVERLAY_RED_BOTTOM  = (192, 53, 53)    # #C03535 (overdue bottom)
WHITE               = (255, 255, 255)
BADGE_TEXT          = (30, 30, 30)     # тёмный текст badge

# ---- Forest fallback-константы (когда palette=None) ----
# Verbatim из forest-preview.html §5 (forest_light tokens).

FOREST_BG          = (242, 237, 224)   # #F2EDE0 bg_overlay_square (light)
FOREST_BORDER      = (206, 196, 174)   # #CEC4AE border_emphasis (light)
FOREST_TEXT        = (46, 43, 36)      # #2E2B24 text_primary (light)
FOREST_BADGE       = (30, 82, 57)      # #1E5239 accent_brand forest (light)
FOREST_BADGE_TEXT  = (238, 233, 220)   # #EEE9DC bg_primary cream (light)
FOREST_OVERDUE     = (158, 106, 90)    # #9E6A5A accent_overdue clay (light)

# Размерные коэффициенты (от стороны иконки)
CORNER_RADIUS_FRAC = 12 / 56     # 21.4% ≈ UI-SPEC radius 12px на 56px
BADGE_SIZE_FRAC    = 18 / 56     # 32.1% — 18px badge на 56px (forest-preview)
ICON_SIZE_FRAC     = 0.55        # 55% → галочка/плюс вписаны в центр


# ---- Public API ----

def render_overlay_image(
    size: int,
    state: str = "default",
    task_count: int = 0,
    overdue_count: int = 0,
    pulse_t: float = 0.0,
    palette: Optional[dict] = None,
) -> Image.Image:
    """
    Создать PIL.Image (RGBA) — rounded-square + иконка + badge.
    Supersampling 3x для плавных краёв.

    Args:
        size: сторона в пикселях (16, 32, 56 …)
        state: 'default' | 'empty' | 'overdue'
        task_count: показывается в badge при state='default'
        overdue_count: показывается в badge при state='overdue'
        pulse_t: 0..1 период pulse (используется только для badge scale в overdue)
        palette: словарь с ключами bg_primary, bg_tertiary, text_primary,
                 accent_brand, accent_overdue. Если None — Forest-light defaults.
    """
    if size >= 24:
        hi = _render_overlay_image_raw(size * 3, state, task_count, overdue_count, pulse_t, palette)
        return hi.resize((size, size), Image.LANCZOS)
    return _render_overlay_image_raw(size, state, task_count, overdue_count, pulse_t, palette)


def _render_overlay_image_raw(
    size: int,
    state: str = "default",
    task_count: int = 0,
    overdue_count: int = 0,
    pulse_t: float = 0.0,
    palette: Optional[dict] = None,
) -> Image.Image:
    """Raw renderer — вызывается через render_overlay_image с supersampling."""
    # Робастная обработка pulse_t
    try:
        t = float(pulse_t)
    except (TypeError, ValueError):
        t = 0.0
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = t - int(t)

    # ---- Резолв палитры ----
    colors = _resolve_palette(palette)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ---- Rounded square — сплошной bg + 1px border (Forest flat) ----
    radius = max(2, int(size * CORNER_RADIUS_FRAC))
    # Border width пропорциональна размеру (1px на 56px = 3px при supersampling 3x)
    border_w = max(1, size // 56) if size >= 32 else 1

    if size >= 32:
        draw.rounded_rectangle(
            [(0, 0), (size - 1, size - 1)],
            radius=radius,
            fill=(*colors["bg"], 255),
            outline=(*colors["border"], 255),
            width=border_w,
        )
    else:
        # Tray 16px — чистый solid, без border (read-ability)
        draw.rounded_rectangle(
            [(0, 0), (size - 1, size - 1)],
            radius=radius,
            fill=(*colors["bg"], 255),
        )

    # ---- Центральная иконка ----
    icon_size = int(size * ICON_SIZE_FRAC)
    ix = (size - icon_size) // 2
    iy = (size - icon_size) // 2
    if state == "empty":
        _draw_plus(draw, ix, iy, icon_size, colors["glyph"])
    else:
        _draw_checkmark(draw, ix, iy, icon_size, colors["glyph"])

    # ---- Badge ----
    badge_count = overdue_count if state == "overdue" else task_count
    if badge_count > 0 and size >= 32:
        badge_fill = colors["badge_overdue"] if state == "overdue" else colors["badge_fill"]
        _draw_badge(
            draw,
            size,
            badge_count,
            fill=badge_fill,
            text=colors["badge_text"],
            border=colors["bg"],  # badge border = bg overlay square (визуальный pop)
        )

    return img


# ---- Internal helpers ----

def _resolve_palette(palette: Optional[dict]) -> dict:
    """Превратить hex-палитру из themes.py в RGB tuples. Forest-light defaults если None.

    Mapping:
        bg                → palette["bg_primary"]       (или FOREST_BG)
        border            → palette["bg_tertiary"]      (или FOREST_BORDER)
                            (themes.py не экспортирует border_emphasis; bg_tertiary — tint-level)
        glyph             → palette["text_primary"]     (или FOREST_TEXT)
        badge_fill        → palette["accent_brand"]     (или FOREST_BADGE)
        badge_text        → palette["bg_primary"]       (или FOREST_BADGE_TEXT)
        badge_overdue     → palette["accent_overdue"]   (или FOREST_OVERDUE)
    """
    if palette is None:
        return {
            "bg": FOREST_BG,
            "border": FOREST_BORDER,
            "glyph": FOREST_TEXT,
            "badge_fill": FOREST_BADGE,
            "badge_text": FOREST_BADGE_TEXT,
            "badge_overdue": FOREST_OVERDUE,
        }

    return {
        "bg":            _hex_to_rgb(palette.get("bg_primary"),    FOREST_BG),
        "border":        _hex_to_rgb(palette.get("bg_tertiary"),   FOREST_BORDER),
        "glyph":         _hex_to_rgb(palette.get("text_primary"),  FOREST_TEXT),
        "badge_fill":    _hex_to_rgb(palette.get("accent_brand"),  FOREST_BADGE),
        "badge_text":    _hex_to_rgb(palette.get("bg_primary"),    FOREST_BADGE_TEXT),
        "badge_overdue": _hex_to_rgb(palette.get("accent_overdue"), FOREST_OVERDUE),
    }


def _hex_to_rgb(hex_str: Optional[str], fallback: tuple) -> tuple:
    """'#RRGGBB' → (r,g,b). Возвращает fallback при некорректном или None."""
    if not hex_str or not isinstance(hex_str, str):
        return fallback
    s = hex_str.strip().lstrip("#")
    if len(s) != 6:
        return fallback
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return fallback


def _lerp_rgb(a: tuple, b: tuple, t: float) -> tuple:
    """Линейная интерполяция двух RGB-цветов по каждому каналу. (Legacy — для возможных тем.)"""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_gradient_rounded(
    img: Image.Image,
    top: tuple,
    bottom: tuple,
    radius: int,
) -> None:
    """Legacy: вертикальный градиент top→bottom с rounded clip.

    Forest-рендер этот helper НЕ использует (flat fill через rounded_rectangle).
    Оставлен для возможных будущих тем, где gradient-эффект уместен.
    """
    w, h = img.size
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        grad.paste((*color, 255), (0, y, w, y + 1))

    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)

    img.paste(grad, (0, 0), mask)


def _draw_checkmark(draw: ImageDraw.Draw, x: int, y: int, size: int, color: tuple) -> None:
    """
    Галочка стиля Things 3 — chunky, stroke ≈ size/7 (3px на 28px).

    Точки: левый низ → центр низ → правый верх.
    """
    w = max(2, size // 7)
    pts = [
        (x + int(size * 0.15), y + int(size * 0.55)),
        (x + int(size * 0.40), y + int(size * 0.75)),
        (x + int(size * 0.85), y + int(size * 0.25)),
    ]
    draw.line(pts, fill=(*color, 255), width=w, joint="curve")


def _draw_plus(draw: ImageDraw.Draw, x: int, y: int, size: int, color: tuple) -> None:
    """
    Плюс для empty-state. Stroke ≈ size/7 (3px на 28px).

    Вертикальная и горизонтальная линии пересекаются в центре icon_box.
    """
    w = max(2, size // 7)
    cx = x + size // 2
    cy = y + size // 2
    draw.line(
        [(cx, y + int(size * 0.2)), (cx, y + int(size * 0.8))],
        fill=(*color, 255),
        width=w,
    )
    draw.line(
        [(x + int(size * 0.2), cy), (x + int(size * 0.8), cy)],
        fill=(*color, 255),
        width=w,
    )


def _draw_badge(
    draw: ImageDraw.Draw,
    size: int,
    count: int,
    fill: tuple,
    text: tuple,
    border: tuple,
) -> None:
    """
    Бейдж-таблетка в правом верхнем углу (18x18 на 56px).

    - Размер badge = BADGE_SIZE_FRAC * size (минимум 10px).
    - Forest-preview §5: bg=accent_forest, text=accent_on_forest (cream),
      1.5px border of bg_overlay_square — визуальный pop.
    - Текст: str(min(count, 99)) — не больше двух цифр.
    - Шрифт: дефолтный Pillow bitmap (для frozen-exe safety).
    """
    bsize = max(10, int(size * BADGE_SIZE_FRAC))
    # Смещаем badge чуть за пределы quad-rect (top:-4px, right:-4px per forest-preview CSS)
    bx = size - bsize + 2
    by = -2
    # Границы бейджа (clip к видимой области)
    x0 = max(0, bx)
    y0 = max(0, by)
    x1 = min(size - 1, bx + bsize - 1)
    y1 = min(size - 1, by + bsize - 1)

    # 1.5px border ~ scale factor от size; на 56px → ~2px при supersampling 3x
    border_w = max(1, size // 40)

    draw.ellipse(
        [(x0, y0), (x1, y1)],
        fill=(*fill, 255),
        outline=(*border, 255),
        width=border_w,
    )

    text_str = str(min(count, 99))
    try:
        bbox = draw.textbbox((0, 0), text_str)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw = len(text_str) * bsize // 4
        th = bsize // 2

    tx = x0 + (x1 - x0 - tw) // 2
    ty = y0 + (y1 - y0 - th) // 2
    draw.text((tx, ty), text_str, fill=(*text, 255))
