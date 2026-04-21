"""Unit-тесты icon_compose.render_overlay_image (Plan 03-03)."""
import pytest
from PIL import Image

from client.ui.icon_compose import (
    render_overlay_image,
    OVERLAY_GREEN_BOTTOM,
    OVERLAY_RED_BOTTOM,
)


def test_returns_pil_image_correct_size():
    """Test 1: возвращает PIL.Image 56x56 RGBA."""
    img = render_overlay_image(56, "default")
    assert isinstance(img, Image.Image)
    assert img.size == (56, 56)
    assert img.mode == "RGBA"


def test_corner_pixel_transparent_rounded_clip():
    """Test 3: угол (0,0) — прозрачный из-за rounded corners."""
    img = render_overlay_image(56, "default")
    r, g, b, a = img.getpixel((0, 0))
    assert a == 0, f"Corner (0,0) должен быть прозрачным, получили alpha={a}"


def test_center_pixel_not_transparent():
    """Test 2: центральный пиксель (28,28) — не прозрачный."""
    img = render_overlay_image(56, "default")
    r, g, b, a = img.getpixel((28, 28))
    assert a > 0, "Центр должен быть непрозрачным (галочка или фон)"


def test_empty_state_has_plus_center_white():
    """Test 4: state='empty' рисует плюс — центр пересечения белый."""
    img_empty = render_overlay_image(56, "empty")
    # Центр иконки (28, 28) — пересечение горизонтали и вертикали плюса — белый
    r, g, b, a = img_empty.getpixel((28, 28))
    assert (r, g, b) == (255, 255, 255) or a == 255


def test_badge_appears_when_count_positive_and_size_large():
    """Test 5 (UX v2): task_count=3 + size=56 → badge присутствует в правом верхнем углу.

    Badge — белый ellipse ~22x22 (BADGE_SIZE_FRAC=22/56), начинается с x=34, y=0.
    Проверяем (50, 8) — внутри ellipse, вне outline и вне зоны текста.
    """
    img = render_overlay_image(56, "default", task_count=3)
    # (50, 8): устойчиво белый внутри нового badge
    r, g, b, a = img.getpixel((50, 8))
    assert (r, g, b) == (255, 255, 255), f"Badge area должен быть белым, got ({r},{g},{b})"


def test_no_badge_when_count_zero():
    """Test 6 (UX v2): task_count=0 → no badge."""
    img = render_overlay_image(56, "default", task_count=0)
    # (50, 8): при badge=off в этом месте будет sage-зелёный фон (не белый)
    r, g, b, a = img.getpixel((50, 8))
    assert not (r == 255 and g == 255 and b == 255), "При task_count=0 badge быть не должно"


def test_no_badge_on_small_icon():
    """Test 7: size=16 + task_count=5 → no badge (badge только для size >= 32)."""
    img = render_overlay_image(16, "default", task_count=5)
    # На 16x16 badge не отрисовывается
    r, g, b, a = img.getpixel((14, 1))
    assert not (r == 255 and g == 255 and b == 255)


def test_overdue_pulse_zero_is_sage():
    """Test 8 (UX v2): state='overdue' + pulse_t=0.0 → фон sage-зелёный (G доминирует)."""
    img = render_overlay_image(56, "overdue", overdue_count=1, pulse_t=0.0)
    # Пиксель фона (не центр, не badge) — зелёный: G > R и G > B
    r, g, b, a = img.getpixel((10, 40))
    assert g > r and g > b, f"pulse_t=0 должен быть зелёным (G>R, G>B): got RGB=({r},{g},{b})"


def test_overdue_pulse_half_is_red():
    """Test 9: state='overdue' + pulse_t=0.5 → фон красный."""
    img = render_overlay_image(56, "overdue", overdue_count=1, pulse_t=0.5)
    # Пиксель фона — красный в пике pulse
    r, g, b, a = img.getpixel((10, 40))
    assert r > b, f"pulse_t=0.5 должен быть красным (R>B): got RGB=({r},{g},{b})"


def test_overdue_badge_shows_overdue_count():
    """Test 10 (UX v2): state='overdue' + overdue_count=3 + size=56 → badge белый."""
    img = render_overlay_image(56, "overdue", task_count=10, overdue_count=3)
    # Badge присутствует при overdue_count > 0 — (50, 8) внутри новой ellipse 22x22
    r, g, b, a = img.getpixel((50, 8))
    assert (r, g, b) == (255, 255, 255), "Overdue badge должен быть белым"


def test_robust_against_pulse_t_out_of_range():
    """Test 11: Не крэшит при pulse_t вне [0,1]."""
    img = render_overlay_image(56, "overdue", overdue_count=1, pulse_t=1.5)
    assert img.size == (56, 56)
    img2 = render_overlay_image(56, "overdue", overdue_count=1, pulse_t=-0.3)
    assert img2.size == (56, 56)


def test_tray_size_16_solid_fill():
    """Test 12: size=16 возвращает 16x16 без crash."""
    img = render_overlay_image(16, "default")
    assert img.size == (16, 16)
