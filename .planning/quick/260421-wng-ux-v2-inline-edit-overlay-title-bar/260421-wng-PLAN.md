---
phase: quick-260421-wng
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/inline_edit_panel.py
  - client/ui/main_window.py
  - client/ui/week_navigation.py
  - client/ui/icon_compose.py
autonomous: true
requirements:
  - UX-V2-01
  - UX-V2-02
  - UX-V2-03
  - UX-V2-04

must_haves:
  truths:
    - "Клик по задаче открывает редактирование прямо в окне (не всплывающий dialog)"
    - "Стрелки недели и кнопка 'Сегодня' окрашены в цвет темы (не синие CTk default)"
    - "Overlay на обоях — бежево-зелёный (sage), badge с цифрой читаем на светлых обоях"
    - "Главное окно не имеет native title-bar Windows: кастомный header с закрытием, drag по header, resize-grip в углу"
  artifacts:
    - path: "client/ui/inline_edit_panel.py"
      provides: "InlineEditPanel — CTkFrame с slide-down анимацией и формой редактирования"
      contains: "class InlineEditPanel"
    - path: "client/ui/main_window.py"
      provides: "_on_task_edit через inline panel + borderless + custom header + resize grip"
      contains: "_open_edit_panel"
    - path: "client/ui/week_navigation.py"
      provides: "Кнопки prev/next/today в цвет темы (transparent + text_primary)"
      contains: "fg_color=\"transparent\""
    - path: "client/ui/icon_compose.py"
      provides: "Sage palette для overlay + увеличенный badge с outline"
      contains: "OVERLAY_GREEN_TOP"
  key_links:
    - from: "client/ui/main_window.py::_on_task_edit"
      to: "client/ui/inline_edit_panel.py::InlineEditPanel"
      via: "_open_edit_panel(task) вместо EditDialog(...)"
      pattern: "InlineEditPanel\\("
    - from: "client/ui/main_window.py::_apply_borderless"
      to: "self._window.overrideredirect"
      via: "after(INIT_DELAY_MS, ...) — PITFALL 1 Win11 DWM"
      pattern: "overrideredirect\\(True\\)"
    - from: "client/ui/week_navigation.py::_build"
      to: "self._theme.get('text_primary')"
      via: "text_color=... на трёх кнопках (prev, next, today)"
      pattern: "text_color=self\\._theme\\.get"
    - from: "client/ui/icon_compose.py::render_overlay_image"
      to: "OVERLAY_GREEN_TOP/BOTTOM"
      via: "замена OVERLAY_BLUE_* в default-state ветке"
      pattern: "OVERLAY_GREEN_TOP"
---

<objective>
UX v2 — 4 независимые правки интерфейса:

1. **InlineEditPanel** — редактирование задачи inline внутри главного окна (не popup dialog).
2. **Стрелки недели и "Сегодня"** — в цвет темы (transparent + text_primary), не дефолтные синие CTk.
3. **Overlay** — бежево-зелёный (sage) вместо синего, увеличенный badge с outline для читаемости на светлых обоях.
4. **Custom title bar** — убрать native Windows title bar у главного окна, добавить кастомный header и resize-grip.

**Purpose:** Приблизить UI к минималистичному, "своему" виду — без чужеродных CTk-синих кнопок и грубого системного title bar. Inline-редактирование ускоряет цикл capture→edit (соответствует core value: speed-of-capture).

**Output:**
- Новый файл `client/ui/inline_edit_panel.py`
- Изменения в `main_window.py`, `week_navigation.py`, `icon_compose.py`
- 4 atomic commits (по одному на задачу, на русском)
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@client/ui/edit_dialog.py
@client/ui/main_window.py
@client/ui/week_navigation.py
@client/ui/overlay.py
@client/ui/icon_compose.py
@client/utils/tray.py
@client/ui/themes.py
@client/core/models.py

<interfaces>
<!-- Ключевые типы/API, которые executor будет использовать. Чтобы не искать по кодбазе. -->

From `client/core/models.py`:
```python
@dataclass
class Task:
    id: str
    user_id: str
    text: str
    day: str                           # ISO date "YYYY-MM-DD"
    time_deadline: Optional[str] = None
    done: bool = False
    position: int = 0
    created_at: str = ""
    updated_at: str = ""
    deleted_at: Optional[str] = None
```

From `client/ui/themes.py`:
```python
# Все темы имеют эти ключи:
# bg_primary, bg_secondary, bg_tertiary
# text_primary, text_secondary, text_tertiary
# accent_brand, accent_brand_light, accent_done, accent_overdue
# shadow_card, border_window

FONTS["h1"]      # (Segoe UI Variable, 16, bold)
FONTS["body"]    # (Segoe UI Variable, 13, normal)
FONTS["body_m"]  # (Segoe UI Variable, 13, bold)
FONTS["caption"] # (Segoe UI Variable, 11, normal)
FONTS["mono"]    # (Cascadia Mono, 12, normal)

class ThemeManager:
    def get(self, key: str) -> str
    def subscribe(self, callback: Callable[[dict[str,str]], None]) -> None
```

From `client/ui/edit_dialog.py` — функции, которые переиспользуются в InlineEditPanel (скопировать как методы):
```python
DAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES_RU = ['', 'янв', ...]
HH_OPTIONS = [f"{h:02d}" for h in range(24)]     # 00..23
MM_OPTIONS = [f"{m:02d}" for m in range(0, 60, 5)]

# Методы для копирования (как self-методы нового класса):
_current_time_parts(self) -> tuple[str, str, bool]
_build_day_options(self) -> list[str]
_get_current_day_label(self) -> str
_day_label_to_iso(self, label: str) -> str
_update_save_state(self), _save(self), _cancel(self), _delete(self)
```

From `client/ui/main_window.py`:
```python
class MainWindow:
    MIN_SIZE = (320, 320)
    DEFAULT_SIZE = (460, 600)
    FADE_DURATION_MS = 150
    FADE_STEPS = 8

    # Уже существуют:
    self._window: ctk.CTkToplevel
    self._root_frame: ctk.CTkFrame   # border_width=1, border_color=border_window
    self._scroll: ctk.CTkScrollableFrame
    self._week_nav: WeekNavigation
    self._theme: ThemeManager
    self._storage: LocalStorage

    # Заменяемый метод:
    def _on_task_edit(self, task_id: str) -> None  # сейчас создаёт EditDialog
    def _on_edit_save(self, updated: Task) -> None  # остаётся, вызывается из InlineEditPanel
    def _on_task_delete(self, task_id: str) -> None  # остаётся
```

From `client/ui/overlay.py`:
```python
# OVERLAY_SIZE = 73px (главный overlay на обоях)
# render_overlay_image(size, state, task_count, overdue_count, pulse_t)
#   state: "default" | "empty" | "overdue"
```

From `client/utils/tray.py`:
```python
TRAY_ICON_SIZE = 64
# Использует ТОТ ЖЕ render_overlay_image — значит смена палитры повлияет и на tray icon.
# User одобрил: tray тоже станет бежево-зелёным — это ок.
```

