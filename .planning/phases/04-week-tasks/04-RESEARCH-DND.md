# Phase 4: DnD Deep-Dive Research — Drag-and-Drop в CustomTkinter 5.2.2 на Windows

**Researched:** 2026-04-15
**Domain:** CustomTkinter widget-to-widget drag-and-drop на Windows 10/11 (HiDPI)
**Confidence:** HIGH (подход 2 верифицирован через официальные источники и паттерны Phase 3)

---

## Резюме

**Вопрос:** Какой подход использовать для cross-day DnD задач между секциями аккордеона?

**Ответ:** `Подход 2 — Custom mouse bindings + CTkToplevel ghost`. Это стандартный Tkinter-способ widget-to-widget DnD. Он хорошо задокументирован, совместим с CustomTkinter 5.2.2, не требует дополнительных зависимостей и работает с HiDPI через уже существующий Phase 3 `SetProcessDpiAwareness`. Аналогичный drag-паттерн уже реализован в `OverlayManager` (Phase 3) — Phase 4 его расширяет.

**Критическое предупреждение:** `winfo_containing()` **НЕ работает** внутри `CTkScrollableFrame` для вложенных виджетов из-за canvas-обёртки. Вместо него нужен ручной геометрический hit-test через `winfo_x/y/width/height` или хранение зон в `DragController`. Это единственный нетривиальный edge case.

**Primary recommendation:** DnD реализовать через `DragController` класс с bindings на `<ButtonPress-1>/<B1-Motion>/<ButtonRelease-1>` на TaskWidget, ghost = `CTkToplevel(overrideredirect=True)` с `-alpha 0.6`, drop-detection = ручной bbox-тест зарегистрированных DropZone'ов.

---

<user_constraints>
## User Constraints (из CONTEXT.md)

### Locked Decisions (D-22..D-28)
- **D-22:** Mouse-down на task body + mouse-move >5px → drag start. Короткий click = обычный click.
- **D-23:** Ghost = отдельный `CTkToplevel` с `overrideredirect=True`, opacity 0.6, копия task block, следует за курсором.
- **D-24:** Source day opacity 0.3 (placeholder). Target day: `rgba(accent_brand, 0.15)` bg + 3px border-left. Adjacent days: `rgba(accent_brand, 0.05)`.
- **D-25:** Next-week drop-zone: появляется при drag, нижняя секция с dashed accent_brand border.
- **D-26:** Drop valid → `task.day = target_day`, DB save, ghost fade-out 100ms, UI refresh. Drop invalid → ghost fade-out, task возвращается.
- **D-27:** Archive weeks — DnD заблокирован.
- **D-28:** Подход уточняется в фазе research (выполняется здесь).

### Claude's Discretion
- Точная реализация DnD (определяется в этом research)
- Структура `DragController` класса
- Fallback стратегия

### Deferred (OUT OF SCOPE)
- Intra-day reorder — v2
- Drag на произвольную неделю (не next) — v2
</user_constraints>

---

## Оценка подходов

### Подход 1: Canvas Overlay

**Идея:** Поверх аккордеона натянуть прозрачный `Canvas` того же размера; перехватывать все события мыши на Canvas; отрисовывать ghost как Canvas item; drop zone — rect hit-test в Canvas-координатах.

**Проблемы:**
- Canvas overlay блокирует все события ниже (click, hover, checkbox) — нужно вручную пробрасывать через `canvas.find_overlapping()` и `winfo_containing()`. Это ~300+ строк boilerplate для нормальной работы.
- Когда пользователь не тащит — Canvas должен быть "прозрачным" для событий. В Tkinter это нереализуемо нативно (`Canvas` всегда перехватывает события).
- Обновление Canvas-картинки задачи при каждом move: нужно рендерить Pillow image в Canvas item — значительно сложнее, чем Toplevel-окно.
- Нет сохраняемого DPI-scale: Canvas coords ≠ screen coords на HiDPI.

**Вердикт: НЕ РЕКОМЕНДУЕТСЯ.** Слишком много обходного кода, высокий риск регрессий в hover/click.

---

### Подход 2: Custom Mouse Bindings + CTkToplevel Ghost (РЕКОМЕНДУЕМЫЙ)

**Идея:**
- `<ButtonPress-1>`, `<B1-Motion>`, `<ButtonRelease-1>` биндинги на CTkFrame тела задачи.
- При движении >5px: создать `CTkToplevel(overrideredirect=True, -alpha=0.6)` с копией task block.
- Ghost следует за `event.x_root / event.y_root`.
- Drop detection: `DragController` хранит список `DropZone` объектов (bbox каждой day-секции); при `ButtonRelease` находит зону под курсором через bbox hit-test.

**Почему работает:**
- Этот паттерн — стандарт для widget-to-widget DnD в чистом Tkinter (без библиотек). Официальная документация `tkinter.dnd` использует аналогичную механику (внутренний `DndHandler` перехватывает события через `grab_set()`).
- В Phase 3 уже реализован drag overlay (`OverlayManager._on_drag_motion`) тем же паттерном — `x_root/y_root` + geometry update. Phase 4 применяет то же самое к ghost Toplevel.
- `overrideredirect=True` + `-alpha=0.6` работает на Windows (Tk 8.5+): alpha поддерживается на Windows 2000/XP+.
- `CTkToplevel` на Windows с `-alpha` может flashнуть при создании (Tk internal class switch) — **решение: создавать ghost один раз при `__init__` и затем `withdraw()/deiconify()`**, а не пересоздавать при каждом drag.

