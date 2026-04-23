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

# ---- Цветовые константы ----
# UX v2: sage (бежево-зелёный) default, красный overdue оставлен.
# Old OVERLAY_BLUE_* удалены — больше не используются.

OVERLAY_GREEN_TOP    = (168, 184, 154)   # #A8B89A светлый оливково-бежевый
OVERLAY_GREEN_BOTTOM = (122, 155, 107)   # #7A9B6B глубокий sage-зелёный
OVERLAY_RED_TOP      = (232, 90, 90)     # #E85A5A (overdue top — оставлен)
OVERLAY_RED_BOTTOM   = (192, 53, 53)     # #C03535 (overdue bottom — оставлен)
WHITE                = (255, 255, 255)
BADGE_TEXT           = (20, 40, 15)      # насыщенный тёмно-зелёный (контраст на белом disc)
BADGE_OUTLINE        = (60, 80, 50)      # тёмно-зелёный outline для читаемости на светлых обоях

# Размерные коэффициенты (от стороны иконки)
# UX v3 (quick-260423-o8z): 16/56 ≈ 28.6% — более выраженное скругление,
# согласовано с macOS-подобным языком. Увеличено для устранения визуально
# "квадратных" углов при supersampling 4x.
CORNER_RADIUS_FRAC = 16 / 56
BADGE_SIZE_FRAC    = 22 / 56     # UX v2: было 16/56 — увеличено для читаемости
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
    Supersampling 4x для плавных краёв (v0.6.1, quick-260423-o8z).
    """
    # Supersampling: render at 4x then downscale with LANCZOS for smoother edges (v0.6.1)
    if size >= 24:
        hi = _render_overlay_image_raw(size * 4, state, task_count, overdue_count, pulse_t)
        img = hi.resize((size, size), Image.LANCZOS)
    else:
        img = _render_overlay_image_raw(size, state, task_count, overdue_count, pulse_t)

    # Quick 260423-p0m: alpha threshold — устраняет чёрные полоски по краям на
    # -transparentcolor canvas. Anti-aliased edges после LANCZOS дают полупрозрачные
    # чёрные пиксели (RGB≈0, alpha~128), которые Win32 color-key transparency не
    # считает прозрачными. Threshold гарантирует: каждый пиксель либо 100% opaque,
    # либо 100% transparent — никаких полутонов.
    r, g, b, a = img.split()
    a = a.point(lambda x: 255 if x > 127 else 0)
    return Image.merge("RGBA", (r, g, b, a))


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
        # Triangle-wave: t=0 → sage, t=0.5 → красный, t=1 → sage
        # intensity = 1 при t=0.5 (пик красного), 0 при t=0 и t=1
        intensity = 1.0 - abs(t * 2.0 - 1.0)
        bg_top    = _lerp_rgb(OVERLAY_GREEN_TOP,    OVERLAY_RED_TOP,    intensity)
        bg_bottom = _lerp_rgb(OVERLAY_GREEN_BOTTOM, OVERLAY_RED_BOTTOM, intensity)
    else:
        bg_top    = OVERLAY_GREEN_TOP
        bg_bottom = OVERLAY_GREEN_BOTTOM

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
    Белый ellipse с тёмно-зелёной обводкой в правом верхнем углу + число.

    UX v2:
      - Увеличен размер (22/56 = ~28px на 73px overlay)
      - Добавлен outline (BADGE_OUTLINE) для читаемости на светлых обоях
      - Текст BADGE_TEXT = (20, 40, 15) тёмно-зелёный
      - Попытка использовать truetype шрифт (Arial Bold) с fallback на default
    """
    bsize = max(10, int(size * BADGE_SIZE_FRAC))
    bx = size - bsize
    by = 0

    # Белый disc с тонкой тёмно-зелёной обводкой
    draw.ellipse(
        [(bx, by), (bx + bsize - 1, by + bsize - 1)],
        fill=(*WHITE, 255),
        outline=(*BADGE_OUTLINE, 255),
        width=max(1, bsize // 14),
    )

    text = str(min(count, 99))

    # Шрифт: truetype Arial Bold если доступен, иначе default.font_variant(size=N)
    font = None
    target_font_px = max(8, int(bsize * 0.60))
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arialbd.ttf", size=target_font_px)
    except (IOError, OSError):
        try:
            from PIL import ImageFont
            # Pillow 9.2+: font_variant на default
            font = ImageFont.load_default().font_variant(size=target_font_px)
        except (AttributeError, TypeError):
            font = None  # fallback — draw.text без font

    # Центрирование
    try:
        if font is not None:
            bbox = draw.textbbox((0, 0), text, font=font)
        else:
            bbox = draw.textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # textbbox возвращает с учётом ascender/offset — корректируем
        tx = bx + (bsize - tw) // 2 - bbox[0]
        ty = by + (bsize - th) // 2 - bbox[1]
    except AttributeError:
        tw = len(text) * bsize // 3
        th = bsize // 2
        tx = bx + (bsize - tw) // 2
        ty = by + (bsize - th) // 2

    if font is not None:
        draw.text((tx, ty), text, fill=(*BADGE_TEXT, 255), font=font)
    else:
        draw.text((tx, ty), text, fill=(*BADGE_TEXT, 255))
