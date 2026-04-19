"""
OverlayManager — draggable square 56×56 на рабочем столе.

Покрывает:
  OVR-01: overrideredirect + topmost + borderless
  OVR-02: позиция персистится через SettingsStore
  OVR-03: multi-monitor bounds validation (D-19: чистый ctypes EnumDisplayMonitors)
  OVR-04: single-click → on_click callback
  OVR-06: set_always_on_top — toggle с hook для main window

Критические pitfall'ы:
  PITFALL 1: overrideredirect(True) через after(100, ...) — Win11 DWM timing
  PITFALL 4: self._tk_image хранится в instance var (Tkinter GC)
  PITFALL 6: saved position validated against virtual desktop bounds

Decision D-19: multi-monitor через ЧИСТЫЙ ctypes (без pywin32).
pywin32 НЕ в requirements.txt — silent fallback к primary monitor недопустим.
Ref: screeninfo/enumerators/windows.py (github.com/rr-/screeninfo) — пример MONITORENUMPROC.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
from PIL import ImageTk

from client.ui.icon_compose import render_overlay_image
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager

logger = logging.getLogger(__name__)

# DWM attribute (Win11 only) — per 03-RESEARCH Pattern 1
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2

# ==== D-19: pure ctypes multi-monitor support ====
# Win32 structs и callback signature для EnumDisplayMonitors.
# Ref: https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-enumdisplaymonitors


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wt.LONG),
        ("top", wt.LONG),
        ("right", wt.LONG),
        ("bottom", wt.LONG),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wt.DWORD),
    ]


# MONITORENUMPROC = BOOL CALLBACK(HMONITOR, HDC, LPRECT, LPARAM)
_MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wt.BOOL,
    wt.HMONITOR,
    wt.HDC,
    ctypes.POINTER(_RECT),
    wt.LPARAM,
)


class OverlayManager:
    """Квадрат-оверлей на рабочем столе. См. 03-UI-SPEC §Overlay."""

    OVERLAY_SIZE = 56  # px per UI-SPEC
    INIT_DELAY_MS = 100  # PITFALL 1 — критичная задержка для Win11 DWM

    def __init__(
        self,
        root: ctk.CTk,
        settings_store: SettingsStore,
        settings: UISettings,
        theme_manager: ThemeManager,
    ) -> None:
        self._root = root
        self._settings_store = settings_store
        self._settings = settings
        self._theme = theme_manager

        # Колбеки — wire'атся в app.py Plan 03-10
        self.on_click: Optional[Callable[[], None]] = None
        self.on_right_click: Optional[Callable[[], None]] = None
        self.on_top_changed: Optional[Callable[[bool], None]] = None

        # Drag state
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._drag_was_motion = False

        # Pillow image reference (PITFALL 4 — хранить ref, иначе GC удалит)
        self._tk_image: Optional[ImageTk.PhotoImage] = None
        self._canvas_item_id: Optional[int] = None

        # Создание окна
        self._overlay = ctk.CTkToplevel(root)
        self._overlay.withdraw()
        self._overlay.geometry(f"{self.OVERLAY_SIZE}x{self.OVERLAY_SIZE}")

        # Canvas для Pillow image
        self._canvas = tk.Canvas(
            self._overlay,
            width=self.OVERLAY_SIZE,
            height=self.OVERLAY_SIZE,
            highlightthickness=0,
            borderwidth=0,
            bg="#000000",  # временный — прозрачность через transparentcolor
        )
        self._canvas.pack(fill="both", expand=True)

        # PITFALL 1: overrideredirect строго через after(INIT_DELAY_MS, ...)
        self._overlay.after(self.INIT_DELAY_MS, self._init_overlay_style)

    def _init_overlay_style(self) -> None:
        """Вызывается после INIT_DELAY_MS — настраивает borderless+topmost+DWM."""
        self._overlay.overrideredirect(True)
        self._overlay.attributes("-topmost", self._settings.on_top)
        # Прозрачность углов (Win10 fallback для rounded — через transparentcolor canvas bg)
        try:
            self._overlay.attributes("-transparentcolor", "#000000")
        except tk.TclError:
            pass

        # DWM rounded corners (Win11)
        try:
            hwnd = ctypes.windll.user32.GetParent(self._overlay.winfo_id())
            value = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(value), ctypes.sizeof(value),
            )
        except Exception:
            pass  # Win10 fallback — Pillow RGBA углы уже прозрачные

        # Восстановить позицию (валидированную против virtual desktop)
        x, y = self._validate_position(self._settings.overlay_position)
        self._overlay.geometry(f"{self.OVERLAY_SIZE}x{self.OVERLAY_SIZE}+{x}+{y}")

        # Event bindings
        self._canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self._canvas.bind("<B1-Motion>", self._on_drag_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self._canvas.bind("<Button-3>", self._on_right_click_event)

        # Начальная отрисовка
        self.refresh_image(state="default", task_count=0, overdue_count=0)
        self._overlay.deiconify()

        logger.info("OverlayManager initialized at (%d, %d)", x, y)

    # ---- Public API ----

    def get_position(self) -> tuple:
        """Возвращает текущую позицию overlay как (x, y)."""
        if self._overlay.winfo_exists():
            return (self._overlay.winfo_x(), self._overlay.winfo_y())
        return tuple(self._settings.overlay_position)

    def set_position(self, x: int, y: int) -> None:
        """Переместить overlay на (x, y), обновить settings (OVR-02)."""
        x, y = self._validate_position([x, y])
        self._overlay.geometry(f"{self.OVERLAY_SIZE}x{self.OVERLAY_SIZE}+{x}+{y}")
        self._settings.overlay_position = [x, y]

    def set_always_on_top(self, enabled: bool) -> None:
        """OVR-06: применить topmost к overlay + вызвать hook для main window."""
        self._settings.on_top = enabled
        try:
            self._overlay.attributes("-topmost", enabled)
        except tk.TclError:
            pass
        self._settings_store.save(self._settings)
        if self.on_top_changed is not None:
            self.on_top_changed(enabled)

    def refresh_image(self, state: str, task_count: int,
                      overdue_count: int, pulse_t: float = 0.0) -> None:
        """Перерисовать Pillow image → ImageTk → Canvas (PITFALL 4: сохранить ref)."""
        img = render_overlay_image(
            size=self.OVERLAY_SIZE,
            state=state,
            task_count=task_count,
            overdue_count=overdue_count,
            pulse_t=pulse_t,
        )
        # PITFALL 4: сохранить ImageTk.PhotoImage в instance var — иначе GC удалит
        self._tk_image = ImageTk.PhotoImage(img)
        if self._canvas_item_id is None:
            self._canvas_item_id = self._canvas.create_image(
                0, 0, anchor="nw", image=self._tk_image,
            )
        else:
            self._canvas.itemconfig(self._canvas_item_id, image=self._tk_image)

    def show(self) -> None:
        """Показать overlay окно."""
        self._overlay.deiconify()

    def hide(self) -> None:
        """Скрыть overlay окно."""
        self._overlay.withdraw()

    def destroy(self) -> None:
        """Уничтожить overlay окно (teardown)."""
        try:
            self._overlay.destroy()
        except Exception as exc:
            logger.debug("Overlay destroy: %s", exc)

    # ---- Internal drag handlers ----

    def _on_drag_start(self, event) -> None:
        """Запомнить offset при начале drag."""
        self._drag_was_motion = False
        self._drag_offset_x = event.x_root - self._overlay.winfo_x()
        self._drag_offset_y = event.y_root - self._overlay.winfo_y()

    def _on_drag_motion(self, event) -> None:
        """Переместить overlay при движении мыши, clamp к virtual desktop."""
        self._drag_was_motion = True
        new_x = event.x_root - self._drag_offset_x
        new_y = event.y_root - self._drag_offset_y
        new_x, new_y = self._clamp_to_virtual_desktop(new_x, new_y)
        self._overlay.geometry(f"{self.OVERLAY_SIZE}x{self.OVERLAY_SIZE}+{new_x}+{new_y}")

    def _on_drag_end(self, event) -> None:
        """Сохранить позицию после drag. Если нет motion — вызвать on_click."""
        if self._drag_was_motion:
            # Сохранить позицию через SettingsStore (OVR-02)
            x, y = self._overlay.winfo_x(), self._overlay.winfo_y()
            self._settings.overlay_position = [x, y]
            self._settings_store.save(self._settings)
            logger.debug("Overlay position saved: (%d, %d)", x, y)
        else:
            # Клик без motion → on_click callback (OVR-04)
            if self.on_click is not None:
                try:
                    self.on_click()
                except Exception as exc:
                    logger.error("on_click handler failed: %s", exc)
        self._drag_was_motion = False

    def _on_right_click_event(self, event) -> None:
        """Правый клик — вызвать on_right_click callback если установлен."""
        if self.on_right_click is not None:
            try:
                self.on_right_click()
            except Exception as exc:
                logger.error("on_right_click handler failed: %s", exc)

    # ---- Multi-monitor support (OVR-03, D-19: pure ctypes) ----

    def _get_virtual_desktop_bounds(self) -> tuple:
        """Возвращает (left, top, right, bottom) virtual desktop (union всех мониторов).

        D-19: использует ПУРНЫЙ ctypes.windll.user32.EnumDisplayMonitors — БЕЗ pywin32.
        Ref: screeninfo/enumerators/windows.py (github.com/rr-/screeninfo)

        Fallback на primary screen через Tk при любой ошибке ctypes
        (не-Windows / нестандартная среда).
        """
        rects: list = []

        def _callback(hmonitor, hdc, lprect, lparam):
            # Вариант A: прочитать прямо из lprect (RECT указатель)
            try:
                r = lprect.contents
                rects.append((int(r.left), int(r.top), int(r.right), int(r.bottom)))
            except Exception:
                # Вариант B (надёжнее): GetMonitorInfoW для work area + full
                try:
                    mi = _MONITORINFO()
                    mi.cbSize = ctypes.sizeof(_MONITORINFO)
                    if ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi)):
                        r = mi.rcMonitor
                        rects.append((int(r.left), int(r.top), int(r.right), int(r.bottom)))
                except Exception:
                    pass
            return True  # продолжить enumeration

        try:
            proc = _MONITORENUMPROC(_callback)
            ok = ctypes.windll.user32.EnumDisplayMonitors(
                wt.HDC(0),  # NULL — все мониторы
                None,       # NULL clip — без ограничения
                proc,
                wt.LPARAM(0),
            )
            if ok and rects:
                left = min(r[0] for r in rects)
                top = min(r[1] for r in rects)
                right = max(r[2] for r in rects)
                bottom = max(r[3] for r in rects)
                return (left, top, right, bottom)
        except (OSError, AttributeError) as exc:
            logger.debug("ctypes EnumDisplayMonitors failed: %s", exc)

        # Fallback: primary screen через Tk (не-Windows / ошибка ctypes)
        try:
            return (
                0, 0,
                self._root.winfo_screenwidth(),
                self._root.winfo_screenheight(),
            )
        except tk.TclError:
            return (0, 0, 1920, 1080)  # последний fallback

    def _clamp_to_virtual_desktop(self, x: int, y: int) -> tuple:
        """Ограничить координаты в пределах virtual desktop."""
        left, top, right, bottom = self._get_virtual_desktop_bounds()
        x = max(left, min(x, right - self.OVERLAY_SIZE))
        y = max(top, min(y, bottom - self.OVERLAY_SIZE))
        return (x, y)

    def _default_visible_position(self) -> tuple:
        """Правый край, верх primary monitor — Things 3-style дефолт."""
        try:
            sw = self._overlay.winfo_screenwidth()
        except tk.TclError:
            sw = 1920
        x = max(0, sw - self.OVERLAY_SIZE - 24)
        y = 80
        return (x, y)

    def _validate_position(self, pos) -> tuple:
        """PITFALL 6: валидация сохранённой позиции против virtual desktop.

        Если позиция вне видимой области — fallback к visible default (правый край).
        """
        try:
            x, y = int(pos[0]), int(pos[1])
        except (TypeError, ValueError, IndexError):
            return self._default_visible_position()
        left, top, right, bottom = self._get_virtual_desktop_bounds()
        if x < left - self.OVERLAY_SIZE + 10 or x > right - 10:
            logger.warning("Saved overlay_x=%d off-screen → visible default", x)
            return self._default_visible_position()
        if y < top - self.OVERLAY_SIZE + 10 or y > bottom - 10:
            logger.warning("Saved overlay_y=%d off-screen → visible default", y)
            return self._default_visible_position()
        return (x, y)