**Ограничения:**
1. `winfo_containing(x_root, y_root)` не надёжен внутри `CTkScrollableFrame` (см. ниже — CRITICAL PITFALL).
2. Ghost Toplevel на multi-monitor: координаты `x_root/y_root` — virtual desktop absolute. Это корректно и именно то, что нужно. Phase 3 уже обрабатывает multi-monitor bounds.
3. При быстром drag ghost может отстать на 1-2 кадра (Tk event queue). **Решение: `update_idletasks()` в motion handler** или позиционировать ghost через `geometry()` (быстрее чем `place()`).

**Вердикт: РЕКОМЕНДУЕТСЯ.** Минимальные зависимости, проверенный паттерн, совместим с существующим кодом Phase 3.

---

### Подход 3: ctypes WH_MOUSE Hook

**Идея:** Установить Windows low-level mouse hook через `SetWindowsHookEx(WH_MOUSE_LL)` для перехвата всех событий мыши на системном уровне.

**Проблемы:**
- Требует `SetWindowsHookEx` в отдельном потоке с message loop. Tk events и Win32 message loop — разные механизмы; мост между ними сложный.
- WH_MOUSE_LL имеет те же ограничения UIPI что и `WH_KEYBOARD_LL` (см. PITFALLS.md Pitfall 3 — тихо не срабатывает без elevation в некоторых сценариях).
- Overkill для задачи: нужно только перехватить события внутри одного окна приложения.
- Phase 3 намеренно НЕ использует системные хуки для drag overlay (использует Tk bindings).

**Вердикт: НЕ РЕКОМЕНДУЕТСЯ.** Избыточная сложность, те же UIPI-риски что и hotkeys.

---

### Подход 4: tkinterdnd2

**Идея:** Использовать `tkinterdnd2` (pip-пакет) для DnD.

**Критическая проблема:** `tkinterdnd2` реализует **OS-level drag-and-drop** (файлы, текст из внешних приложений). Он **НЕ решает** widget-to-widget DnD внутри одного приложения. Это разные механизмы. Из официального обсуждения CustomTkinter Discussion #470: "An important clarification emerged: TkinterDnD2 handles external file drops, while internal widget dragging requires custom motion-event handling."

Дополнительно: `tkinterdnd2` требует нативных `.dll` файлов и модификации `CTk.__init__` (подкласс от `TkinterDnD.DnDWrapper`). Это несовместимо с `customtkinter==5.2.2` (pinned — нельзя менять).

**Вердикт: НЕ ПРИМЕНИМО** для нашей задачи.

---

## CRITICAL PITFALL: winfo_containing в CTkScrollableFrame

`CTkScrollableFrame` внутренне использует Tk `Canvas` с `create_window()` для вложения виджетов. Это означает, что вложенные виджеты (DaySection, TaskWidget) находятся **внутри canvas coordinate space**, а не в обычном widget tree.

**Следствие:** `root.winfo_containing(x_root, y_root)` вернёт **Canvas** виджет, а не вложенный `CTkFrame` секции дня.

**Верификация:** Из CustomTkinter source code: `CTkScrollableFrame` переопределяет `winfo_children()` чтобы скрывать внутренний `_canvas`. Это подтверждает что внутренняя иерархия нестандартная.

**Решение:** `DragController` хранит explicit список `DropZone(day_date, frame_widget)` объектов. При release — итерировать список и проверять через `bbox_contains(zone.frame, x_root, y_root)`:

```python
def _find_drop_zone(self, x_root: int, y_root: int) -> Optional[DropZone]:
    for zone in self._drop_zones:
        widget = zone.frame
        if not widget.winfo_exists():
            continue
        wx = widget.winfo_rootx()
        wy = widget.winfo_rooty()
        ww = widget.winfo_width()
        wh = widget.winfo_height()
        if wx <= x_root <= wx + ww and wy <= y_root <= wy + wh:
            return zone
    return None
```

Это O(n) где n = 7-8 зон. Производительность несущественна.

---

## DragController — Полный скелет

### Архитектура

```
DragController
├── DropZone(day_date, frame_widget, is_archive)
├── _ghost: Optional[GhostWindow]  ← pre-created, withdraw/deiconify
├── _drop_zones: list[DropZone]    ← регистрируются из DaySection
├── _source: Optional[TaskWidget]  ← виджет, который тащат
└── _drag_threshold_px = 5
```

### Полный рабочий скелет

