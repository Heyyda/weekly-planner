"""
Unit-тесты PulseAnimator (Plan 03-05). Covers OVR-05.

Проверяет:
- Жизненный цикл: is_active, start, stop
- Idempotent start (защита от двойного after-цикла)
- Reset на blue при stop() через on_frame(0.0)
- Хотя бы один вызов on_frame после tick
- _compute_pulse_t: wrap, середина цикла, начало, конец
- Константы PULSE_INTERVAL_MS и PULSE_CYCLE_MS
- Отсутствие threading.Timer (PITFALL 2 / D-28)
"""
from unittest.mock import MagicMock

import pytest

from client.ui.pulse import PulseAnimator


def test_initial_state_inactive(headless_tk):
    """До start() анимация неактивна, on_frame не вызывался."""
    cb = MagicMock()
    anim = PulseAnimator(headless_tk, on_frame=cb)
    assert not anim.is_active()
    assert cb.call_count == 0


def test_start_activates(headless_tk):
    """start() устанавливает is_active=True."""
    cb = MagicMock()
    anim = PulseAnimator(headless_tk, on_frame=cb)
    anim.start()
    assert anim.is_active()
    anim.stop()


def test_start_idempotent(headless_tk):
    """Повторный start() не создаёт новый after-цикл (не перезаписывает _after_id)."""
    cb = MagicMock()
    anim = PulseAnimator(headless_tk, on_frame=cb)
    anim.start()
    first_after = anim._after_id
    anim.start()  # noop — уже активен
    assert anim._after_id == first_after  # after_id не перезаписан
    anim.stop()


def test_stop_deactivates(headless_tk):
    """stop() сбрасывает is_active=False и обнуляет _after_id."""
    cb = MagicMock()
    anim = PulseAnimator(headless_tk, on_frame=cb)
    anim.start()
    anim.stop()
    assert not anim.is_active()
    assert anim._after_id is None


def test_stop_resets_to_blue(headless_tk):
    """stop() вызывает on_frame(0.0) для возврата overlay в синий цвет."""
    cb = MagicMock()
    anim = PulseAnimator(headless_tk, on_frame=cb)
    anim.start()
    cb.reset_mock()
    anim.stop()
    # Последний вызов должен быть on_frame(0.0) — reset на blue
    cb.assert_called_with(0.0)


def test_tick_invokes_on_frame_at_least_once(headless_tk):
    """После start() + update() on_frame вызван хотя бы раз."""
    cb = MagicMock()
    anim = PulseAnimator(headless_tk, on_frame=cb)
    anim.start()
    # Процессируем несколько tick'ов через event loop
    for _ in range(3):
        headless_tk.update()
        headless_tk.after(20)
        headless_tk.update_idletasks()
    anim.stop()
    assert cb.call_count >= 1


def test_compute_pulse_t_zero_at_start(headless_tk):
    """_compute_pulse_t(0) == 0.0 — начало цикла синий."""
    anim = PulseAnimator(headless_tk, on_frame=lambda t: None)
    assert anim._compute_pulse_t(0) == 0.0


def test_compute_pulse_t_half_at_mid_cycle(headless_tk):
    """_compute_pulse_t(1250) ≈ 0.5 — пик красного (середина 2500ms цикла)."""
    anim = PulseAnimator(headless_tk, on_frame=lambda t: None)
    t = anim._compute_pulse_t(1250)
    assert abs(t - 0.5) < 0.01


def test_compute_pulse_t_wraps_at_full_cycle(headless_tk):
    """_compute_pulse_t(2500) == 0.0 — конец цикла = начало следующего."""
    anim = PulseAnimator(headless_tk, on_frame=lambda t: None)
    assert anim._compute_pulse_t(2500) == 0.0


def test_compute_pulse_t_wraps_beyond_cycle(headless_tk):
    """_compute_pulse_t(3000) ≈ 0.2 — wrap: 3000 % 2500 = 500; 500/2500 = 0.2."""
    anim = PulseAnimator(headless_tk, on_frame=lambda t: None)
    t = anim._compute_pulse_t(3000)
    assert abs(t - 0.2) < 0.01


def test_pulse_interval_is_16ms_60fps(headless_tk):
    """PULSE_INTERVAL_MS == 16 — гарантия 60fps (D-28)."""
    assert PulseAnimator.PULSE_INTERVAL_MS == 16


def test_pulse_cycle_is_2500ms(headless_tk):
    """PULSE_CYCLE_MS == 2500 — 2.5-секундный цикл per UI-SPEC."""
    assert PulseAnimator.PULSE_CYCLE_MS == 2500


def test_uses_root_after_not_threading_timer(headless_tk):
    """
    PITFALL 2 / D-28 верификация.
    PulseAnimator использует root.after(), НЕ threading.Timer.
    """
    import inspect
    source = inspect.getsource(PulseAnimator)
    assert "threading.Timer" not in source, "threading.Timer запрещён (D-28 / PITFALL 2)"
    assert "root.after" in source, "root.after() должен присутствовать"


def test_stop_on_inactive_is_noop(headless_tk):
    """stop() без предшествующего start() — тихий no-op, on_frame не вызывается."""
    cb = MagicMock()
    anim = PulseAnimator(headless_tk, on_frame=cb)
    anim.stop()  # без start — должно быть тихо
    cb.assert_not_called()
