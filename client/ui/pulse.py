"""
PulseAnimator — 60fps driver для overlay pulse animation (OVR-05).

Цикл per UI-SPEC §Overdue:
    2500ms total (PULSE_CYCLE_MS)
    t = 0.0   → normal overlay (начало цикла)
    t = 0.5   → peak pulse intensity (середина)
    t = 1.0   → normal overlay (конец = начало следующего цикла, wrap)

Интерпретация в icon_compose.render_overlay_image (Forest Phase E):
    Плашка — плоская, solid color из палитры. Pulse задаёт только
    акцент badge при overdue (scale или intensity — в будущем).
    Triangle-wave: intensity = 1 - |2t - 1|

Критично: root.after() only (D-28). threading.Timer запрещён (PITFALL 2).
Idempotent start/stop — guard против двойного after-цикла (120fps chaos).
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PulseAnimator:
    """
    60fps pulse driver для overlay overdue-анимации.

    Вызывает on_frame(pulse_t: float) каждые PULSE_INTERVAL_MS мс,
    где pulse_t в [0.0..1.0] — текущая позиция в 2500ms цикле.

    Caller (OverlayManager, Plan 03-10) использует pulse_t для:
        overlay.refresh_image(state="overdue", pulse_t=t)

    Пример использования:
        pulse = PulseAnimator(
            root,
            on_frame=lambda t: overlay.refresh_image(
                state="overdue",
                task_count=task_count,
                overdue_count=overdue_count,
                pulse_t=t,
            )
        )
        # При появлении просроченных задач:
        pulse.start()
        # При очистке всех просрочек:
        pulse.stop()
    """

    PULSE_INTERVAL_MS: int = 16    # ~60fps per D-28
    PULSE_CYCLE_MS: int = 2500     # полный цикл 2.5s per UI-SPEC §Overdue

    def __init__(
        self,
        root,
        on_frame: Callable[[float], None],
    ) -> None:
        """
        Args:
            root: CTk root (или любой Tk widget) — для вызова root.after().
            on_frame: callback(pulse_t: float) — вызывается каждый кадр.
                pulse_t от 0.0 (normal) до 1.0 (normal через пик 0.5 intensity).
        """
        self._root = root
        self._on_frame = on_frame
        self._active: bool = False
        self._after_id: Optional[str] = None
        self._start_time_ms: int = 0

    def is_active(self) -> bool:
        """True если after-цикл запущен."""
        return self._active

    def start(self) -> None:
        """
        Запустить pulse-анимацию.

        Idempotent — повторный вызов при уже активном аниматоре игнорируется.
        Это предотвращает дублирование after-циклов (120fps chaos).
        """
        if self._active:
            logger.debug("PulseAnimator.start: уже активен, игнорируем повторный вызов")
            return
        self._active = True
        self._start_time_ms = self._now_ms()
        self._tick()
        logger.debug("PulseAnimator: запущен (PULSE_INTERVAL_MS=%d, PULSE_CYCLE_MS=%d)",
                     self.PULSE_INTERVAL_MS, self.PULSE_CYCLE_MS)

    def stop(self) -> None:
        """
        Остановить pulse-анимацию и вернуть overlay в синий (pulse_t=0.0).

        Отменяет pending after через after_cancel().
        Вызывает on_frame(0.0) для сброса состояния — нет flicker при остановке.
        Idempotent — вызов без предшествующего start() — no-op.
        """
        if not self._active:
            return
        self._active = False
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception as exc:
                logger.debug("after_cancel не удался (уже выполнен): %s", exc)
            self._after_id = None
        # Сброс в normal state — on_frame(0.0)
        try:
            self._on_frame(0.0)
        except Exception as exc:
            logger.error("on_frame(reset 0.0) ошибка: %s", exc)
        logger.debug("PulseAnimator: остановлен, overlay сброшен в normal state")

    def _tick(self) -> None:
        """
        Один кадр анимации.

        Вычисляет pulse_t → вызывает on_frame → планирует следующий кадр
        через self._root.after(self.PULSE_INTERVAL_MS, self._tick).
        """
        if not self._active:
            return
        elapsed = self._now_ms() - self._start_time_ms
        t = self._compute_pulse_t(elapsed)
        try:
            self._on_frame(t)
        except Exception as exc:
            logger.error("on_frame(pulse_t=%.3f) ошибка — останавливаем анимацию: %s", t, exc)
            self._active = False
            self._after_id = None
            return
        # Планируем следующий кадр (D-28: root.after — единственный верный способ)
        self._after_id = self._root.after(self.PULSE_INTERVAL_MS, self._tick)

    def _compute_pulse_t(self, elapsed_ms: int) -> float:
        """
        Позиция в pulse-цикле как доля [0.0..1.0].

        Формула: (elapsed_ms % PULSE_CYCLE_MS) / PULSE_CYCLE_MS

        Примеры:
            elapsed=0    → 0.0  (normal, начало)
            elapsed=1250 → 0.5  (peak intensity, пик)
            elapsed=2500 → 0.0  (normal, wrap)
            elapsed=3000 → 0.2  (3000 % 2500=500, 500/2500=0.2)

        Args:
            elapsed_ms: миллисекунды с момента start().

        Returns:
            float в [0.0, 1.0) — позиция в цикле.
        """
        cycle_pos = elapsed_ms % self.PULSE_CYCLE_MS
        return cycle_pos / self.PULSE_CYCLE_MS

    @staticmethod
    def _now_ms() -> int:
        """Monotonic timestamp в миллисекундах."""
        return int(time.monotonic() * 1000)