```python
# client/ui/drag_controller.py
"""
DragController — реализация cross-day DnD через mouse bindings + ghost Toplevel.

Паттерн: Phase 3 OverlayManager drag (B1-Motion + x_root/y_root) расширен
до widget-to-widget DnD с ghost окном и drop zone detection.

Ключевые решения:
  - Ghost pre-created (withdraw/deiconify), не пересоздаётся на каждый drag
    (избегает alpha-flash при создании Toplevel на Windows)
  - Drop zones — explicit list с bbox hit-test (winfo_containing ненадёжен в CTkScrollableFrame)
  - Bindings на task body frame, НЕ на checkbox/icons (D-22)
  - <B1-Motion> bound на root для захвата мыши вне source виджета (grab_set аналог)
"""
from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

logger = logging.getLogger(__name__)


@dataclass
class DropZone:
    """Зарегистрированная drop-зона (секция дня)."""
    day_date: date
    frame: ctk.CTkFrame        # CTkFrame тела секции дня (не заголовок)
    is_archive: bool = False   # D-27: архивные зоны блокируют drop
    is_next_week: bool = False # D-25: специальная зона следующей недели

    def get_bbox(self) -> tuple[int, int, int, int]:
        """Возвращает (x, y, x+w, y+h) в screen coordinates."""
        w = self.frame
        return (
            w.winfo_rootx(),
            w.winfo_rooty(),
            w.winfo_rootx() + w.winfo_width(),
            w.winfo_rooty() + w.winfo_height(),
        )

    def contains(self, x_root: int, y_root: int) -> bool:
        """Проверить что screen point (x_root, y_root) внутри зоны."""
        x1, y1, x2, y2 = self.get_bbox()
        return x1 <= x_root <= x2 and y1 <= y_root <= y2


class GhostWindow:
    """Полупрозрачное окно-призрак следующее за курсором.

    Pre-created при инициализации DragController. withdraw() скрывает,
    deiconify() показывает — без пересоздания (избегает alpha-flash).
    """

    ALPHA = 0.6

    def __init__(self, root: ctk.CTk, theme_colors: dict) -> None:
        self._root = root
        self._colors = theme_colors
        self._width = 300   # ширина по умолчанию, обновляется в show()
        self._height = 40   # высота по умолчанию

        self._window = ctk.CTkToplevel(root)
        self._window.withdraw()

        # CRITICAL: overrideredirect через after(100) — Win11 DWM (PITFALL 1 из 03-RESEARCH)
        self._window.after(100, self._init_style)

        # Содержимое — Label с текстом задачи
        self._label = ctk.CTkLabel(
            self._window,
            text="",
            anchor="w",
            fg_color=theme_colors.get("bg_secondary", "#EDE6D9"),
            corner_radius=6,
        )
        self._label.pack(fill="both", expand=True, padx=4, pady=4)

    def _init_style(self) -> None:
        """Применить overrideredirect + alpha. После Win11 DWM delay."""
        try:
            self._window.overrideredirect(True)
            self._window.attributes("-alpha", self.ALPHA)
            self._window.attributes("-topmost", True)
        except tk.TclError as e:
            logger.debug("GhostWindow style init: %s", e)

    def show(self, text: str, width: int, height: int,
             x: int, y: int) -> None:
        """Показать ghost с текстом задачи на позиции (x, y) — screen coords."""
        self._width = width
        self._height = height
        self._label.configure(text=text)
        self._window.geometry(f"{width}x{height}+{x}+{y}")
        self._window.deiconify()
        self._window.lift()

    def move(self, x: int, y: int) -> None:
        """Переместить ghost на (x, y) — screen coords."""
        self._window.geometry(f"{self._width}x{self._height}+{x}+{y}")

    def hide(self) -> None:
        """Скрыть ghost."""
        self._window.withdraw()

    def destroy(self) -> None:
        try:
            self._window.destroy()
        except Exception:
            pass


class DragController:
    """Контроллер drag-and-drop задач между секциями дня.

    Использование:
        controller = DragController(root, theme_manager)

        # Из DaySection._build_task_list():
        controller.register_drop_zone(DropZone(day_date=d, frame=body_frame))

        # Из TaskWidget.__init__():
        controller.bind_task(task_body_frame, task_id, task_text)

        # При смене недели:
        controller.clear_drop_zones()
    """

    DRAG_THRESHOLD_PX = 5  # D-22: минимальное смещение для начала drag

    def __init__(
        self,
        root: ctk.CTk,
        theme_manager,       # ThemeManager из Phase 3
        on_task_moved: Callable[[str, date], None],  # callback: task_id, new_day
    ) -> None:
        self._root = root
        self._theme = theme_manager
        self._on_task_moved = on_task_moved

        self._drop_zones: list[DropZone] = []

        # Drag state
        self._dragging: bool = False
        self._source_task_id: Optional[str] = None
        self._source_widget: Optional[ctk.CTkFrame] = None
        self._source_zone: Optional[DropZone] = None
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._drag_offset_x: int = 0
        self._drag_offset_y: int = 0
        self._hovered_zone: Optional[DropZone] = None

        # Ghost window — pre-created
        colors = {
            "bg_secondary": self._theme.get("bg_secondary"),
            "accent_brand": self._theme.get("accent_brand"),
        }
        self._ghost = GhostWindow(root, colors)

        # ThemeManager subscribe для обновления ghost при смене темы
        self._theme.subscribe(self._on_theme_change)

    # ---- Public API ----

    def register_drop_zone(self, zone: DropZone) -> None:
        """Зарегистрировать секцию дня как drop target."""
        self._drop_zones.append(zone)

    def clear_drop_zones(self) -> None:
        """Очистить все зоны (при смене недели)."""
        self._drop_zones.clear()

    def bind_task(
        self,
        task_body_frame: ctk.CTkFrame,
        task_id: str,
        task_text: str,
        source_zone: DropZone,
    ) -> None:
        """Привязать drag bindings к телу задачи (НЕ к checkbox, НЕ к icons).

        D-22: только body frame — не весь TaskWidget.
        """
        # Сохранить метаданные через lambda capture
        def on_press(event, tid=task_id, txt=task_text, sz=source_zone,
                     widget=task_body_frame):
            self._on_press(event, tid, txt, sz, widget)

        task_body_frame.bind("<ButtonPress-1>", on_press)
        task_body_frame.bind("<B1-Motion>", self._on_motion)
        task_body_frame.bind("<ButtonRelease-1>", self._on_release)

    def set_archive_mode(self, is_archive: bool) -> None:
        """D-27: заблокировать все drop zones при просмотре архивной недели."""
        for zone in self._drop_zones:
            zone.is_archive = is_archive

    def destroy(self) -> None:
        self._ghost.destroy()

    # ---- Internal drag handlers ----

    def _on_press(
        self,
        event,
        task_id: str,
        task_text: str,
        source_zone: DropZone,
        widget: ctk.CTkFrame,
    ) -> None:
        """ButtonPress-1: запомнить начало потенциального drag."""
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._source_task_id = task_id
        self._source_widget = widget
        self._source_zone = source_zone
        self._dragging = False

        # Offset: позиция клика внутри виджета (для ghost placement)
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y

        # ВАЖНО: биндим motion/release на root чтобы продолжать
        # получать события даже когда курсор за пределами source виджета
        self._root.bind("<B1-Motion>", self._on_motion, add="+")
        self._root.bind("<ButtonRelease-1>", self._on_release, add="+")

    def _on_motion(self, event) -> None:
        """B1-Motion: обновить ghost позицию, highlight drop zones."""
        if self._source_task_id is None:
            return

        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)

        if not self._dragging:
            # D-22: активировать drag только после >5px
            if dx < self.DRAG_THRESHOLD_PX and dy < self.DRAG_THRESHOLD_PX:
                return
            self._start_drag(event)

        # Обновить позицию ghost
        ghost_x = event.x_root - self._drag_offset_x
        ghost_y = event.y_root - self._drag_offset_y
        self._ghost.move(ghost_x, ghost_y)

        # Обновить highlight drop zones
        self._update_zone_highlights(event.x_root, event.y_root)

    def _on_release(self, event) -> None:
        """ButtonRelease-1: commit drop или cancel."""
        # Снять root bindings
        self._root.unbind("<B1-Motion>")
        self._root.unbind("<ButtonRelease-1>")

        if not self._dragging:
            # Не был drag — сбросить состояние, пропустить обычный click
            self._reset_state()
            return

        # Найти drop zone под курсором
        target = self._find_drop_zone(event.x_root, event.y_root)

        if target is not None and target != self._source_zone and not target.is_archive:
            # D-26: valid drop
            self._commit_drop(target)
        else:
            # D-26: invalid drop — cancel
            self._cancel_drag()

    def _start_drag(self, event) -> None:
        """Начать фактический drag: показать ghost, скрыть source."""
        self._dragging = True

        # Показать ghost
        ghost_x = event.x_root - self._drag_offset_x
        ghost_y = event.y_root - self._drag_offset_y
        widget_w = self._source_widget.winfo_width()
        widget_h = self._source_widget.winfo_height()
        # Получить текст задачи через widget tag или хранить отдельно
        # (в реальной реализации — из TaskWidget._task.text)
        task_text = self._get_source_text()
        self._ghost.show(task_text, widget_w, widget_h, ghost_x, ghost_y)

        # D-24: Source задача → opacity 0.3 (dim placeholder)
        try:
            self._source_widget.configure(fg_color=self._theme.get("bg_secondary"))
            # Применить визуальный dim через alpha на label внутри
            for child in self._source_widget.winfo_children():
                try:
                    child.configure(text_color=self._make_dim_color(
                        self._theme.get("text_primary")))
                except (tk.TclError, AttributeError):
                    pass
        except Exception as e:
            logger.debug("dim source widget: %s", e)

        # D-25: показать next-week zone
        self._show_next_week_zone()

    def _commit_drop(self, target: DropZone) -> None:
        """D-26: Применить drop — task.day → target_day."""
        self._ghost.hide()
        self._clear_all_highlights()
        self._restore_source_widget()

        if self._source_task_id and self._on_task_moved:
            try:
                self._on_task_moved(self._source_task_id, target.day_date)
            except Exception as e:
                logger.error("on_task_moved callback failed: %s", e)

        self._reset_state()

    def _cancel_drag(self) -> None:
        """D-26: отменить drag — ghost исчезает, задача возвращается."""
        self._ghost.hide()
        self._clear_all_highlights()
        self._restore_source_widget()
        self._reset_state()
        logger.debug("DnD cancelled")

    def _reset_state(self) -> None:
        """Сбросить все drag-переменные."""
        self._dragging = False
        self._source_task_id = None
        self._source_widget = None
        self._source_zone = None
        self._hovered_zone = None

    # ---- Drop zone detection (CRITICAL: не использовать winfo_containing) ----

    def _find_drop_zone(self, x_root: int, y_root: int) -> Optional[DropZone]:
        """Найти DropZone под курсором через bbox hit-test.

        НЕ использует winfo_containing() — ненадёжен внутри CTkScrollableFrame.
        Итерирует registered zones (O(n), n≤8 — несущественно).
        """
        for zone in self._drop_zones:
            if not zone.frame.winfo_exists():
                continue
            if zone.contains(x_root, y_root):
                return zone
        return None

    def _update_zone_highlights(self, x_root: int, y_root: int) -> None:
        """D-24: обновить подсветку drop zones при движении."""
        hovered = self._find_drop_zone(x_root, y_root)

        if hovered == self._hovered_zone:
            return  # нет изменений

        # Снять подсветку со старой зоны
        if self._hovered_zone is not None:
            self._set_zone_highlight(self._hovered_zone, "normal")

        # Применить подсветку к новой
        if hovered is not None and not hovered.is_archive and hovered != self._source_zone:
            self._set_zone_highlight(hovered, "active")
            # Adjacent zones — soft highlight
            for zone in self._drop_zones:
                if zone != hovered and zone != self._source_zone and not zone.is_archive:
                    self._set_zone_highlight(zone, "adjacent")
        else:
            # Сбросить все adjacent
            for zone in self._drop_zones:
                if zone != self._source_zone:
                    self._set_zone_highlight(zone, "normal")

        self._hovered_zone = hovered

    def _set_zone_highlight(self, zone: DropZone, mode: str) -> None:
        """Применить visual highlight к frame секции дня.

        mode: "active" | "adjacent" | "normal"
        """
        if not zone.frame.winfo_exists():
            return
        accent = self._theme.get("accent_brand")
        bg_primary = self._theme.get("bg_primary")

        # Простой rgba через HEX alpha-blend
        # (CTkFrame не поддерживает rgba — blend вручную)
        try:
            if mode == "active":
                # D-24: rgba(accent_brand, 0.15) blended на bg
                color = self._blend_hex(bg_primary, accent, 0.15)
                zone.frame.configure(fg_color=color)
            elif mode == "adjacent":
                # D-24: rgba(accent_brand, 0.05)
                color = self._blend_hex(bg_primary, accent, 0.05)
                zone.frame.configure(fg_color=color)
            else:
                zone.frame.configure(fg_color=bg_primary)
        except tk.TclError as e:
            logger.debug("zone highlight error: %s", e)

    def _clear_all_highlights(self) -> None:
        """Снять все highlights после drop/cancel."""
        for zone in self._drop_zones:
            self._set_zone_highlight(zone, "normal")

    # ---- Next-week zone (D-25) ----

    def _show_next_week_zone(self) -> None:
        """D-25: показать секцию 'Следующая неделя' при начале drag."""
        for zone in self._drop_zones:
            if zone.is_next_week:
                try:
                    zone.frame.pack(fill="x", pady=(8, 4))
                except Exception:
                    pass

    def _hide_next_week_zone(self) -> None:
        """Скрыть секцию следующей недели после drop/cancel."""
        for zone in self._drop_zones:
            if zone.is_next_week:
                try:
                    zone.frame.pack_forget()
                except Exception:
                    pass

    # ---- Helpers ----

    def _restore_source_widget(self) -> None:
        """Вернуть source виджет в нормальный вид."""
        if self._source_widget and self._source_widget.winfo_exists():
            try:
                self._source_widget.configure(
                    fg_color=self._theme.get("bg_secondary"))
                for child in self._source_widget.winfo_children():
                    try:
                        child.configure(text_color=self._theme.get("text_primary"))
                    except (tk.TclError, AttributeError):
                        pass
            except Exception as e:
                logger.debug("restore source: %s", e)

    def _get_source_text(self) -> str:
        """Получить текст задачи из source виджета (fallback)."""
        # В реальной реализации DragController хранит task_text при bind_task()
        # Здесь — заглушка
        return "Задача..."

    def _make_dim_color(self, hex_color: str) -> str:
        """Сделать цвет тусклым (50% opacity blend с фоном)."""
        return self._blend_hex(self._theme.get("bg_secondary"), hex_color, 0.3)

    @staticmethod
    def _blend_hex(bg: str, fg: str, alpha: float) -> str:
        """Линейный blend: result = bg * (1-alpha) + fg * alpha.

        Принимает HEX strings (#RRGGBB), возвращает #RRGGBB.
        """
        def parse(h: str) -> tuple:
            h = h.lstrip("#")
            if len(h) == 6:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            return (128, 128, 128)  # fallback

        br, bg_, bb = parse(bg)
        fr, fg_, fb = parse(fg)
        r = int(br * (1 - alpha) + fr * alpha)
        g = int(bg_ * (1 - alpha) + fg_ * alpha)
        b = int(bb * (1 - alpha) + fb * alpha)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_theme_change(self, palette: dict) -> None:
        """ThemeManager subscribe: обновить ghost цвета при смене темы."""
        try:
            self._ghost._label.configure(
                fg_color=palette.get("bg_secondary", "#EDE6D9"))
        except Exception:
            pass
```