From `client/ui/icon_compose.py` (текущие константы):
```python
OVERLAY_BLUE_TOP    = (78, 161, 255)   # ЗАМЕНИТЬ на OVERLAY_GREEN_TOP
OVERLAY_BLUE_BOTTOM = (30, 115, 232)   # ЗАМЕНИТЬ на OVERLAY_GREEN_BOTTOM
OVERLAY_RED_TOP     = (232, 90, 90)    # ОСТАВИТЬ (overdue)
OVERLAY_RED_BOTTOM  = (192, 53, 53)    # ОСТАВИТЬ (overdue)
BADGE_SIZE_FRAC    = 16 / 56     # ЗАМЕНИТЬ на 22/56
BADGE_TEXT         = (30, 30, 30) # ЗАМЕНИТЬ на (20, 40, 15)
```
</interfaces>

<code_patterns>
<!-- Паттерны проекта, которым нужно следовать -->

**Error handling (проектный стандарт):**
- `except tk.TclError: pass` — для виджетных операций которые могут упасть при destroy
- Bare `except Exception: pass` или `logger.debug(...)` — для graceful degradation
- Не raise'ить наружу из UI-методов — вернуть `None`/`False` молча

**Тематизация:**
- Subscribe pattern: `self._theme.subscribe(self._apply_theme)` — виджеты обновляются live при смене темы
- Цвета всегда через `self._theme.get("ключ")` — никаких hex-хардкодов
- `_apply_theme(palette: dict)` метод получает новую палитру и `.configure(...)` обновляет виджеты

**Анимация:**
- `self._window.after(delay_ms, callback, *args)` — Tkinter scheduling
- Ease-out quadratic как в `main_window._fade`: `eased = 1.0 - (1.0 - progress) ** 2`
- Не использовать `time.sleep()` в UI thread — это заморозит окно

**Russian commits (обязательно):**
- `feat(inline-edit): заменить EditDialog popup на inline slide-down панель`
- `style(week-nav): кнопки навигации в цвет темы (transparent + text_primary)`
- `feat(overlay): sage-зелёный градиент + увеличенный badge с outline`
- `feat(window): кастомный title-bar с drag + resize-grip вместо native Windows frame`
- Перед `git push` — **СПРОСИТЬ пользователя**. Сейчас только local commits.
</code_patterns>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: InlineEditPanel — inline-редактирование задачи вместо EditDialog popup</name>
  <files>client/ui/inline_edit_panel.py, client/ui/main_window.py</files>

  <behavior>
    - Клик по задаче → панель slide-down сверху scroll area, ширина = окно - 24px, высота ~280px
    - Esc закрывает без сохранения
    - Ctrl+Enter сохраняет
    - Кнопки "Удалить"/"Отмена"/"Сохранить" работают как в EditDialog
    - Поля: textbox задачи, Day dropdown ("Сегодня"/"Завтра"/"Послезавтра"/"Пн 14 апр"...), Time (HH:MM через 2 OptionMenu + "✕" clear), Done checkbox
    - При resize окна — панель адаптирует ширину (relwidth=0.94 через place)
    - Повторное открытие на другой задаче: предыдущая панель закрывается, новая открывается
    - EditDialog НЕ удаляется из codebase (остаётся на случай будущих сценариев)
  </behavior>

  <action>
**Шаг 1.** Создать НОВЫЙ файл `client/ui/inline_edit_panel.py`:

