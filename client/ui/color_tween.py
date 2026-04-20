"""ColorTween — плавная анимация цветов для CustomTkinter виджетов. Forest Phase G.

Заменяет мгновенный `widget.configure(text_color=X)` на RGB-интерполяцию через
`root.after()` шагом ~16ms (≈60fps). Поддерживает отмену superseding-твинов
(новый tween на ту же пару (widget, property) отменяет in-flight), easing
(linear / ease-in / ease-out / ease-in-out cubic) и on_complete-коллбек.

ТОЛЬКО для hex-строк вида `#RRGGBB`. CTk-специальные значения ('transparent',
('gray15','gray86') tuple'ы) не поддерживаются — передавайте уже резолвнутый
hex из текущей палитры ThemeManager.get(...).

Защита от destroy-mid-animation:
- На каждом шаге `winfo_exists()` — если False, tween тихо отменяется.
- Любой `widget.configure` обёрнут в try/except TclError.

Интеграция Phase G:
- TaskWidget._icon_hover / _refresh_icon_visibility → tween text_color
- WeekNavigation arrows → tween text_color на hover
- DaySection plus-btn → tween text_color на hover
- MainWindow title close ✕ → tween text_color + fg_color

Usage:
    ColorTween.tween(
        widget=btn,
        property_name="text_color",
        from_hex="#7A715F",
        to_hex="#5E9E7A",
        duration_ms=150,
        easing="ease-out",
    )
"""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ---------- Easing ----------

def _ease_linear(t: float) -> float:
    return t


def _ease_in_cubic(t: float) -> float:
    return t * t * t


def _ease_out_cubic(t: float) -> float:
    # f(0)=0, f(1)=1, производная на t=1 → 0 (плавное торможение)
    inv = 1.0 - t
    return 1.0 - inv * inv * inv


def _ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4.0 * t * t * t
    inv = -2.0 * t + 2.0
    return 1.0 - (inv * inv * inv) / 2.0


_EASINGS = {
    "linear": _ease_linear,
    "ease-in": _ease_in_cubic,
    "ease-out": _ease_out_cubic,
    "ease-in-out": _ease_in_out_cubic,
}


# ---------- Hex / RGB helpers ----------