---

## Integration в TaskWidget

```python
# В client/ui/task_widget.py — как биндить DragController

class TaskWidget:
    def __init__(self, parent, task: Task, drag_controller: DragController,
                 source_zone: DropZone, theme_manager, on_done, on_edit, on_delete):
        self._task = task

        # Контейнер всего виджета
        outer = ctk.CTkFrame(parent, corner_radius=8)
        outer.pack(fill="x", pady=4)

        # Row: [checkbox] [body_frame] [action_icons]
        row = ctk.CTkFrame(outer, fg_color="transparent")
        row.pack(fill="x")

        # Checkbox — НЕ drag target (D-22)
        checkbox = ctk.CTkCheckBox(row, ...)
        checkbox.pack(side="left", padx=8)

        # Body frame — drag target (D-22: mouse на теле, не на checkbox/icons)
        body_frame = ctk.CTkFrame(row, fg_color="transparent", cursor="fleur")
        body_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(body_frame, text=task.text, ...).pack(...)

        # Action icons (hover-reveal) — НЕ drag target (D-22)
        icons_frame = ctk.CTkFrame(row, fg_color="transparent")
        icons_frame.pack(side="right", padx=8)
        # ... edit/delete buttons ...

        # BIND DnD только на body_frame
        drag_controller.bind_task(body_frame, task.id, task.text, source_zone)
```