```python
"""InlineEditPanel — inline-редактирование задачи. UX v2.

Заменяет EditDialog popup: панель появляется slide-down внутри главного окна,
поверх scroll area через place(). Быстрее и органичнее чем modal Toplevel.
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

DAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES_RU = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
                  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
HH_OPTIONS = [f"{h:02d}" for h in range(24)]
MM_OPTIONS = [f"{m:02d}" for m in range(0, 60, 5)]


class InlineEditPanel:
    """Slide-down панель редактирования задачи, живёт внутри main_window._root_frame."""

    PANEL_HEIGHT = 280
    ANIM_DURATION_MS = 150
    ANIM_STEPS = 8

    def __init__(
        self,
        parent_frame: ctk.CTkFrame,
        root_window: ctk.CTkToplevel,
        task: Task,
        theme_manager: ThemeManager,
        on_save: Callable[[Task], None],
        on_delete: Callable[[str], None],
        on_close: Callable[[], None],
    ) -> None:
        self._parent = parent_frame
        self._root_window = root_window
        self._task = task
        self._theme = theme_manager
        self._on_save = on_save
        self._on_delete = on_delete
        self._on_close = on_close
        self._closed = False
        self._animating = False

        self._text_box: Optional[ctk.CTkTextbox] = None
        self._day_var: Optional[ctk.StringVar] = None
        self._hh_var: Optional[ctk.StringVar] = None
        self._mm_var: Optional[ctk.StringVar] = None
        self._time_enabled_var: Optional[tk.BooleanVar] = None
        self._done_var: Optional[tk.BooleanVar] = None
        self._save_btn: Optional[ctk.CTkButton] = None
        self._hh_menu: Optional[ctk.CTkOptionMenu] = None
        self._mm_menu: Optional[ctk.CTkOptionMenu] = None

        bg = self._theme.get("bg_secondary")
        border = self._theme.get("border_window")

        self._frame = ctk.CTkFrame(
            parent_frame,
            fg_color=bg,
            corner_radius=12,
            border_width=1,
            border_color=border,
            height=self.PANEL_HEIGHT,
        )
        self._build_ui()

        # Start hidden above the viewport: y = -PANEL_HEIGHT
        self._frame.place(
            relx=0.5, rely=0, x=0, y=-self.PANEL_HEIGHT,
            anchor="n", relwidth=0.94,
        )
        self._frame.lift()

        # Bindings
        self._frame.bind("<Escape>", lambda e: self._cancel())
        self._root_window.bind("<Escape>", lambda e: self._cancel(), add="+")
        self._root_window.bind("<Control-Return>", lambda e: self._save(), add="+")

        # Начать анимацию slide-down
        self._slide(target_y=12, step=0)

        # Focus textbox
        try:
            if self._text_box:
                self._text_box.focus_set()
        except tk.TclError:
            pass
        self._update_save_state()

    def _build_ui(self) -> None:
        bg = self._theme.get("bg_secondary")
        text_primary = self._theme.get("text_primary")
        text_sec = self._theme.get("text_secondary")

        content = ctk.CTkFrame(self._frame, fg_color=bg, corner_radius=0)
        content.pack(fill="both", expand=True, padx=14, pady=12)

        # Задача (textbox)
        ctk.CTkLabel(
            content, text="Задача", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")
        self._text_box = ctk.CTkTextbox(
            content, height=54, wrap="word", corner_radius=10, font=FONTS["body"],
        )
        self._text_box.pack(fill="x", pady=(2, 10))
        self._text_box.insert("1.0", self._task.text)
        self._text_box.bind("<KeyRelease>", lambda e: self._update_save_state())

        # Day + Time row
        grid = ctk.CTkFrame(content, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 10))

        day_col = ctk.CTkFrame(grid, fg_color="transparent")
        day_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            day_col, text="День", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")
        self._day_var = ctk.StringVar(value=self._get_current_day_label())
        ctk.CTkOptionMenu(
            day_col, values=self._build_day_options(), variable=self._day_var,
            corner_radius=10, font=FONTS["body"], height=30,
        ).pack(fill="x", pady=(2, 0))

        time_col = ctk.CTkFrame(grid, fg_color="transparent")
        time_col.pack(side="right", padx=(12, 0))
        ctk.CTkLabel(
            time_col, text="Время", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")
        time_row = ctk.CTkFrame(time_col, fg_color="transparent")
        time_row.pack(fill="x", pady=(2, 0))

        cur_hh, cur_mm, has_time = self._current_time_parts()
        self._time_enabled_var = tk.BooleanVar(value=has_time)
        self._hh_var = ctk.StringVar(value=cur_hh if has_time else "09")
        self._mm_var = ctk.StringVar(value=cur_mm if has_time else "00")

        self._hh_menu = ctk.CTkOptionMenu(
            time_row, values=HH_OPTIONS, variable=self._hh_var,
            width=60, corner_radius=10, font=FONTS["mono"], height=30,
            command=lambda *_: self._on_time_enabled_implicit(True),
        )
        self._hh_menu.pack(side="left")
        ctk.CTkLabel(time_row, text=":", font=FONTS["mono"],
                     text_color=text_primary).pack(side="left", padx=3)
        self._mm_menu = ctk.CTkOptionMenu(
            time_row, values=MM_OPTIONS, variable=self._mm_var,
            width=60, corner_radius=10, font=FONTS["mono"], height=30,
            command=lambda *_: self._on_time_enabled_implicit(True),
        )
        self._mm_menu.pack(side="left")
        ctk.CTkButton(
            time_row, text="✕", width=26, height=30, corner_radius=10,
            fg_color="transparent", border_width=1, text_color=text_sec,
            hover_color=self._theme.get("bg_tertiary"),
            command=self._clear_time,
        ).pack(side="left", padx=(6, 0))
        if not has_time:
            self._set_time_menus_dim(True)

        # Done checkbox
        self._done_var = tk.BooleanVar(value=self._task.done)
        ctk.CTkCheckBox(
            content, text="Выполнено", variable=self._done_var,
            command=self._update_save_state, font=FONTS["body"],
            corner_radius=4, checkbox_width=20, checkbox_height=20,
        ).pack(anchor="w", pady=(0, 10))

        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")
        ctk.CTkButton(
            btn_frame, text="Удалить",
            fg_color="transparent", border_width=1,
            border_color=self._theme.get("accent_overdue"),
            text_color=self._theme.get("accent_overdue"),
            hover_color=self._theme.get("bg_tertiary"),
            width=90, height=30, corner_radius=10,
            font=FONTS["body"], command=self._delete,
        ).pack(side="left")
        ctk.CTkButton(
            btn_frame, text="Отмена",
            fg_color="transparent", border_width=1,
            text_color=text_primary,
            hover_color=self._theme.get("bg_tertiary"),
            width=80, height=30, corner_radius=10,
            font=FONTS["body"], command=self._cancel,
        ).pack(side="right", padx=(6, 0))
        self._save_btn = ctk.CTkButton(
            btn_frame, text="Сохранить", width=110, height=30, corner_radius=10,
            font=FONTS["body_m"], command=self._save,
        )
        self._save_btn.pack(side="right")

    # ---- Animation ----

    def _slide(self, target_y: int, step: int,
               on_complete: Optional[Callable[[], None]] = None) -> None:
        """Slide панели по y от current к target с ease-out quadratic."""
        self._animating = True
        current_step = step + 1
        progress = current_step / self.ANIM_STEPS
        eased = 1.0 - (1.0 - progress) ** 2

        # Интерполяция от start к target
        if not hasattr(self, "_anim_start_y"):
            # первый кадр — захватить start
            try:
                self._anim_start_y = self._frame.place_info().get("y", -self.PANEL_HEIGHT)
                self._anim_start_y = int(self._anim_start_y)
            except (tk.TclError, ValueError, TypeError):
                self._anim_start_y = -self.PANEL_HEIGHT
            self._anim_target_y = target_y

        start = self._anim_start_y
        end = self._anim_target_y
        y = int(start + (end - start) * eased)
        try:
            self._frame.place_configure(y=y)
        except tk.TclError:
            self._animating = False
            return

        if current_step >= self.ANIM_STEPS:
            try:
                self._frame.place_configure(y=end)
            except tk.TclError:
                pass
            self._animating = False
            # Очистить анимационное состояние для возможного повторного использования
            if hasattr(self, "_anim_start_y"):
                del self._anim_start_y
            if hasattr(self, "_anim_target_y"):
                del self._anim_target_y
            if on_complete:
                try:
                    on_complete()
                except Exception as exc:
                    logger.debug("slide on_complete: %s", exc)
            return

        delay_ms = max(1, int(self.ANIM_DURATION_MS / self.ANIM_STEPS))
        try:
            self._frame.after(delay_ms, self._slide, target_y, current_step, on_complete)
        except tk.TclError:
            self._animating = False

    # ---- Time helpers (скопировано из EditDialog) ----

    def _current_time_parts(self) -> tuple[str, str, bool]:
        from datetime import datetime
        td = self._task.time_deadline
        if not td:
            return ("09", "00", False)
        try:
            if "T" in td:
                dt = datetime.fromisoformat(td.replace("Z", "+00:00"))
                return (dt.strftime("%H"), dt.strftime("%M"), True)
            parts = td.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return (f"{int(parts[0]):02d}", f"{int(parts[1]):02d}", True)
        except (ValueError, TypeError):
            pass
        return ("09", "00", False)

    def _clear_time(self) -> None:
        if self._time_enabled_var is not None:
            self._time_enabled_var.set(False)
        self._set_time_menus_dim(True)

    def _on_time_enabled_implicit(self, enabled: bool) -> None:
        if self._time_enabled_var is not None:
            self._time_enabled_var.set(enabled)
        self._set_time_menus_dim(not enabled)

    def _set_time_menus_dim(self, dim: bool) -> None:
        color = self._theme.get("text_tertiary") if dim else self._theme.get("text_primary")
        for menu in (self._hh_menu, self._mm_menu):
            try:
                if menu is not None:
                    menu.configure(text_color=color)
            except (tk.TclError, AttributeError):
                pass

    # ---- Day helpers (скопировано из EditDialog) ----

    def _build_day_options(self) -> list[str]:
        today = date.today()
        opts = ["Сегодня", "Завтра", "Послезавтра"]
        monday = today - timedelta(days=today.weekday())
        for i in range(7):
            d = monday + timedelta(days=i)
            if d in (today, today + timedelta(1), today + timedelta(2)):
                continue
            opts.append(f"{DAY_NAMES_RU[i]} {d.day} {MONTH_NAMES_RU[d.month]}")
        return opts

    def _get_current_day_label(self) -> str:
        today = date.today()
        try:
            d = date.fromisoformat(self._task.day)
        except (ValueError, TypeError):
            return "Сегодня"
        if d == today:
            return "Сегодня"
        if d == today + timedelta(1):
            return "Завтра"
        if d == today + timedelta(2):
            return "Послезавтра"
        return f"{DAY_NAMES_RU[d.weekday()]} {d.day} {MONTH_NAMES_RU[d.month]}"

    def _day_label_to_iso(self, label: str) -> str:
        today = date.today()
        if label == "Сегодня":
            return today.isoformat()
        if label == "Завтра":
            return (today + timedelta(1)).isoformat()
        if label == "Послезавтра":
            return (today + timedelta(2)).isoformat()
        parts = label.split()
        if len(parts) >= 2:
            try:
                day_num = int(parts[1])
                monday = today - timedelta(days=today.weekday())
                for i in range(7):
                    d = monday + timedelta(days=i)
                    if d.day == day_num:
                        return d.isoformat()
            except (ValueError, IndexError):
                pass
        return self._task.day

    # ---- Validation / save ----

    def _update_save_state(self) -> None:
        if self._save_btn is None or not self._save_btn.winfo_exists():
            return
        ok = False
        if self._text_box and self._text_box.winfo_exists():
            ok = bool(self._text_box.get("1.0", "end-1c").strip())
        try:
            self._save_btn.configure(state="normal" if ok else "disabled")
        except tk.TclError:
            pass

    def _save(self) -> None:
        if self._closed:
            return
        text = self._text_box.get("1.0", "end-1c").strip() if self._text_box else ""
        if not text:
            return
        day_iso = self._day_label_to_iso(self._day_var.get()) if self._day_var else self._task.day
        done = self._done_var.get() if self._done_var else self._task.done
        time_val: Optional[str] = None
        if self._time_enabled_var and self._time_enabled_var.get():
            hh = self._hh_var.get() if self._hh_var else "09"
            mm = self._mm_var.get() if self._mm_var else "00"
            time_val = f"{hh}:{mm}"

        updated = Task(
            id=self._task.id, user_id=self._task.user_id, text=text,
            day=day_iso, time_deadline=time_val, done=done,
            position=self._task.position,
            created_at=self._task.created_at, updated_at=self._task.updated_at,
            deleted_at=self._task.deleted_at,
        )
        self._close_with_callback(lambda: self._on_save(updated))

    def _cancel(self) -> None:
        if self._closed:
            return
        self._close_with_callback(None)

    def _delete(self) -> None:
        if self._closed:
            return
        task_id = self._task.id
        self._close_with_callback(lambda: self._on_delete(task_id))

    def _close_with_callback(self, cb: Optional[Callable[[], None]]) -> None:
        if self._closed:
            return
        self._closed = True

        def finalize() -> None:
            try:
                self._frame.destroy()
            except tk.TclError:
                pass
            try:
                self._on_close()
            except Exception as exc:
                logger.debug("on_close: %s", exc)
            if cb is not None:
                try:
                    cb()
                except Exception as exc:
                    logger.error("close callback failed: %s", exc)

        # Slide-up анимация
        if hasattr(self, "_anim_start_y"):
            del self._anim_start_y
        if hasattr(self, "_anim_target_y"):
            del self._anim_target_y
        self._slide(target_y=-self.PANEL_HEIGHT, step=0, on_complete=finalize)

    def destroy(self) -> None:
        """Немедленное уничтожение без анимации (для replace случая)."""
        self._closed = True
        try:
            self._frame.destroy()
        except tk.TclError:
            pass
```