def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Парсит '#RRGGBB' → (r, g, b). Raises ValueError на невалидный hex."""
    if not isinstance(hex_str, str):
        raise ValueError(f"hex must be str, got {type(hex_str).__name__}")
    s = hex_str.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"hex must be 6 chars (#RRGGBB), got {hex_str!r}")
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
    except ValueError as exc:
        raise ValueError(f"invalid hex digits in {hex_str!r}") from exc
    return (r, g, b)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """(r, g, b) → '#RRGGBB' с clamp-0..255."""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return f"#{r:02x}{g:02x}{b:02x}"


def interpolate_hex(from_hex: str, to_hex: str, t: float) -> str:
    """Линейная интерполяция двух hex-цветов в RGB-пространстве.

    t=0 → from_hex, t=1 → to_hex. t clamp'нут [0.0, 1.0].
    Возвращает '#rrggbb'. Public — используется в тестах.
    """
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_to_rgb(from_hex)
    r2, g2, b2 = _hex_to_rgb(to_hex)
    r = r1 + (r2 - r1) * t
    g = g1 + (g2 - g1) * t
    b = b1 + (b2 - b1) * t
    return _rgb_to_hex(r, g, b)


# ---------- ColorTween ----------

class ColorTween:
    """Easing-based color animation для tkinter/CustomTkinter виджетов.

    Public API:
        ColorTween.tween(widget, property, from_hex, to_hex, duration_ms, easing, on_complete)
        ColorTween.cancel(widget, property)
        ColorTween.cancel_all(widget)

    Thread-safety: НЕ thread-safe, вызывать только из Tk main loop.
    """

    # Global registry in-flight твинов: {(id(widget), property): _TweenJob}
    _active: dict[tuple[int, str], "_TweenJob"] = {}

    # Frame budget — 16ms ≈ 60fps. Tk after() округляет до кратного timer resolution.
    FRAME_MS = 16

    @classmethod
    def tween(
        cls,
        widget,
        property_name: str,
        from_hex: str,
        to_hex: str,
        duration_ms: int = 150,
        easing: str = "ease-out",
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """Анимировать `widget.configure(**{property_name: interpolated_hex})`.

        Если активен tween на той же (widget, property) — он отменяется и
        заменяется новым (superseding semantics — при быстром hover in/out
        flip не накапливается в очередь).

        Если duration_ms <= 0 — мгновенно применить to_hex + on_complete.
        Если widget уже destroyed — silent no-op.
        """
        if widget is None:
            return

        # Fast path: widget destroyed
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return

        # Fast path: duration<=0 → мгновенно
        if duration_ms <= 0:
            cls._apply(widget, property_name, to_hex)
            if on_complete:
                try:
                    on_complete()
                except Exception as exc:
                    logger.debug("on_complete callback failed: %s", exc)
            return

        # Fast path: from == to → мгновенно (экономит after-вызовы)
        try:
            if from_hex.lower() == to_hex.lower():
                cls._apply(widget, property_name, to_hex)
                if on_complete:
                    try:
                        on_complete()
                    except Exception as exc:
                        logger.debug("on_complete callback failed: %s", exc)
                return
        except AttributeError:
            pass

        # Валидация hex: если невалидно → fallback на мгновенный set to_hex
        try:
            _hex_to_rgb(from_hex)
            _hex_to_rgb(to_hex)
        except ValueError as exc:
            logger.debug("ColorTween: invalid hex, fallback to instant: %s", exc)
            cls._apply(widget, property_name, to_hex)
            if on_complete:
                try:
                    on_complete()
                except Exception as e2:
                    logger.debug("on_complete callback failed: %s", e2)
            return

        easing_fn = _EASINGS.get(easing, _ease_out_cubic)

        # Отменить предыдущий tween на той же паре
        key = (id(widget), property_name)
        cls._cancel_job(key)

        job = _TweenJob(
            widget=widget,
            property_name=property_name,
            from_hex=from_hex,
            to_hex=to_hex,
            duration_ms=duration_ms,
            easing_fn=easing_fn,
            on_complete=on_complete,
            key=key,
        )
        cls._active[key] = job
        job.start()

    @classmethod
    def cancel(cls, widget, property_name: str) -> bool:
        """Отменить in-flight tween на (widget, property). Возвращает True если
        был активный tween."""
        if widget is None:
            return False
        key = (id(widget), property_name)
        return cls._cancel_job(key)

    @classmethod
    def cancel_all(cls, widget) -> None:
        """Отменить все in-flight твины на конкретном widget (для widget.destroy)."""
        if widget is None:
            return
        wid = id(widget)
        keys = [k for k in list(cls._active.keys()) if k[0] == wid]
        for key in keys:
            cls._cancel_job(key)

    # ---- Internal ----

    @classmethod
    def _cancel_job(cls, key: tuple[int, str]) -> bool:
        job = cls._active.pop(key, None)
        if job is None:
            return False
        job.cancel()
        return True

    @classmethod
    def _apply(cls, widget, property_name: str, value: str) -> None:
        """widget.configure(**{property_name: value}) с try/except TclError."""
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            widget.configure(**{property_name: value})
        except (tk.TclError, ValueError) as exc:
            # CTk может выбросить ValueError если виджет не поддерживает свойство.
            logger.debug(
                "ColorTween._apply %s=%s failed: %s", property_name, value, exc,
            )

    @classmethod
    def _on_job_done(cls, key: tuple[int, str]) -> None:
        """Колбек от _TweenJob когда анимация завершилась — очистить registry."""
        cls._active.pop(key, None)


class _TweenJob:
    """Один конкретный tween — хранит after_id, progress, колбек завершения."""

    def __init__(
        self,
        widget,
        property_name: str,
        from_hex: str,
        to_hex: str,
        duration_ms: int,
        easing_fn: Callable[[float], float],
        on_complete: Optional[Callable[[], None]],
        key: tuple[int, str],
    ) -> None:
        self._widget = widget
        self._property = property_name
        self._from = from_hex
        self._to = to_hex
        self._duration = max(1, int(duration_ms))
        self._easing = easing_fn
        self._on_complete = on_complete
        self._key = key
        self._elapsed = 0
        self._after_id: Optional[str] = None
        self._cancelled: bool = False

    def start(self) -> None:
        """Применить from_hex сразу + schedule первый step."""
        ColorTween._apply(self._widget, self._property, self._from)
        self._schedule_next()

    def cancel(self) -> None:
        """Остановить анимацию. Widget остаётся в последнем применённом цвете."""
        self._cancelled = True
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except (tk.TclError, AttributeError):
                pass
            self._after_id = None

    def _schedule_next(self) -> None:
        if self._cancelled:
            return
        try:
            if not self._widget.winfo_exists():
                self._finish(fire_complete=False)
                return
        except tk.TclError:
            self._finish(fire_complete=False)
            return
        try:
            self._after_id = self._widget.after(ColorTween.FRAME_MS, self._step)
        except tk.TclError:
            self._finish(fire_complete=False)

    def _step(self) -> None:
        if self._cancelled:
            return
        self._after_id = None

        # Widget мог быть destroyed между after-вызовами
        try:
            if not self._widget.winfo_exists():
                self._finish(fire_complete=False)
                return
        except tk.TclError:
            self._finish(fire_complete=False)
            return

        self._elapsed += ColorTween.FRAME_MS
        if self._elapsed >= self._duration:
            # Финальный кадр — снап в to_hex чтобы избежать rounding-дрифта
            ColorTween._apply(self._widget, self._property, self._to)
            self._finish(fire_complete=True)
            return

        t_raw = self._elapsed / self._duration
        t_eased = self._easing(t_raw)
        # Clamp для защиты от ease-функций, которые могут выдать <0 или >1
        t_eased = max(0.0, min(1.0, t_eased))
        hex_val = interpolate_hex(self._from, self._to, t_eased)
        ColorTween._apply(self._widget, self._property, hex_val)
        self._schedule_next()

    def _finish(self, fire_complete: bool) -> None:
        """Убрать себя из registry и вызвать on_complete (если не отменён)."""
        self._cancelled = True
        ColorTween._on_job_done(self._key)
        if fire_complete and self._on_complete is not None:
            try:
                self._on_complete()
            except Exception as exc:
                logger.debug("on_complete callback failed: %s", exc)