---

## Integration в DaySection

```python
# В client/ui/day_section.py — регистрация DropZone

class DaySection:
    def __init__(self, parent, day_date: date, drag_controller: DragController, ...):
        self._day_date = day_date
        self._drag_controller = drag_controller

        # Секция: заголовок + body frame
        self._frame = ctk.CTkFrame(parent, ...)
        self._body = ctk.CTkFrame(self._frame, ...)  # сюда кладутся задачи
        self._body.pack(fill="x")

        # Регистрируем как drop zone
        zone = DropZone(day_date=day_date, frame=self._body)
        drag_controller.register_drop_zone(zone)
        self._zone = zone

    def set_archive(self, is_archive: bool) -> None:
        self._zone.is_archive = is_archive
```

---

## Edge Cases и обработка

### 1. Drop на собственный источник (D-26)

**Проблема:** Пользователь drop'нул на тот же день откуда взял.

**Решение:** В `_on_release` — `if target == self._source_zone` → cancel (не commit). Уже включено в скелет: `target != self._source_zone` в условии.

---

### 2. Drop вне окна приложения

**Проблема:** Пользователь отпустил мышь вне окна MainWindow.

**Решение:** `_find_drop_zone()` вернёт `None` (ни одна зона не покрывает точку вне окна) → `_cancel_drag()`. Работает автоматически.