**Шаг 2.** Изменить `client/ui/main_window.py`:

1. Заменить импорт (оставить EditDialog на будущее, но импортировать новый класс):
```python
from client.ui.edit_dialog import EditDialog  # оставить — на будущее
from client.ui.inline_edit_panel import InlineEditPanel  # NEW
```

2. Добавить атрибут в `__init__` (рядом с `self._week_nav`):
```python
self._edit_panel: Optional[InlineEditPanel] = None
```

3. Заменить метод `_on_task_edit`:
```python
def _on_task_edit(self, task_id: str) -> None:
    if self._storage is None:
        return
    task = self._storage.get_task(task_id)
    if task is None:
        return
    self._open_edit_panel(task)

def _open_edit_panel(self, task: Task) -> None:
    """Открыть InlineEditPanel для задачи — закрыть предыдущую если есть."""
    if self._edit_panel is not None:
        try:
            self._edit_panel.destroy()
        except Exception:
            pass
        self._edit_panel = None
    self._edit_panel = InlineEditPanel(
        parent_frame=self._root_frame,
        root_window=self._window,
        task=task,
        theme_manager=self._theme,
        on_save=self._on_edit_save,
        on_delete=self._on_task_delete,
        on_close=self._close_edit_panel,
    )

def _close_edit_panel(self) -> None:
    """Callback от InlineEditPanel после закрытия — очистить ref."""
    self._edit_panel = None
```

**НЕ удаляй** класс `EditDialog` или файл `edit_dialog.py`. Оставь импорт — он может понадобиться.

**Pitfall 1:** Панель через `place(relx=0.5, rely=0, y=..., anchor="n", relwidth=0.94)` поверх pack'нутых виджетов — работает, но нужен `lift()` чтобы быть над scroll area.
**Pitfall 2:** `place_info()["y"]` возвращает строку — привести к int через `int(...)`.
**Pitfall 3:** Esc bind на root_window добавляется через `add="+"` — чтобы не перезатирать существующие bindings (Ctrl+Space quick_capture и пр.).
**Pitfall 4:** Не забудь очищать `_anim_start_y`/`_anim_target_y` между анимациями, иначе slide-up использует старые значения slide-down.
**Pitfall 5:** EditDialog оставить в codebase — НЕ удалять файл, НЕ удалять импорт (depreca­ted, но не dead code).
  </action>

  <verify>
    <automated>cd "S:\Проекты\ежедневник" && python -c "from client.ui.inline_edit_panel import InlineEditPanel; print('import ok')" && python -m pytest client/tests/test_main_window.py -x -q 2>&1 | tail -30</automated>
  </verify>

  <done>
  - `client/ui/inline_edit_panel.py` существует, класс `InlineEditPanel` импортируется
  - `main_window.py::_on_task_edit` вызывает `_open_edit_panel(task)`, НЕ `EditDialog(...)`
  - `EditDialog` и `edit_dialog.py` не удалены (проверить `ls client/ui/edit_dialog.py`)
  - `python -c "from client.ui.inline_edit_panel import InlineEditPanel"` работает
  - `python -c "from client.ui.main_window import MainWindow"` работает
  - test_main_window.py — те же failing тесты что и до (новых не добавилось); если есть тест для `_on_task_edit` проверяющий EditDialog — обновить на InlineEditPanel mock
  - Ручная проверка (после merge всех 4 задач): запуск приложения, клик по задаче → панель выезжает сверху scroll area с anim ~150мс; Esc/Cancel/Save закрывают панель
  - Commit: `feat(inline-edit): заменить EditDialog popup на inline slide-down панель`
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Стрелки недели и кнопка "Сегодня" в цвет темы (не синие default)</name>
  <files>client/ui/week_navigation.py</files>

  <behavior>
    - Кнопки `◀`, `▶`, `Сегодня` больше не отрисовываются как CTk-дефолтные синие
    - Стрелки: transparent fg, text_primary цвет текста, bg_secondary hover, border_width=0
    - "Сегодня": transparent fg, text_primary, bg_secondary hover, border_width=1 с border_color=text_tertiary (едва заметный outline)
    - При смене темы через ThemeManager — цвета всех 3 кнопок обновляются
  </behavior>

  <action>
В `client/ui/week_navigation.py::_build` заменить создание трёх кнопок:

