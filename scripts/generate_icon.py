"""
scripts/generate_icon.py — Pillow-генератор иконки приложения.

Запуск:  python scripts/generate_icon.py

Создаёт:
  client/assets/icon.ico  (multi-size: 16, 32, 48, 64, 128, 256)
  client/assets/icon.png  (256×256)

Дизайн: минималистичный календарь в палитре темы
  - Фон: крем #F5EFE6 (bg_primary light)
  - Акцент: синий #1E73E8 (accent_brand light)
  - Контур: тёплый тёмный #2B2420 (text_primary light)

Supersampling 3× + LANCZOS — плавные края на всех размерах.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# ---- Палитра (verbatim из client/ui/themes.py light palette) ----
BG = (245, 239, 230, 255)       # #F5EFE6 — bg_primary
ACCENT = (30, 115, 232, 255)    # #1E73E8 — accent_brand
INK = (43, 36, 32, 255)         # #2B2420 — text_primary

# ---- Размеры ICO ----
SIZES = [16, 32, 48, 64, 128, 256]

# ---- Пути ----
ASSETS = Path(__file__).resolve().parent.parent / "client" / "assets"


def render_icon(size: int) -> Image.Image:
    """Рендерит иконку-календарь заданного размера.

    Supersampling 3× + LANCZOS даунскейл — плавные края даже на 16×16.
    Фракционные коэффициенты (0.18, 0.35, 0.85 итд) — масштабируются под любой size.
    """
    hi = size * 3  # supersampling factor
    img = Image.new("RGBA", (hi, hi), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Radius rounded square — та же пропорция что в icon_compose (12/56)
    radius = max(2, int(hi * 12 / 56))

    # Фон: скруглённый квадрат крем
    draw.rounded_rectangle(
        [(0, 0), (hi - 1, hi - 1)],
        radius=radius,
        fill=BG,
    )

    # Верхняя синяя "шапка" календаря (18% высоты, но не меньше radius*2 —
    # иначе нижняя часть "среза скругления" даст invalid rect coords).
    header_h = max(int(hi * 0.18), radius * 2 + 2)
    # Сначала скруглённый прямоугольник с синим фоном (верхние углы наследуют радиус фона)
    draw.rounded_rectangle(
        [(0, 0), (hi - 1, header_h)],
        radius=radius,
        fill=ACCENT,
    )
    # Заливаем низ шапки чтобы нижние углы стали прямыми (только верхние скруглены).
    # Гарантируем y1 > y0 — на малых size radius может быть ≥ header_h без защиты выше.
    fill_top = min(radius, header_h - 1)
    if header_h > fill_top:
        draw.rectangle(
            [(0, fill_top), (hi - 1, header_h)],
            fill=ACCENT,
        )

    # Сетка дней: 4 колонки × 3 ряда точек
    grid_top = int(hi * 0.35)
    grid_bottom = int(hi * 0.85)
    grid_left = int(hi * 0.15)
    grid_right = int(hi * 0.85)
    cols, rows = 4, 3
    col_w = (grid_right - grid_left) // cols
    row_h = (grid_bottom - grid_top) // rows
    dot_r = max(2, hi // 60)

    for r in range(rows):
        for c in range(cols):
            cx = grid_left + c * col_w + col_w // 2
            cy = grid_top + r * row_h + row_h // 2
            if r == 1 and c == 2:
                # "Текущий день" — акцентный круг двойного размера
                big = dot_r * 2
                draw.ellipse(
                    [(cx - big, cy - big), (cx + big, cy + big)],
                    fill=ACCENT,
                )
            else:
                draw.ellipse(
                    [(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)],
                    fill=INK,
                )

    # Даунскейл в целевой размер — LANCZOS для острых краёв
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    # PNG 256×256 — fallback для winotify и документации
    png256 = render_icon(256)
    png256.save(ASSETS / "icon.png", format="PNG")
    print(f"Saved {ASSETS / 'icon.png'}")

    # ICO multi-size: Pillow принимает sizes=[...] при save
    base = render_icon(256)
    base.save(
        ASSETS / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in SIZES],
    )
    print(f"Saved {ASSETS / 'icon.ico'} with sizes={SIZES}")


if __name__ == "__main__":
    main()