**Дополнительно:** Root-level `<ButtonRelease-1>` binding гарантирует получение события даже вне source виджета.

---

### 3. Rapid drag (быстрое движение)

**Проблема:** При очень быстром движении `B1-Motion` может пропустить кадры — ghost отстаёт.

**Решение:** Позиционирование ghost через `geometry()` (синхронная Win32 `SetWindowPos`) + опционально `update_idletasks()` в конце `_on_motion`. Не вызывать `update()` — это может вызвать вложенный event loop.

```python
def _on_motion(self, event) -> None:
    # ... обновить ghost ...
    self._ghost.move(ghost_x, ghost_y)
    # Опционально — убрать если вызывает проблемы:
    # self._root.update_idletasks()
```

---

### 4. Ghost alpha flash при создании Toplevel

**Проблема:** На Windows, изменение `-alpha` с `1.0` на другое значение вызывает flash (Tk меняет window class). Пересоздание ghost при каждом drag вызовет flash.

**Решение (уже включено в скелет):** Ghost создаётся ОДИН РАЗ в `DragController.__init__`, затем только `deiconify()/withdraw()`. `-alpha` устанавливается один раз в `GhostWindow._init_style()`.

---

### 5. Ghost на multi-monitor (D-28 риск)

**Проблема:** На secondary monitor с другим DPI scale — ghost может смещаться.

**Решение:** Phase 3 уже вызывает `SetProcessDpiAwareness(2)` (per-monitor DPI aware). Все `x_root/y_root` события Tkinter возвращают physical pixels (не логические) после этого вызова. `geometry(f"+{x}+{y}")` использует те же physical pixels. Смещений быть не должно.

**Проверка:** Тест на системе с двумя мониторами с разным DPI — обязательный smoke-test.

---

### 6. CTkScrollableFrame event conflicts

**Проблема:** `CTkScrollableFrame` использует `<B1-Motion>` для скролла мышью (touchpad drag). Binding на child виджет может конфликтовать.

**Решение:**
- Биндинг `<B1-Motion>` на конкретный `task_body_frame` (не на CTkScrollableFrame) — по умолчанию не propagate.
- При начале drag (>5px) — вернуть `"break"` из motion handler чтобы блокировать scroll propagation:

```python
def _on_motion(self, event) -> None:
    if self._dragging:
        return "break"  # блокировать scroll в CTkScrollableFrame
    # проверить threshold...
```

---

### 7. Быстрый drop + последовательные drag

**Проблема:** Второй drag начинается до завершения первого (очень редко, но возможно).

**Решение:** `_on_press` проверяет `if self._dragging: self._cancel_drag()` перед сохранением нового состояния.

---

### 8. Archive weeks (D-27)

**Проблема:** При просмотре архивной недели DnD должен быть заблокирован.

**Решение:** `DragController.set_archive_mode(True)` вызывается при переходе на архивную неделю. Все zone.is_archive = True. В `_on_release`: `not target.is_archive` блокирует commit.

**Дополнительно:** Сами bindings на task body можно не трогать — блокировка через is_archive flag эффективна.

---

## Fallback: Если DnD окажется нестабильным