**Было (строки ~160-175):**
```python
self._prev_btn = ctk.CTkButton(
    row, text="◀", width=self.ARROW_WIDTH, command=self.prev_week,
)
self._prev_btn.pack(side="left", padx=4, pady=4)
# ...
self._today_btn = ctk.CTkButton(
    row, text="Сегодня", width=self.TODAY_BTN_WIDTH, command=self.today,
)
# ...
self._next_btn = ctk.CTkButton(
    row, text="▶", width=self.ARROW_WIDTH, command=self.next_week,
)
self._next_btn.pack(side="right", padx=4, pady=4)
```

**Стало:**
```python
text_primary = self._theme.get("text_primary")
text_tertiary = self._theme.get("text_tertiary")
hover_bg = self._theme.get("bg_secondary")

self._prev_btn = ctk.CTkButton(
    row, text="◀", width=self.ARROW_WIDTH, command=self.prev_week,
    fg_color="transparent",
    text_color=text_primary,
    hover_color=hover_bg,
    border_width=0,
    corner_radius=10,
)
self._prev_btn.pack(side="left", padx=4, pady=4)

self._header_label = ctk.CTkLabel(row, text="Неделя —", font=FONTS["h1"])
self._header_label.pack(side="left", expand=True)

self._today_btn = ctk.CTkButton(
    row, text="Сегодня", width=self.TODAY_BTN_WIDTH, command=self.today,
    fg_color="transparent",
    text_color=text_primary,
    hover_color=hover_bg,
    border_width=1,
    border_color=text_tertiary,
    corner_radius=10,
)
# Не pack по default — виден только для не-current

self._next_btn = ctk.CTkButton(
    row, text="▶", width=self.ARROW_WIDTH, command=self.next_week,
    fg_color="transparent",
    text_color=text_primary,
    hover_color=hover_bg,
    border_width=0,
    corner_radius=10,
)
self._next_btn.pack(side="right", padx=4, pady=4)
```

**Обновить `_apply_theme`** (строки ~257-266) — добавить цвета кнопок:

```python
def _apply_theme(self, palette: dict) -> None:
    if self._destroyed:
        return
    try:
        if self._header_frame and self._header_frame.winfo_exists():
            self._header_frame.configure(fg_color=palette.get("bg_primary"))
        if self._archive_banner and self._archive_banner.winfo_exists():
            self._archive_banner.configure(fg_color=palette.get("bg_tertiary"))
        # NEW: обновить цвета кнопок
        text_primary = palette.get("text_primary", "#2B2420")
        text_tertiary = palette.get("text_tertiary", "#9A8F7D")
        hover_bg = palette.get("bg_secondary", "#EDE6D9")
        for btn in (self._prev_btn, self._next_btn):
            if btn and btn.winfo_exists():
                btn.configure(text_color=text_primary, hover_color=hover_bg)
        if self._today_btn and self._today_btn.winfo_exists():
            self._today_btn.configure(
                text_color=text_primary,
                hover_color=hover_bg,
                border_color=text_tertiary,
            )
    except tk.TclError:
        pass
```

