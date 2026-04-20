"""
Pillow-композитор иконки overlay/tray.

Используется:
  - Plan 03-04 OverlayManager (статичная отрисовка 56x56 canvas image)
  - Plan 03-05 PulseAnimator (60fps перерисовка с pulse_t 0..1)
  - Plan 03-07 TrayManager (16/32px tray icon)

Все цвета — verbatim из UI-SPEC §Color Palette + §Brand Identity.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

# ---- Цветовые константы (UI-SPEC verbatim) ----

OVERLAY_BLUE_TOP    = (78, 161, 255)   # #4EA1FF (gradient top)
OVERLAY_BLUE_BOTTOM = (30, 115, 232)   # #1E73E8 (gradient bottom / tray solid)
OVERLAY_RED_TOP     = (232, 90, 90)    # #E85A5A (overdue top)
OVERLAY_RED_BOTTOM  = (192, 53, 53)    # #C03535 (overdue bottom)
WHITE               = (255, 255, 255)
BADGE_TEXT          = (30, 30, 30)     # тёмный текст badge

# Размерные коэффициенты (от стороны иконки)
CORNER_RADIUS_FRAC = 12 / 56     # 21.4% ≈ UI-SPEC radius 12px на 56px
BADGE_SIZE_FRAC    = 16 / 56     # 28.6% — 16px badge на 56px
ICON_SIZE_FRAC     = 0.55        # 55% → галочка/плюс вписаны в центр


# ---- Public API ----

def render_overlay_image(
    size: int,
    state: str = "default",
    task_count: int = 0,
    overdue_count: int = 0,
    pulse_t: float = 0.0,
) -> Image.Image:
    """
    Создать PIL.Image (RGBA) — rounded-square + иконка + badge.
    Supersampling 3x для плавных краёв (v0.4.0).
    """
    # Supersampling: render at 3x then downscale with LANCZOS for smooth anti-aliasing
    if size >= 24:
        hi = _render_overlay_image_raw(size * 3, state, task_count, overdue_count, pulse_t)
        return hi.resize((size, size), Image.LANCZOS)
    return _render_overlay_image_raw(size, state, task_count, overdue_count, pulse_t)


def _render_overlay_image_raw(
    size: int,
    state: str = "default",
    task_count: int = 0,
    overdue_count: int = 0,
    pulse_t: float = 0.0,
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
        # Периодичность: 1.5 → 0.5, 2.3 → 0.3
        t = t - int(t)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ---- Цвет фона ----
    if state == "overdue":
        # Triangle-wave: t=0 → синий, t=0.5 → красный, t=1 → синий
        # intensity = 1 при t=0.5 (пик красного), 0 при t=0 и t=1
        intensity = 1.0 - abs(t * 2.0 - 1.0)
        bg_top    = _lerp_rgb(OVERLAY_BLUE_TOP,    OVERLAY_RED_TOP,    intensity)
        bg_bottom = _lerp_rgb(OVERLAY_BLUE_BOTTOM, OVERLAY_RED_BOTTOM, intensity)
    else:
        bg_top    = OVERLAY_BLUE_TOP
        bg_bottom = OVERLAY_BLUE_BOTTOM

    # ---- Rounded square с фоном ----
    radius = max(2, int(size * CORNER_RADIUS_FRAC))
    if size >= 32:
        # Градиент top→bottom через pixel-by-pixel fill + rounded mask
        _draw_gradient_rounded(img, bg_top, bg_bottom, radius)
    else:
        # Solid для tray 16px — градиент при таком масштабе не читается
        draw.rounded_rectangle(
            [(0, 0), (size - 1, size - 1)],
            radius=radius,
            fill=(*bg_bottom, 255),
        )

    # ---- Центральная иконка ----
    draw = ImageDraw.Draw(img)  # обновить draw после paste в gradient
    icon_size = int(size * ICON_SIZE_FRAC)
    ix = (size - icon_size) // 2
    iy = (size - icon_size) // 2
    if state == "empty":
        _draw_plus(draw, ix, iy, icon_size)
    else:
        _draw_checkmark(draw, ix, iy, icon_size)

    # ---- Badge ----
    badge_count = overdue_count if state == "overdue" else task_count
    if badge_count > 0 and size >= 32:
        _draw_badge(draw, size, badge_count)

    return img


# ---- Internal helpers ----

def _lerp_rgb(a: tuple, b: tuple, t: float) -> tuple:
    """Линейная интерполяция двух RGB-цветов по каждому каналу."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_gradient_rounded(
    img: Image.Image,
    top: tuple,
    bottom: tuple,
    radius: int,
) -> None:
    """
    Нанести вертикальный градиент top→bottom на img, клипнув по rounded rect.

    Алгоритм:
        1. Создать gradient-слой (RGBA) заливкой построчно.
        2. Создать маску (L) с rounded_rectangle=255, остальное 0.
        3. paste(gradient, mask) — прозрачные углы сохраняются.
    """
    w, h = img.size
    # Gradient layer
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        grad.paste((*color, 255), (0, y, w, y + 1))

    # Rounded rectangle mask
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)

    # Apply
    img.paste(grad, (0, 0), mask)


def _draw_checkmark(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Белая галочка в стиле Things 3 — chunky, stroke ≈ size/7 (3px на 28px).

    Точки: левый низ → центр низ → правый верх.
    """
    w = max(2, size // 7)
    pts = [
        (x + int(size * 0.15), y + int(size * 0.55)),
        (x + int(size * 0.40), y + int(size * 0.75)),
        (x + int(size * 0.85), y + int(size * 0.25)),
    ]
    draw.line(pts, fill=(*WHITE, 255), width=w, joint="curve")


def _draw_plus(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Белый плюс для empty-state. Stroke ≈ size/7 (3px на 28px).

    Вертикальная и горизонтальная линии пересекаются в центре icon_box.
    """
    w = max(2, size // 7)
    cx = x + size // 2
    cy = y + size // 2
    draw.line(
        [(cx, y + int(size * 0.2)), (cx, y + int(size * 0.8))],
        fill=(*WHITE, 255),
        width=w,
    )
    draw.line(
        [(x + int(size * 0.2), cy), (x + int(size * 0.8), cy)],
        fill=(*WHITE, 255),
        width=w,
    )


def _draw_badge(draw: ImageDraw.Draw, size: int, count: int) -> None:
    """
    Белый ellipse (круг) 16x16 в правом верхнем углу с тёмным числом.

    - Размер badge = BADGE_SIZE_FRAC * size (минимум 8px).
    - Текст: str(min(count, 99)) — не больше двух цифр.
    - Шрифт: дефолтный Pillow bitmap (без truetype — избежать проблем в frozen .exe).
    """
    bsize = max(8, int(size * BADGE_SIZE_FRAC))
    bx = size - bsize
    by = 0
    draw.ellipse([(bx, by), (bx + bsize - 1, by + bsize - 1)], fill=(*WHITE, 255))

    text = str(min(count, 99))
    try:
        # Pillow 9.2+ поддерживает textbbox для точного центрирования
        bbox = draw.textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        # Старые версии Pillow — грубая оценка
        tw = len(text) * bsize // 4
        th = bsize // 2

    tx = bx + (bsize - tw) // 2
    ty = by + (bsize - th) // 2
    draw.text((tx, ty), text, fill=(*BADGE_TEXT, 255))