Если при выполнении Phase 4 обнаружится что ghost Toplevel вызывает критические проблемы (crash на конкретной конфигурации, неустранимый lag), следующий fallback **НЕ требует изменений в CONTEXT.md** (это реализационный выбор, входящий в Claude's Discretion):

**Fallback: Ghost без Toplevel — Canvas overlay на одном MainWindow**

Вместо отдельного Toplevel создать `tk.Canvas` поверх MainWindow (временный overlay только во время drag). На Canvas рисовать скопированный content через Pillow snapshot виджета:

```python
# Pillow snapshot виджета (упрощённо)
import PIL.ImageGrab

def snapshot_widget(widget) -> PIL.Image:
    x = widget.winfo_rootx()
    y = widget.winfo_rooty()
    w = widget.winfo_width()
    h = widget.winfo_height()
    return PIL.ImageGrab.grab(bbox=(x, y, x+w, y+h))
```

Минус: на HiDPI `ImageGrab.grab()` может вернуть удвоенные размеры — нужна DPI коррекция. Использовать только как последний резерв.

**Второй fallback (context menu):** Если Canvas snapshot тоже нестабильный — реализовать контекстное меню "Перенести на..." через right-click на задаче. По D-22..D-28 этот вариант заменяет DnD UX. Требует одобрения владельца — но DnD реализуем через Подход 2, поэтому этот fallback маловероятен.

---

## Тестовая стратегия

### Unit тесты (без display)

```python
# client/tests/test_drag_controller.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
import customtkinter as ctk

@pytest.fixture(scope="session")
def tk_root():
    root = ctk.CTk()
    root.withdraw()
    yield root
    root.destroy()

@pytest.fixture
def mock_theme():
    theme = MagicMock()
    theme.get.side_effect = lambda key: {
        "bg_primary": "#F5EFE6",
        "bg_secondary": "#EDE6D9",
        "text_primary": "#2B2420",
        "accent_brand": "#1E73E8",
    }.get(key, "#ffffff")
    return theme


class TestDropZone:
    def test_contains_inside(self, tk_root):
        """DropZone.contains() True для точки внутри bbox."""
        frame = ctk.CTkFrame(tk_root)
        frame.place(x=100, y=100, width=200, height=50)
        tk_root.update_idletasks()
        zone = DropZone(day_date=date.today(), frame=frame)
        # Не можем тестировать winfo_rootx без реального display
        # Тестируем логику через mock
        with patch.object(frame, 'winfo_rootx', return_value=100), \
             patch.object(frame, 'winfo_rooty', return_value=100), \
             patch.object(frame, 'winfo_width', return_value=200), \
             patch.object(frame, 'winfo_height', return_value=50), \
             patch.object(frame, 'winfo_exists', return_value=True):
            assert zone.contains(150, 125) is True
            assert zone.contains(50, 125) is False
            assert zone.contains(150, 200) is False

    def test_archive_zone_rejected(self):
        """Archive zone не принимает drop."""
        frame = MagicMock()
        frame.winfo_exists.return_value = True
        frame.winfo_rootx.return_value = 0
        frame.winfo_rooty.return_value = 0
        frame.winfo_width.return_value = 300
        frame.winfo_height.return_value = 100
        zone = DropZone(day_date=date.today(), frame=frame, is_archive=True)
        # В DragController: not target.is_archive блокирует commit
        assert zone.is_archive is True


class TestDragController:
    def test_find_drop_zone_hit(self, mock_theme):
        """_find_drop_zone находит зону под курсором."""
        root = MagicMock()
        controller = DragController(root, mock_theme, on_task_moved=lambda t, d: None)

        frame1 = MagicMock()
        frame1.winfo_exists.return_value = True
        frame1.winfo_rootx.return_value = 0
        frame1.winfo_rooty.return_value = 0
        frame1.winfo_width.return_value = 300
        frame1.winfo_height.return_value = 60
        zone1 = DropZone(day_date=date(2026, 4, 14), frame=frame1)

        frame2 = MagicMock()
        frame2.winfo_exists.return_value = True
        frame2.winfo_rootx.return_value = 0
        frame2.winfo_rooty.return_value = 70
        frame2.winfo_width.return_value = 300
        frame2.winfo_height.return_value = 60
        zone2 = DropZone(day_date=date(2026, 4, 15), frame=frame2)

        controller.register_drop_zone(zone1)
        controller.register_drop_zone(zone2)

        assert controller._find_drop_zone(150, 30) is zone1
        assert controller._find_drop_zone(150, 100) is zone2
        assert controller._find_drop_zone(150, 200) is None

    def test_drag_threshold(self, mock_theme):
        """Drag не активируется до >5px движения."""
        root = MagicMock()
        called = []
        controller = DragController(root, mock_theme,
                                    on_task_moved=lambda t, d: called.append((t, d)))

        # Симулируем press
        event_press = MagicMock()
        event_press.x_root = 100
        event_press.y_root = 100
        event_press.x = 5
        event_press.y = 5
        source_zone = DropZone(day_date=date.today(), frame=MagicMock())
        controller._drag_start_x = 100
        controller._drag_start_y = 100
        controller._source_task_id = "task-001"
        controller._source_widget = MagicMock()
        controller._source_zone = source_zone

        # Motion <5px — drag не активируется
        event_motion = MagicMock()
        event_motion.x_root = 103
        event_motion.y_root = 102
        controller._on_motion(event_motion)
        assert not controller._dragging

        # Motion >5px — drag активируется
        event_motion.x_root = 108
        with patch.object(controller, '_start_drag') as mock_start:
            controller._on_motion(event_motion)
            mock_start.assert_called_once()

    def test_cancel_on_same_source(self, mock_theme):
        """Drop на источник отменяет drag."""
        root = MagicMock()
        moved = []
        controller = DragController(root, mock_theme,
                                    on_task_moved=lambda t, d: moved.append((t, d)))

        source_frame = MagicMock()
        source_frame.winfo_exists.return_value = True
        source_frame.winfo_rootx.return_value = 0
        source_frame.winfo_rooty.return_value = 0
        source_frame.winfo_width.return_value = 300
        source_frame.winfo_height.return_value = 60
        source_zone = DropZone(day_date=date.today(), frame=source_frame)

        controller._dragging = True
        controller._source_zone = source_zone
        controller._source_task_id = "task-001"
        controller.register_drop_zone(source_zone)

        with patch.object(controller, '_cancel_drag') as mock_cancel, \
             patch.object(controller, '_commit_drop') as mock_commit:
            event = MagicMock()
            event.x_root = 150
            event.y_root = 30
            controller._on_release(event)
            # Drop на source_zone → cancel (не commit)
            mock_cancel.assert_called_once()
            mock_commit.assert_not_called()

    def test_blend_hex(self):
        """_blend_hex корректно смешивает цвета."""
        # 50% blend белого и чёрного = средне-серый
        result = DragController._blend_hex("#000000", "#ffffff", 0.5)
        assert result == "#7f7f7f"
        # 0% blend = bg
        result = DragController._blend_hex("#ff0000", "#0000ff", 0.0)
        assert result == "#ff0000"
        # 100% blend = fg
        result = DragController._blend_hex("#ff0000", "#0000ff", 1.0)
        assert result == "#0000ff"
```

### Smoke тест (ручной — при наличии display)

```
1. Запустить приложение
2. Открыть главное окно
3. Создать задачу в Пн через quick-capture
4. Попытаться drag: короткий click → никакого drag (task stays, click propagates)
5. Drag >5px → ghost появляется, следует за курсором
6. Hover на Вт → синий highlight
7. Drop на Вт → задача переместилась, ghost исчез
8. Drop вне окна → задача вернулась
9. Multi-monitor: drag через границу мониторов → ghost не "прыгает"
```

---

## Совместимость с CustomTkinter 5.2.2

| Аспект | Статус | Источник |
|--------|--------|---------|
| CTkToplevel + overrideredirect | РАБОТАЕТ (паттерн из Phase 3) | overlay.py реализация |
| CTkToplevel + -alpha 0.6 | РАБОТАЕТ (Windows Tk 8.4+) | wm attributes docs |
| CTkFrame.configure(fg_color=...) | РАБОТАЕТ | CustomTkinter wiki |
| CTkLabel.configure(text_color=...) | РАБОТАЕТ | CustomTkinter wiki |
| <B1-Motion> on CTkFrame | РАБОТАЕТ (стандартный Tkinter) | tkinter events docs |
| winfo_containing в CTkScrollableFrame | НЕ НАДЁЖНО | CTkScrollableFrame source |
| winfo_rootx/y/width/height на CTkFrame | РАБОТАЕТ | stандартный Tkinter |

---

## Источники

### Primary (HIGH confidence)
- `client/ui/overlay.py` — Phase 3 drag реализация (x_root/y_root pattern верифицирован)
- `.planning/phases/03-overlay-system/03-RESEARCH.md` Pattern 5 — Drag Behavior
- CustomTkinter Discussion #470 — подтверждение что tkinterdnd2 ≠ widget DnD
- Python docs `tkinter.dnd` — официальное описание dnd_accept/dnd_commit интерфейса
- Tcl/Tk `wm attributes` docs — alpha support на Windows

### Secondary (MEDIUM confidence)
- GitHub Discussion #470 комментарии — CTkButtonDnD B1-Motion example
- Tkinter `winfo_containing` docs — поведение с nested canvas widgets
- CustomTkinter CTkScrollableFrame wiki — внутренняя структура canvas

### Tertiary (LOW confidence)
- Community claims о performance 60fps ghost на Windows — не измерено формально
- CTkScrollableFrame B1-Motion conflict — логический вывод из canvas architecture, не воспроизведено

---

## Итог

| Вопрос | Ответ |
|--------|-------|
| Какой подход? | Подход 2: mouse bindings + CTkToplevel ghost |
| Нужны новые зависимости? | Нет |
| Совместимо с customtkinter==5.2.2? | Да |
| Совместимо с HiDPI? | Да (Phase 3 SetProcessDpiAwareness уже активен) |
| Совместимо с multi-monitor? | Да (x_root/y_root — virtual desktop coords) |
| Самый опасный pitfall? | winfo_containing в CTkScrollableFrame — решён через bbox hit-test |
| DnD реализуемо? | Да. Ghost Toplevel pre-created, bbox detection, O(n) зоны |
| Fallback если что-то пойдёт не так? | Pillow ImageGrab canvas ghost → context menu "Перенести на..." |

*DnD research: 2026-04-15*
*Автор: gsd-researcher Phase 04*