**Pitfall 1:** CTkButton с `fg_color="transparent"` делает hover'ом именно `hover_color` — проверено в существующем коде (см. edit_dialog.py строка 218 где эта же схема используется для кнопок "Отмена"/"Удалить").
**Pitfall 2:** `bg_secondary` чуть светлее/темнее `bg_primary` — даёт видимый hover, но не кричащий. Не использовать `accent_brand` — это вернёт синий.
**Pitfall 3:** Стрелки `◀`/`▶` — юникод-символы; при `text_color="text_primary"` (тёмный на светлой теме) будут хорошо видны. На тёмной теме `text_primary` — светлый, тоже ок.
  </action>

  <verify>
    <automated>cd "S:\Проекты\ежедневник" && python -c "from client.ui.week_navigation import WeekNavigation; print('import ok')" && python -m pytest client/tests/test_week_navigation.py -x -q 2>&1 | tail -20</automated>
  </verify>

  <done>
  - `week_navigation.py::_build` содержит `fg_color="transparent"` для всех трёх кнопок (grep'ается)
  - `week_navigation.py::_apply_theme` обновляет `text_color`/`hover_color` для `_prev_btn`/`_next_btn`/`_today_btn`
  - `python -c "from client.ui.week_navigation import WeekNavigation"` работает
  - test_week_navigation.py — не упали новые тесты
  - Ручная проверка (после всех задач): открыть главное окно — стрелки и "Сегодня" в цвет темы, НЕ синие CTk default; hover работает (mild bg shift); смена темы через tray → цвета меняются
  - Commit: `style(week-nav): кнопки навигации в цвет темы (transparent + text_primary)`
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Overlay бежево-зелёный (sage) + увеличенный badge с outline</name>
  <files>client/ui/icon_compose.py</files>

  <behavior>
    - Default-state overlay (на обоях и в tray) — бежево-зелёный градиент вместо синего
    - Overdue-state (pulse красный) — НЕ изменился (OVERLAY_RED_* остались)
    - Badge с числом задач: больше (22/56 вместо 16/56), тёмно-зелёный текст (20,40,15), тонкий outline по периметру для контраста на светлых обоях
    - Badge по-прежнему отображается только при size >= 32 (то есть НЕ на tray 16px но ДА на tray 64px и overlay 73px)
    - Shape icon (галочка/плюс) не меняется
  </behavior>

  <action>
В `client/ui/icon_compose.py` изменения:

**Шаг 1.** Заменить цветовые константы (строки ~17-22):

```python
# ---- Цветовые константы ----
# v2: sage (бежево-зелёный) default, красный overdue оставлен
OVERLAY_GREEN_TOP    = (168, 184, 154)   # #A8B89A светлый оливково-бежевый
OVERLAY_GREEN_BOTTOM = (122, 155, 107)   # #7A9B6B глубокий sage-зелёный
OVERLAY_RED_TOP      = (232, 90, 90)     # #E85A5A (overdue top — оставлен)
OVERLAY_RED_BOTTOM   = (192, 53, 53)     # #C03535 (overdue bottom — оставлен)
WHITE                = (255, 255, 255)
BADGE_TEXT           = (20, 40, 15)      # насыщенный тёмно-зелёный (гармония с sage, контраст на белом disc)
BADGE_OUTLINE        = (60, 80, 50)      # тёмно-зелёный outline для читаемости на светлых обоях
```

**Удалить** старые константы `OVERLAY_BLUE_TOP` и `OVERLAY_BLUE_BOTTOM` — они больше не используются.

**Шаг 2.** Изменить размерный коэффициент badge (строка ~26):

```python
CORNER_RADIUS_FRAC = 12 / 56
BADGE_SIZE_FRAC    = 22 / 56     # v2: было 16/56 — увеличено для читаемости
ICON_SIZE_FRAC     = 0.55
```

**Шаг 3.** Заменить ссылки на `OVERLAY_BLUE_*` в `_render_overlay_image_raw` (строки ~73-81):

**Было:**
```python
if state == "overdue":
    intensity = 1.0 - abs(t * 2.0 - 1.0)
    bg_top    = _lerp_rgb(OVERLAY_BLUE_TOP,    OVERLAY_RED_TOP,    intensity)
    bg_bottom = _lerp_rgb(OVERLAY_BLUE_BOTTOM, OVERLAY_RED_BOTTOM, intensity)
else:
    bg_top    = OVERLAY_BLUE_TOP
    bg_bottom = OVERLAY_BLUE_BOTTOM
```

**Стало:**
```python
if state == "overdue":
    # Triangle-wave: t=0 → sage, t=0.5 → красный, t=1 → sage
    intensity = 1.0 - abs(t * 2.0 - 1.0)
    bg_top    = _lerp_rgb(OVERLAY_GREEN_TOP,    OVERLAY_RED_TOP,    intensity)
    bg_bottom = _lerp_rgb(OVERLAY_GREEN_BOTTOM, OVERLAY_RED_BOTTOM, intensity)
else:
    bg_top    = OVERLAY_GREEN_TOP
    bg_bottom = OVERLAY_GREEN_BOTTOM
```

**Шаг 4.** Улучшить `_draw_badge` (строки ~188-214):

```python
def _draw_badge(draw: ImageDraw.Draw, size: int, count: int) -> None:
    """
    Белый ellipse с тёмно-зелёной обводкой в правом верхнем углу + число.
    v2 changes:
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
```

**Pitfall 1 (CRITICAL):** `render_overlay_image` используется в 3 местах:
- `overlay.py` (73px на обоях) — badge отрисуется
- `tray.py` (TRAY_ICON_SIZE=64) — badge отрисуется (>= 32)
- Внутренне при tray 16px — badge НЕ отрисуется (size >= 32 проверка уже есть в `_render_overlay_image_raw` строка ~108). **Оставить эту проверку — не менять**.

**Pitfall 2:** Supersampling 3x в `render_overlay_image` (строки 44-46) делает всё 3x → при 73px рендерится 219px → down-scale LANCZOS. Значит `_draw_badge` получает `size=219` и `bsize = int(219 * 22/56) = ~86px` — что вполне ок для truetype шрифта. Font target = `86 * 0.60 = ~51px` — нормальный шрифт, чётко downscale'нется.

**Pitfall 3:** `arialbd.ttf` на Windows находится в `C:\Windows\Fonts\` — Pillow обычно находит по имени через system fonts. В frozen .exe тоже работает (system fonts не bundl'ятся). Но если `IOError`/`OSError` — graceful fallback на `ImageFont.load_default().font_variant(size=N)`.

**Pitfall 4:** `font_variant(size=N)` доступен в Pillow 9.2+ (проверить — в requirements.txt указано `Pillow>=10.0.0`, значит точно доступен).

**Pitfall 5:** NOT ouput проверка — Pillow `draw.text(pos, ..., font=font)` — если font=None, используется default bitmap font, что лучше чем падать. Обе ветки поддерживаются.

**Pitfall 6:** `tray.py` использует `render_overlay_image(size=64, state="default", ...)` — badge отрисуется (64 >= 32). Это ок, user принял что tray тоже станет зелёным.
  </action>

  <verify>
    <automated>cd "S:\Проекты\ежедневник" && python -c "from client.ui.icon_compose import render_overlay_image, OVERLAY_GREEN_TOP, OVERLAY_GREEN_BOTTOM; img = render_overlay_image(size=73, state='default', task_count=5, overdue_count=0); assert img.size == (73, 73); print('default ok'); img2 = render_overlay_image(size=73, state='overdue', task_count=3, overdue_count=3, pulse_t=0.5); assert img2.size == (73, 73); print('overdue ok'); img3 = render_overlay_image(size=16, state='default', task_count=0, overdue_count=0); assert img3.size == (16, 16); print('tiny ok')" && python -m pytest client/tests/test_icon_compose.py client/tests/test_overlay.py -x -q 2>&1 | tail -20</automated>
  </verify>

  <done>
  - `icon_compose.py` содержит `OVERLAY_GREEN_TOP = (168, 184, 154)` и `OVERLAY_GREEN_BOTTOM = (122, 155, 107)` (grep'ается)
  - `OVERLAY_BLUE_TOP`/`OVERLAY_BLUE_BOTTOM` больше нет в файле (grep возвращает 0 совпадений)
  - `BADGE_SIZE_FRAC = 22 / 56`
  - `BADGE_TEXT = (20, 40, 15)`
  - `_draw_badge` содержит outline (проверить "outline=" в функции)
  - `render_overlay_image(size=73, state='default', ...)` возвращает Image 73x73 (автоматический тест выше)
  - test_icon_compose.py — если тесты проверяют конкретные hex/RGB значения — обновить ожидания под зелёный; если тесты проверяют "not None"/"size correct" — пройдут без изменений
  - Ручная проверка (после всех задач): запуск приложения → overlay на обоях бежево-зелёный; tray icon зелёная; добавить 3 задачи → badge с "3" чётко читаем
  - Commit: `feat(overlay): sage-зелёный градиент + увеличенный badge с outline`
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Убрать native title bar главного окна (custom header + resize grip)</name>
  <files>client/ui/main_window.py</files>

  <behavior>
    - Главное окно больше не имеет native Windows title-bar (синяя/тёмная полоса сверху с "Личный Еженедельник" и кнопкой X)
    - Вместо native есть кастомный header (30px высотой, bg_secondary) с:
      - Опциональный label "Личный Еженедельник" слева (FONTS["caption"], text_tertiary)
      - Кнопка "✕" справа → `self.hide()` (fade-out в tray, не destroy)
    - Header работает как drag-region — зажать и тянуть перемещает окно
    - Resize-grip "⤡" в правом нижнем углу `_root_frame` — drag меняет размер окна
    - Окно присутствует в Windows taskbar (через WS_EX_APPWINDOW) — не исчезает с Alt+Tab
    - Border_width=1 на `_root_frame` уже есть (из предыдущей правки) — трогать не нужно
    - `attributes("-alpha", ...)` (fade show/hide) продолжает работать с overrideredirect=True; если нет — fallback
  </behavior>

  <action>
В `client/ui/main_window.py` — многоэтапные изменения:

**Шаг 1.** В `__init__` после `self._window.protocol("WM_DELETE_WINDOW", self._on_close)` (строка 93) добавить вызов apply borderless с delay (PITFALL 1 — Win11 DWM):

```python
# UX v2: убрать native title bar через overrideredirect + кастомный header
# PITFALL 1 (Win11 DWM): overrideredirect строго через after(100, ...)
self._window.after(100, self._apply_borderless)
```

**Шаг 2.** Добавить импорт ctypes в начало файла (если ещё нет):
```python
import ctypes
```

**Шаг 3.** Добавить новые методы в класс `MainWindow`:

```python
def _apply_borderless(self) -> None:
    """UX v2: убрать native title bar. Сохранить taskbar через WS_EX_APPWINDOW.
    PITFALL 1 (Win11 DWM): overrideredirect должен вызываться после after(100, ...).
    """
    try:
        self._window.overrideredirect(True)
    except tk.TclError as exc:
        logger.debug("overrideredirect failed: %s", exc)
        return

    # WS_EX_APPWINDOW — сохранить окно в taskbar и Alt+Tab
    try:
        hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new = (current & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)
        # Re-apply window style: withdraw/deiconify цикл — но только если окно видимо
        # (иначе будет flash при каждом старте)
        if self._window.winfo_viewable():
            self._window.withdraw()
            self._window.deiconify()
    except Exception as exc:
        logger.debug("WS_EX_APPWINDOW failed: %s", exc)

def _build_custom_header(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
    """UX v2: кастомный header с drag-to-move + кнопкой закрытия.
    Заменяет native title bar."""
    bg = self._theme.get("bg_secondary")
    text_sec = self._theme.get("text_secondary")
    text_ter = self._theme.get("text_tertiary")

    header = ctk.CTkFrame(parent, fg_color=bg, height=30, corner_radius=0)
    header.pack(fill="x", side="top")
    header.pack_propagate(False)

    # Label слева (опциональный)
    title_lbl = ctk.CTkLabel(
        header, text="Личный Еженедельник",
        font=FONTS["caption"], text_color=text_ter, anchor="w",
    )
    title_lbl.pack(side="left", padx=10)

    # Кнопка закрытия ✕
    close_btn = ctk.CTkLabel(
        header, text="✕", font=FONTS["body_m"],
        text_color=text_sec, cursor="hand2", width=30, height=30,
    )
    close_btn.pack(side="right", padx=4)
    close_btn.bind("<Button-1>", lambda e: self.hide())
    close_btn.bind(
        "<Enter>",
        lambda e: close_btn.configure(text_color=self._theme.get("accent_overdue")),
    )
    close_btn.bind(
        "<Leave>",
        lambda e: close_btn.configure(text_color=self._theme.get("text_secondary")),
    )

    # Drag-to-move: bind на header И title_lbl
    for widget in (header, title_lbl):
        widget.bind("<ButtonPress-1>", self._on_header_drag_start)
        widget.bind("<B1-Motion>", self._on_header_drag_motion)

    self._header_frame = header
    self._header_title_lbl = title_lbl
    self._header_close_btn = close_btn
    return header

def _on_header_drag_start(self, event) -> None:
    """Запомнить offset курсора относительно окна в момент press."""
    try:
        self._drag_offset_x = event.x_root - self._window.winfo_x()
        self._drag_offset_y = event.y_root - self._window.winfo_y()
    except tk.TclError:
        pass

def _on_header_drag_motion(self, event) -> None:
    """Перемещение окна следом за курсором."""
    try:
        new_x = event.x_root - self._drag_offset_x
        new_y = event.y_root - self._drag_offset_y
        self._window.geometry(f"+{new_x}+{new_y}")
    except tk.TclError:
        pass

def _build_resize_grip(self, parent: ctk.CTkFrame) -> None:
    """UX v2: resize-grip ⤡ в правом нижнем углу. Заменяет native resize-border."""
    text_ter = self._theme.get("text_tertiary")
    grip = ctk.CTkLabel(
        parent, text="⤡", font=FONTS["body_m"],
        text_color=text_ter, cursor="bottom_right_corner",
        width=16, height=16,
    )
    grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)
    grip.lift()
    grip.bind("<ButtonPress-1>", self._on_grip_drag_start)
    grip.bind("<B1-Motion>", self._on_grip_drag_motion)
    self._resize_grip = grip

def _on_grip_drag_start(self, event) -> None:
    """Запомнить начальный размер и позицию курсора."""
    try:
        self._resize_start_w = self._window.winfo_width()
        self._resize_start_h = self._window.winfo_height()
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
    except tk.TclError:
        pass

def _on_grip_drag_motion(self, event) -> None:
    """Изменить размер окна, соблюдая MIN_SIZE."""
    try:
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        new_w = max(self.MIN_SIZE[0], self._resize_start_w + dx)
        new_h = max(self.MIN_SIZE[1], self._resize_start_h + dy)
        x = self._window.winfo_x()
        y = self._window.winfo_y()
        self._window.geometry(f"{new_w}x{new_h}+{x}+{y}")
    except tk.TclError:
        pass
```

**Шаг 4.** Интегрировать custom header в `_build_ui` (метод ~строка 269). **Вставить custom header СРАЗУ после создания `_root_frame`, ПЕРЕД `WeekNavigation`:**

```python
def _build_ui(self) -> None:
    self._root_frame = ctk.CTkFrame(
        self._window,
        corner_radius=0,
        border_width=1,
        border_color=self._theme.get("border_window"),
    )
    self._root_frame.pack(fill="both", expand=True)

    # UX v2: кастомный header вместо native title bar
    self._build_custom_header(self._root_frame)

    self._week_nav = WeekNavigation(
        self._root_frame, self._window, self._theme,
        on_week_changed=self._on_week_changed,
        on_archive_changed=self._on_archive_changed,
    )
    self._week_nav.pack(fill="x", side="top")

    self._scroll = ctk.CTkScrollableFrame(self._root_frame)
    self._scroll.pack(fill="both", expand=True, padx=8, pady=4)

    self._undo_toast = UndoToastManager(
        self._root_frame, self._root, self._theme,
    )

    self._drag_controller = DragController(
        self._root, self._theme,
        on_task_moved=self._on_task_moved,
    )

    # UX v2: resize grip в правом нижнем углу
    self._build_resize_grip(self._root_frame)

    self._rebuild_day_sections()
```

**Шаг 5.** Добавить атрибуты в `__init__` (рядом с `self._day_sections`):

```python
self._header_frame: Optional[ctk.CTkFrame] = None
self._header_title_lbl: Optional[ctk.CTkLabel] = None
self._header_close_btn: Optional[ctk.CTkLabel] = None
self._resize_grip: Optional[ctk.CTkLabel] = None
self._drag_offset_x = 0
self._drag_offset_y = 0
self._resize_start_w = 0
self._resize_start_h = 0
self._resize_start_x = 0
self._resize_start_y = 0
```

**Шаг 6.** Обновить `_apply_theme` — добавить перекраску header и grip:

```python
def _apply_theme(self, palette: dict) -> None:
    bg = palette.get("bg_primary", "#F5EFE6")
    border = palette.get("border_window", "#8A7D6B")
    bg_sec = palette.get("bg_secondary", "#EDE6D9")
    text_sec = palette.get("text_secondary", "#6B5E4E")
    text_ter = palette.get("text_tertiary", "#9A8F7D")
    try:
        self._window.configure(fg_color=bg)
        if hasattr(self, "_root_frame"):
            self._root_frame.configure(fg_color=bg, border_color=border)
        # NEW: header + grip
        if self._header_frame and self._header_frame.winfo_exists():
            self._header_frame.configure(fg_color=bg_sec)
        if self._header_title_lbl and self._header_title_lbl.winfo_exists():
            self._header_title_lbl.configure(text_color=text_ter)
        if self._header_close_btn and self._header_close_btn.winfo_exists():
            self._header_close_btn.configure(text_color=text_sec)
        if self._resize_grip and self._resize_grip.winfo_exists():
            self._resize_grip.configure(text_color=text_ter)
    except tk.TclError:
        pass
```

**Pitfall 1 (CRITICAL):** `attributes("-alpha", ...)` + `overrideredirect(True)` — проверить что работает. Если нет (fade не видно) → пользователь увидит мгновенное показ/скрытие, но приложение будет работать. **НЕ откатывать** — просто задокументировать в SUMMARY. Если fade всё-таки видно визуально — идеально.

**Pitfall 2:** `withdraw()/deiconify()` цикл в `_apply_borderless` применяется только если окно уже видимо. На первом старте окно не видимо (`_window.withdraw()` в `__init__` строка 74) — значит flash не случится при старте. На show() после первого `_apply_borderless` уже применён → деиконификация произойдёт один раз.

**Pitfall 3:** Snap Win11 (drag-to-edges для auto-maximize) НЕ работает с overrideredirect — user знает и принял.

**Pitfall 4:** Кнопка "−" минимизировать НЕ добавляется — iconify() может странно работать с overrideredirect. Одна кнопка "✕" (= hide в tray) — проще и надёжнее. User'у напоминаем через tooltip: приложение живёт в tray.

**Pitfall 5:** Resize grip в правом нижнем углу через `place(relx=1.0, rely=1.0, anchor="se")` — значок находится над scroll area или над DaySection контентом, НЕ перекрывает пользовательские клики (16x16 px в самом углу). Если всё же перекрывает важный элемент (unlikely) — можно сдвинуть на x=-8 y=-8.

**Pitfall 6:** `ctypes.windll.user32.GetParent(hwnd)` — на некоторых Win версиях может вернуть 0 (no parent). Обёрнуто в try/except Exception, так что graceful.

**Pitfall 7:** `_on_configure` уже существует (строки 528-537) — он сохраняет size/position окна. Drag-to-move генерирует много `<Configure>` events → можно получить много save calls → проверить что `self._on_configure` только обновляет `self._settings`, но НЕ пишет файл на каждый event (файл пишется только в `_save_window_state` на close). Grep: `_save_window_state` вызывается только в `_on_close` — значит save на drag не происходит, только memory update. OK.

**Pitfall 8:** header `pack` до WeekNavigation'а — значит порядок виджетов: header (30px), week_nav (40px), scroll (fill). Grip через `place` не конфликтует с pack (они используют разные geometry managers).

**Pitfall 9 (fallback):** Если overrideredirect ломает что-то фатально (например fade crash, main window невидим, не открывается) — **откат в SUMMARY**: оставить `_apply_borderless` но закомментировать строку `self._window.overrideredirect(True)` и custom header/grip — native bar вернётся, но остальные 3 изменения из Task 1/2/3 работают. Это acceptable degradation, не повод revert всего.
  </action>

  <verify>
    <automated>cd "S:\Проекты\ежедневник" && python -c "from client.ui.main_window import MainWindow; print('import ok')" && python -m pytest client/tests/test_main_window.py -x -q 2>&1 | tail -30</automated>
  </verify>

  <done>
  - `main_window.py` содержит `_apply_borderless` метод (grep: "def _apply_borderless")
  - `main_window.py` содержит `_build_custom_header` метод
  - `main_window.py` содержит `_build_resize_grip` метод
  - `_build_ui` вызывает оба новых метода
  - `_apply_theme` обновляет цвета header и grip
  - `python -c "from client.ui.main_window import MainWindow"` работает
  - Ручная проверка (критичная): запуск приложения → главное окно БЕЗ native title bar Windows; кастомный header 30px с ✕; drag по header перемещает окно; resize-grip ⤡ работает; окно в taskbar присутствует; Alt+Tab видит окно; fade show/hide по-прежнему плавный (если нет — zафиксировать в SUMMARY как known issue, не блокер)
  - test_main_window.py — если тесты падают из-за overrideredirect в headless режиме (нет DWM) — допустимо, отметить в SUMMARY что тесты тестировались вживую
  - Commit: `feat(window): кастомный title-bar с drag + resize-grip вместо native Windows frame`
  </done>
</task>

</tasks>

<verification>
**После всех 4 задач — итоговая проверка:**

1. **Импорты/компиляция:**
   ```bash
   cd "S:\Проекты\ежедневник" && python -c "
   from client.ui.inline_edit_panel import InlineEditPanel
   from client.ui.main_window import MainWindow
   from client.ui.week_navigation import WeekNavigation
   from client.ui.icon_compose import render_overlay_image, OVERLAY_GREEN_TOP
   print('ALL IMPORTS OK')
   "
   ```

2. **Тесты:**
   ```bash
   cd "S:\Проекты\ежедневник" && python -m pytest client/tests/test_main_window.py client/tests/test_week_navigation.py client/tests/test_icon_compose.py client/tests/test_overlay.py -x -q 2>&1 | tail -40
   ```
   - Pre-existing test_e2e_phase3/phase4 Tcl errors — игнорировать (не блокеры)
   - Новые падения в других тестах — fix перед commit

3. **Ручная проверка (ОБЯЗАТЕЛЬНО — пользователь запускает живое приложение):**
   ```bash
   cd "S:\Проекты\ежедневник" && python main.py
   ```
   Чеклист:
   - [ ] Overlay на обоях — бежево-зелёный (не синий)
   - [ ] Tray icon тоже зелёная (user это одобрил)
   - [ ] Клик по overlay → главное окно БЕЗ native Windows title bar, с кастомным header (bg_secondary, 30px, "Личный Еженедельник" + ✕)
   - [ ] Drag по header перемещает окно
   - [ ] ✕ в header — fade-out в tray (не destroy)
   - [ ] Resize-grip ⤡ в правом нижнем углу работает
   - [ ] Окно видно в Windows taskbar
   - [ ] Alt+Tab показывает окно
   - [ ] Стрелки недели ◀/▶ и "Сегодня" — в цвет темы (text_primary, НЕ синие); hover показывает mild bg shift
   - [ ] Клик по задаче → InlineEditPanel выезжает slide-down сверху scroll area (не popup Toplevel)
   - [ ] Esc закрывает inline panel (без сохранения)
   - [ ] Ctrl+Enter сохраняет изменения и закрывает
   - [ ] Клик "Удалить" удаляет задачу через UndoToast
   - [ ] Смена темы через tray → все обновляется (header/navigation buttons/grip)

4. **Git status:**
   ```bash
   git status
   ```
   Должны быть изменены: `client/ui/inline_edit_panel.py` (new), `client/ui/main_window.py`, `client/ui/week_navigation.py`, `client/ui/icon_compose.py`.
</verification>

<success_criteria>
- [ ] 4 файла изменены (1 новый + 3 modified)
- [ ] Все существующие тесты проходят (или pre-existing failures не ухудшены)
- [ ] 4 atomic commits на русском (по одному на задачу)
- [ ] Commits НЕ запушены — дождаться user подтверждения (CLAUDE.md rule: "спрашивать перед пушем")
- [ ] Ручная проверка пройдена на живом приложении — все 14 чеклист-пунктов выше OK
- [ ] Если Task 4 частично сломан (fade не работает с overrideredirect или что-то ещё) — задокументировать в SUMMARY как known issue, приложение всё равно работает

**Risk acceptance:** Если при ручной проверке Task 4 ломает приложение (например, невозможно открыть или crash) — разрешён частичный revert Task 4: закомментировать `self._window.overrideredirect(True)` в `_apply_borderless` и оставить остальные изменения. Native title bar вернётся, но Task 1/2/3 сработают.
</success_criteria>

<output>
После completion создать `.planning/quick/260421-wng-ux-v2-inline-edit-overlay-title-bar/260421-wng-SUMMARY.md` со:
- Что реализовано (по каждой из 4 задач)
- Известные issues (особенно по Task 4 — fade + overrideredirect поведение)
- Commit hashes (4 штуки)
- Скриншоты/описания визуального результата (если пользователь их запросит)
- Рекомендации для следующих правок (если что-то всплыло в процессе)
</output>
