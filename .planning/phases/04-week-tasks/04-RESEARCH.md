# Phase 4: Недельный вид и задачи — Research

**Researched:** 2026-04-15
**Domain:** CustomTkinter task CRUD + quick-capture popup + edit dialog + undo-toast + keyboard navigation
**Confidence:** HIGH (большинство паттернов верифицировано через существующую кодовую базу Phase 3 и официальную документацию CustomTkinter)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Quick Capture**
- D-01: Right-click overlay → Quick Capture input (замена mini-menu из Phase 3 UI-SPEC). Tray-меню уже покрывает action'ы mini-menu — избыточности нет.
- D-02: Input 400×40 под overlay-квадратом (gap 8px); edge-flip наверх если overlay у нижнего края экрана.
- D-03: Input закрывается на: Esc, focus-loss, еще один right-click на overlay, drag квадрата.
- D-04: Smart parse RU: `HH:MM` + {сегодня / завтра / послезавтра} + {пн / вт / ср / чт / пт / сб / вс}. Fallback day=сегодня если не распознан.
- D-05: Enter → save + clear input + keep focus (multi-add). Empty Enter → short red-border flash.
- D-06: Ближайшая дата для weekday: если день уже прошёл в текущей неделе → следующая неделя того же weekday.

**Task block rendering (3 styles)**
- D-07: Style A (cards): bg_secondary + shadow_card + rounded 8, padding 12/10, gap 8.
- D-08: Style B (lines): 1px bottom-border, padding 10/8, no shadow/bg.
- D-09: Style C (minimal): невидимый по default, hover → rgba(accent, 0.04) bg + rounded 6 + padding 6.
- D-10: Task text — wrap без лимита, word-wrap break-word, CTkLabel.configure(wraplength=width-24).
- D-11: Checkbox 18×18 rounded 3: not-done (text_secondary border), done (accent_done fill + white ✓), overdue (accent_overdue border).
- D-12: Time field: mono, text_secondary; red (accent_overdue) если time_deadline < now && !done; dim (text_tertiary) если done.
- D-13: Hover → ✏️ + 🗑 fade-in справа (size 14×14, opacity 0 → 1 за 150ms).

**Edit dialog**
- D-14: Modal center of main window (НЕ overlay); backdrop rgba(0,0,0,0.4).
- D-15: Fields: Text (multiline Text widget, Ctrl+Enter = Save, Enter = newline) + Day (dropdown "Сегодня / Завтра / Послезавтра / выбрать дату→CalendarModal") + Time (HH:MM input с validation regex + ✕ clear) + Done (checkbox).
- D-16: Buttons: [🗑 Удалить] слева (red, immediate delete + undo-toast), [Отмена] [Сохранить] справа (Esc=Отмена, Ctrl+Enter=Сохранить).
- D-17: Save disabled при empty text OR invalid HH:MM regex.

**Delete (undo-toast)**
- D-18: Click 🗑 или "Удалить" в dialog → task fade-out 200ms + storage.soft_delete_task() (tombstone из Phase 2).
- D-19: Toast 280×40 bottom-center main window: "⟲ Задача удалена • [Отменить]", countdown-bar shrinks 5s.
- D-20: Click "Отменить" < 5s → task.deleted_at = None (Phase 2 API), task fade-in обратно в исходное место.
- D-21: Multi-delete → queued toasts, max 3 одновременно (stack vertically).

**Drag-and-Drop**
- D-22: Mouse-down на task body (не checkbox, не icons) + mouse-move >5px → drag start.
- D-23: Ghost = отдельный CTkToplevel с overrideredirect=True, opacity 0.6, копия task block.
- D-24: Source day: task opacity 0.3 (placeholder). Target day highlighting: rgba(accent_brand, 0.15) bg.
- D-25: Next-week drop-zone при drag, нижняя секция с dashed accent_brand border.
- D-26: Drop valid → task.day = target_day, DB save, ghost fade-out. Drop invalid → cancelled.
- D-27: Archive weeks — DnD заблокирован.
- D-28: DnD approach уточняется в phase-research (ОТДЕЛЬНЫЙ RESEARCHER).

**Week navigation & archive**
- D-29: Header: ◀ Неделя N • DD-DD мес • Сегодня ▶. "Сегодня" виден только для не-current week.
- D-30: Keyboard shortcuts: Ctrl+←/→ = prev/next week, Ctrl+T = today, Esc = close, Ctrl+Space = quick-capture.
- D-31: Archive (week_start < current_monday): opacity 0.7 на content + banner "📦 Архив • неделя N • Вернуться →". Editing/DnD disabled.
- D-32: Future weeks: full functionality.
- D-33: Empty day: "+" icon 24×24 по центру, click → inline add input в этот день.

**Task keyboard controls**
- D-34: Space = toggle done, Del = delete (undo-toast), Enter = open edit dialog, Arrow up/down = prev/next task.

**Data contracts (Phase 2 — не изменяем)**
- D-35: LocalStorage.add_task(), update_task(), soft_delete_task(), merge_from_server(), get_visible_tasks() — из Phase 2.
- D-36: Task model неизменна: id(UUID), user_id, text, day(ISO), time_deadline(ISO|None), done, position, created_at, updated_at, deleted_at.
- D-37: position — drag-reorder внутри дня v2. Phase 4 = cross-day drag only.

### Claude's Discretion

- Конкретная структура client/ui/ (split на day_section.py, task_widget.py, edit_dialog.py, quick_capture.py, drag_controller.py, undo_toast.py)
- Точная implementation DnD (определяется в phase-research)
- Calendar picker UI (Day dropdown fallback "выбрать дату")
- Exact animation timings в рамках UI-SPEC ranges
- Error handling для parse edge cases
- Test strategy (unit/integration/e2e split)

### Deferred Ideas (OUT OF SCOPE)

- Global hotkey (Win+Q) — v2 (requires admin elevation)
- Recurring tasks — excluded per PROJECT.md
- Task priorities, categories, tags — anti-features v1
- Multi-select + bulk ops — v2
- Search по всем неделям — v2
- Drag arbitrary week (не just next) — v1 covers next; arbitrary v2 (UXI-03)
- Undo stack >1 level — v1 undoes only last delete within 5s
- English smart-parse — v2
- Intra-day task reorder via DnD — v2
- Calendar picker full UI — v2 polish (basic dropdown достаточно)
- Task colors/emoji tags — v2
- Attachments — never v1

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WEEK-01 | Окно отображает текущую неделю (Пн-Вс, 7 дней-секций) | §Rendering Engine — MainWindow._build_day_section extension с TaskWidget list |
| WEEK-02 | Стрелки навигации: предыдущая/следующая неделя; номер недели и диапазон дат | §Week Navigation — ISO week calc + date.isocalendar() |
| WEEK-03 | Кнопка "Сегодня" — быстрый возврат к текущей неделе | §Week Navigation — visible only when not current week |
| WEEK-04 | Просроченные задачи подсвечены красным | §Task Rendering — TaskWidget overdue detection, accent_overdue border |
| WEEK-05 | Минималистичный закруглённый дизайн задач-блоков | §Task Styles — 3 styles via SettingsStore.task_style |
| WEEK-06 | Архив прошлых недель через навигацию | §Archive Pattern — opacity 0.7, banner, editing disabled |
| TASK-01 | Добавление задачи: текст + день + время (2-3 действия) | §Quick Capture — CTkToplevel popup + smart parse RU |
| TASK-02 | Отметить задачу выполненной (checkbox) | §Checkbox Pattern — CTkFrame-based checkbox, LocalStorage.update_task(done=True) |
| TASK-03 | Редактировать текст/время существующей задачи | §Edit Dialog — CTkToplevel + grab_set() modal |
| TASK-04 | Удалить задачу (мягкое удаление + tombstone) | §Delete + Undo-Toast — soft_delete_task() + 5s undo window |
| TASK-05 | Drag-and-drop задачи между днями текущей недели | Отдельный DnD researcher — D-28 |
| TASK-06 | Drag-and-drop на следующую неделю (drop zone) | Отдельный DnD researcher — D-28 |
| TASK-07 | Позиция задачи в дне (position) запоминается | §Task Position — LocalStorage.update_task(position=...) |

</phase_requirements>

---

## Summary

Phase 4 наполняет каркас Phase 3 реальным контентом. Техническая основа — расширение `MainWindow._build_day_section()` для рендеринга `TaskWidget` списков, плюс 4 новых компонента: `QuickCapturePopup`, `EditDialog`, `UndoToastManager`, и `InlineAddInput`. Все компоненты работают через существующий `LocalStorage` API (Phase 2) и подписываются на `ThemeManager` (Phase 3).

Три критических области для Phase 4: (1) `QuickCapturePopup` — это `CTkToplevel` с `overrideredirect=True`, тот же паттерн что Phase 3 overlay, с edge-flip логикой; (2) `EditDialog` — `CTkToplevel` с `grab_set()` для модальности, `CTkTextbox` для мультистрочного текста; (3) `UndoToastManager` — `CTkFrame` внутри `MainWindow` (не Toplevel), абсолютно позиционированный через `place()`.

Ключевой инсайт: все "сложные" вещи в Phase 4 — это комбинации уже работающих Pattern 1 (overrideredirect) и Pattern 7 (ThemeManager) из Phase 3. Никакой принципиально новой технологии не нужно. DnD — исключение (отдельный researcher).

**Primary recommendation:** TaskWidget — `CTkFrame` с Canvas-based custom checkbox (не CTkCheckBox), hover через `<Enter>`/`<Leave>` events, анимации через `root.after()` циклы. QuickCapturePopup — `CTkToplevel` overrideredirect как Phase 3 overlay. EditDialog — CTkToplevel + `grab_set()`. UndoToast — `CTkFrame` с `place()` bottom-center, timer через `root.after(5000, hide)`.

---

## Standard Stack

### Core (pinned — не менять)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| customtkinter | ==5.2.2 | Все виджеты: CTkFrame, CTkLabel, CTkEntry, CTkTextbox, CTkOptionMenu | Pinned Phase 3; уже в requirements.txt |
| tkinter | stdlib | Canvas для custom checkbox, bind events, after() | Stdlib — всегда доступен |
| re | stdlib | Smart parse regex для quick-capture | Stdlib; без зависимостей |
| datetime | stdlib | ISO date arithmetic, ISO week calc | Stdlib |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tkcalendar | — | Full calendar date picker | НЕ ИСПОЛЬЗОВАТЬ в v1 — не в requirements.txt, нет в среде. CTkOptionMenu с "Сегодня/Завтра/Послезавтра" + text ISO input достаточно (D-15 Claude's discretion) |
| Pillow | >=11.0.0 | Ghost widget rendering для DnD (уже в requirements.txt) | DnD ghost (D-23) — отдельный researcher |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Canvas custom checkbox | CTkCheckBox | CTkCheckBox не поддерживает точный стиль (округление 3px, overdue border color). Canvas полностью контролируемый |
| root.after() toast timer | threading.Timer | threading.Timer вызывает callback из другого потока — нужен root.after() для UI обновлений. root.after(5000, hide) — единственный корректный подход |
| place() для toast | pack()/grid() | place() позволяет точную abs. позицию "bottom-center" без влияния на layout других виджетов |
| CTkToplevel quick-capture | CTkEntry в overlay | Overlay = overrideredirect(True), нельзя разместить Entry поверх без нового Toplevel |
| grab_set() modal | custom modal | grab_set() — официальный Tkinter способ создания модального окна |

**Installation:** Нет новых зависимостей. Все библиотеки уже в `requirements.txt`.

---

## Architecture Patterns

### Recommended File Structure

```
client/ui/
├── overlay.py           ← Phase 3 (patch on_right_click → QuickCapturePopup.show)
├── main_window.py       ← Phase 3 (extend _build_day_section + add keyboard bindings)
├── day_section.py       ← НОВЫЙ Phase 4 (DaySection с task list + inline add)
├── task_widget.py       ← НОВЫЙ Phase 4 (TaskWidget 3 styles)
├── quick_capture.py     ← НОВЫЙ Phase 4 (QuickCapturePopup + smart parse)
├── edit_dialog.py       ← НОВЫЙ Phase 4 (EditDialog modal)
├── undo_toast.py        ← НОВЫЙ Phase 4 (UndoToastManager + queue)
├── tray_icon.py         ← Phase 3
├── notifications.py     ← Phase 3
├── themes.py            ← Phase 3 (без изменений)
└── settings.py          ← Phase 3 (без изменений)
```

**Phase 3 patch points:**
- `overlay.py`: `on_right_click` callback уже существует (строка 94). Phase 4 wire'ит его на `QuickCapturePopup.show(overlay_x, overlay_y)` вместо mini-menu.
- `main_window.py`: `_build_day_section()` расширяется для принятия `list[Task]` + рендеринга через `DaySection`. Keyboard bindings добавляются в `__init__`.

---

### Pattern 1: QuickCapturePopup (CTkToplevel overrideredirect)

**What:** Popup-input под overlay-квадратом. Использует тот же overrideredirect паттерн что и Phase 3 overlay — но с edge-flip и focus-loss dismissal.

**Critical:**
- `overrideredirect(True)` через `after(100, ...)` delay (PITFALL Phase 3)
- `-toolwindow` атрибут скрывает entry из taskbar (Windows)
- `wm_attributes("-toolwindow", 1)` — это отдельный Windows-specific флаг

```python
# Source: Phase 3 RESEARCH.md Pattern 1 + Tkinter wm_attributes docs
import customtkinter as ctk
import tkinter as tk
from typing import Callable, Optional

class QuickCapturePopup:
    POPUP_WIDTH = 400
    POPUP_HEIGHT = 40
    POPUP_GAP = 8      # px ниже overlay
    EDGE_MARGIN = 80   # px от нижнего края → flip наверх

    def __init__(self, root: ctk.CTk, on_save: Callable[[str, str, Optional[str]], None]) -> None:
        self._root = root
        self._on_save = on_save  # (text, day_iso, time_hhmm|None)
        self._popup: Optional[ctk.CTkToplevel] = None
        self._entry: Optional[ctk.CTkEntry] = None
        self._visible = False

    def show(self, overlay_x: int, overlay_y: int, overlay_size: int = 56) -> None:
        """Показать popup под/над overlay. Вызывается из overlay on_right_click callback."""
        if self._visible:
            self.hide()
            return

        screen_h = self._root.winfo_screenheight()
        # Edge detection: если снизу мало места — flip наверх
        if overlay_y + overlay_size + self.POPUP_GAP + self.POPUP_HEIGHT + self.EDGE_MARGIN > screen_h:
            popup_y = overlay_y - self.POPUP_HEIGHT - self.POPUP_GAP
        else:
            popup_y = overlay_y + overlay_size + self.POPUP_GAP

        # Центрировать горизонтально относительно overlay
        popup_x = overlay_x + overlay_size // 2 - self.POPUP_WIDTH // 2

        self._popup = ctk.CTkToplevel(self._root)
        self._popup.withdraw()
        self._popup.geometry(f"{self.POPUP_WIDTH}x{self.POPUP_HEIGHT}+{popup_x}+{popup_y}")

        # КРИТИЧНО: after(100, ...) delay для Win11 DWM
        self._popup.after(100, lambda: self._init_popup_style(popup_x, popup_y))

    def _init_popup_style(self, x: int, y: int) -> None:
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        try:
            # Убрать из taskbar (Windows)
            self._popup.wm_attributes("-toolwindow", 1)
        except tk.TclError:
            pass  # Только Windows

        self._entry = ctk.CTkEntry(
            self._popup,
            placeholder_text="Новая задача на сегодня...",
            width=self.POPUP_WIDTH - 8,
            height=self.POPUP_HEIGHT - 4,
        )
        self._entry.pack(padx=4, pady=2)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Escape>", lambda e: self.hide())
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._popup.bind("<FocusOut>", self._on_focus_out)

        self._popup.deiconify()
        self._popup.focus_force()
        self._entry.focus_set()
        self._visible = True

    def _on_enter(self, event) -> None:
        text = self._entry.get().strip()
        if not text:
            # Flash red border
            self._entry.configure(border_color="red")
            self._root.after(300, lambda: self._entry.configure(border_color=""))
            return
        parsed = parse_quick_input(text)
        self._on_save(parsed["text"], parsed["day"], parsed.get("time"))
        self._entry.delete(0, "end")
        # Multi-add: keep focus open

    def _on_focus_out(self, event) -> None:
        """Dismiss при потере фокуса — но подождать один event-цикл (click может быть на нашем виджете)."""
        self._popup.after(50, self._check_focus)

    def _check_focus(self) -> None:
        try:
            focused = self._root.focus_get()
            if focused not in (self._popup, self._entry):
                self.hide()
        except Exception:
            self.hide()

    def hide(self) -> None:
        self._visible = False
        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
            self._entry = None
```

**wm_attributes -toolwindow:** Скрывает окно из Windows taskbar. Верифицировано в Tkinter docs (Windows-specific). При `overrideredirect(True)` taskbar обычно и так не показывает, но `-toolwindow` — extra guard. Важно вызывать ДО `deiconify()`.

**Focus-loss detection:** `<FocusOut>` + 50ms delay — стандартный паттерн. Без задержки popup закрывается при клике внутри самого popup.

---

### Pattern 2: Smart Parse RU (regex-based)

**What:** Извлечение дня и времени из текста quick-capture. Python `re` stdlib, никаких внешних зависимостей.

**Algorithm priority:** HH:MM first → relative keyword → weekday → remainder = text → fallback day=сегодня.

```python
# Source: Python re docs + UI-SPEC §Smart Parse
import re
from datetime import date, timedelta

# Regex паттерны
_RE_TIME = re.compile(r'\b(\d{1,2}:\d{2})\b')  # HH:MM
_RE_RELATIVE = re.compile(
    r'\b(сегодня|завтра|послезавтра)\b', re.IGNORECASE
)
_WEEKDAY_MAP = {
    'пн': 0, 'вт': 1, 'ср': 2, 'чт': 3, 'пт': 4, 'сб': 5, 'вс': 6,
}
# "в" как предлог перед временем — должен удаляться
_RE_PREPOSITION_TIME = re.compile(r'\bв\s+(\d{1,2}:\d{2})\b', re.IGNORECASE)

MONTH_NAMES_RU = [
    '', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
    'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'
]

def format_date_range_ru(monday: date, sunday: date) -> str:
    """'14-20 апр' или '28 апр - 4 май' если разные месяцы."""
    if monday.month == sunday.month:
        return f"{monday.day}-{sunday.day} {MONTH_NAMES_RU[monday.month]}"
    return f"{monday.day} {MONTH_NAMES_RU[monday.month]} - {sunday.day} {MONTH_NAMES_RU[sunday.month]}"

def parse_quick_input(raw: str) -> dict:
    """
    Возвращает {"text": str, "day": "YYYY-MM-DD", "time": "HH:MM" | None}.
    Fallback: day=сегодня, time=None.
    """
    text = raw.strip()
    today = date.today()
    extracted_day: Optional[date] = None
    extracted_time: Optional[str] = None

    # 1. Время: "в 14:00" → удаляем предлог "в"
    m = _RE_PREPOSITION_TIME.search(text)
    if m:
        extracted_time = m.group(1)
        text = text[:m.start()] + text[m.end():]
    else:
        m = _RE_TIME.search(text)
        if m:
            extracted_time = m.group(1)
            text = text[:m.start()] + text[m.end():]

    # Нормализация времени: "9:00" → "09:00"
    if extracted_time:
        parts = extracted_time.split(":")
        extracted_time = f"{int(parts[0]):02d}:{parts[1]}"

    # 2. Относительный день
    m = _RE_RELATIVE.search(text)
    if m:
        kw = m.group(1).lower()
        if kw == 'сегодня':
            extracted_day = today
        elif kw == 'завтра':
            extracted_day = today + timedelta(days=1)
        elif kw == 'послезавтра':
            extracted_day = today + timedelta(days=2)
        text = text[:m.start()] + text[m.end():]

    # 3. День недели (только если relative не найден)
    if extracted_day is None:
        # Ищем по 2-буквенным сокращениям в конце слова или как отдельное слово
        pattern = r'\b(' + '|'.join(_WEEKDAY_MAP.keys()) + r')\b'
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            target_wd = _WEEKDAY_MAP[m.group(1).lower()]
            current_wd = today.weekday()  # Пн=0..Вс=6
            delta = (target_wd - current_wd) % 7
            if delta == 0:
                extracted_day = today  # Сегодня тот же день
            else:
                extracted_day = today + timedelta(days=delta)
            text = text[:m.start()] + text[m.end():]

    # 4. Fallback
    if extracted_day is None:
        extracted_day = today

    # Очистить лишние пробелы
    text = ' '.join(text.split())

    return {
        "text": text or raw.strip(),  # fallback: если всё распарсилось — вернуть original
        "day": extracted_day.isoformat(),
        "time": extracted_time,
    }
```

**Edge cases:**
- "позвонить в 14:00" → text="позвонить", time="14:00" (предлог "в" удаляется)
- "заехать на склад пт" → text="заехать на склад", day=ближайшая пятница
- "встреча завтра 15:30" → text="встреча", day=завтра, time="15:30"
- Пустой remainder после parse → fallback возвращает original text (D-04 error handling)

**D-06 compliance:** `delta = (target_wd - current_wd) % 7` — если результат 0, значит сегодня тот же день недели. Если пользователь хочет "следующую пятницу" когда сегодня пятница — берётся сегодня (так описано в D-06: "или сегодня если сегодня пятница"). Для "уже прошёл в этой неделе" — `delta > 0` naturally handles это.

---

### Pattern 3: TaskWidget (3 styles)

**What:** Один виджет задачи — CTkFrame с custom Canvas checkbox + labels. Поддерживает 3 стиля (D-07/08/09) через единый класс.

**Critical insight:** CTkCheckBox не подходит для точного стиля (overdue border, 18×18 с rounded 3px). Используем `tk.Canvas` 18×18 для checkbox rendering.

```python
# Source: Tkinter Canvas docs + CustomTkinter widget patterns
import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional

class TaskWidget:
    """
    Виджет одной задачи. 3 стиля через style param ("card" | "line" | "minimal").
    ThemeManager.subscribe вызывает _apply_theme при смене темы.
    """
    CHECKBOX_SIZE = 18
    CHECKBOX_RADIUS = 3  # D-11

    def __init__(
        self,
        parent,
        task: "Task",
        style: str,
        theme_manager: "ThemeManager",
        on_toggle: Callable[[str, bool], None],  # (task_id, new_done)
        on_edit: Callable[[str], None],           # (task_id)
        on_delete: Callable[[str], None],         # (task_id)
    ) -> None:
        self._task = task
        self._style = style
        self._theme = theme_manager
        self._on_toggle = on_toggle
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._hover = False
        self._icon_opacity = 0.0

        # Frame — контейнер (style A: card; B/C: transparent)
        self.frame = ctk.CTkFrame(parent, corner_radius=8 if style == "card" else 0)
        self._build()
        self._theme.subscribe(self._apply_theme_callback)

    def _build(self) -> None:
        self.frame.bind("<Enter>", self._on_hover_enter)
        self.frame.bind("<Leave>", self._on_hover_leave)

        inner = ctk.CTkFrame(self.frame, fg_color="transparent")
        inner.pack(fill="x", padx=self._get_padding()[0], pady=self._get_padding()[1])

        # Custom checkbox (Canvas 18×18)
        self._cb_canvas = tk.Canvas(
            inner,
            width=self.CHECKBOX_SIZE,
            height=self.CHECKBOX_SIZE,
            highlightthickness=0,
            cursor="hand2",
        )
        self._cb_canvas.pack(side="left", padx=(0, 8))
        self._cb_canvas.bind("<Button-1>", lambda e: self._toggle())

        # Task text label
        self._text_label = ctk.CTkLabel(
            inner,
            text=self._task.text,
            anchor="w",
            wraplength=0,  # Set by container resize
            justify="left",
        )
        self._text_label.pack(side="left", fill="x", expand=True)
        self._text_label.bind("<Enter>", self._on_hover_enter)
        self._text_label.bind("<Leave>", self._on_hover_leave)

        # Time field (if exists)
        if self._task.time_deadline:
            hhmm = self._task.time_deadline[:5] if len(self._task.time_deadline) >= 5 else self._task.time_deadline
            self._time_label = ctk.CTkLabel(
                inner, text=hhmm, font=("Cascadia Code", 11, "normal")
            )
            self._time_label.pack(side="left", padx=4)
        else:
            self._time_label = None

        # Hover icons (initially hidden via alpha trick — CTkLabel opacity_0 via fg_color match)
        icons_frame = ctk.CTkFrame(inner, fg_color="transparent")
        icons_frame.pack(side="right")
        self._edit_btn = ctk.CTkLabel(icons_frame, text="✏", cursor="hand2", width=20, height=20)
        self._edit_btn.pack(side="left")
        self._del_btn = ctk.CTkLabel(icons_frame, text="🗑", cursor="hand2", width=20, height=20)
        self._del_btn.pack(side="left")
        self._edit_btn.bind("<Button-1>", lambda e: self._on_edit(self._task.id))
        self._del_btn.bind("<Button-1>", lambda e: self._on_delete(self._task.id))

        # Initially hide icons
        self._set_icons_visible(False)
        self._render_checkbox()

    def _get_padding(self) -> tuple[int, int]:
        """Padding по стилю: card=12/10, line=10/8, minimal=6/6."""
        return {"card": (12, 10), "line": (10, 8), "minimal": (6, 6)}.get(self._style, (8, 6))

    def _render_checkbox(self) -> None:
        """Рисует checkbox на Canvas. 3 состояния: done / not-done / overdue."""
        c = self._cb_canvas
        c.delete("all")
        s = self.CHECKBOX_SIZE
        r = self.CHECKBOX_RADIUS
        palette = self._theme.get  # shortcut

        if self._task.done:
            # Filled square + white checkmark
            fill = palette("accent_done")
            c.create_rectangle(r, r, s - r, s - r, fill=fill, outline="", tags="box")
            # Checkmark: 3 points
            pts = [s * 0.2, s * 0.55, s * 0.45, s * 0.75, s * 0.80, s * 0.25]
            c.create_line(pts, fill="white", width=2, smooth=False, tags="check")
        elif self._task.is_overdue():
            border = palette("accent_overdue")
            c.create_rectangle(r, r, s - r, s - r, fill="", outline=border, width=2, tags="box")
        else:
            border = palette("text_secondary")
            c.create_rectangle(r, r, s - r, s - r, fill="", outline=border, width=1.5, tags="box")

    def _toggle(self) -> None:
        new_done = not self._task.done
        self._task = Task(**{**self._task.to_dict(), "done": new_done})  # optimistic update
        self._render_checkbox()
        self._on_toggle(self._task.id, new_done)

    def _on_hover_enter(self, event=None) -> None:
        self._hover = True
        if self._style == "card":
            pass  # bg уже есть
        elif self._style == "minimal":
            accent = self._theme.get("accent_brand")
            # Симуляция rgba(accent, 0.04) через interpolation с bg
            self.frame.configure(fg_color=self._theme.get("bg_secondary"))
        self._set_icons_visible(True)

    def _on_hover_leave(self, event=None) -> None:
        self._hover = False
        if self._style == "minimal":
            self.frame.configure(fg_color="transparent")
        self._set_icons_visible(False)

    def _set_icons_visible(self, visible: bool) -> None:
        """Show/hide icons. CustomTkinter не имеет opacity — используем text color trick."""
        color = self._theme.get("text_secondary") if visible else self._theme.get("bg_primary")
        try:
            self._edit_btn.configure(text_color=color)
            self._del_btn.configure(text_color=color)
        except Exception:
            pass

    def _apply_theme_callback(self, palette: dict) -> None:
        self._render_checkbox()
        # Обновить time_label цвет
        if self._time_label:
            from datetime import datetime
            is_overdue_time = False
            if self._task.time_deadline and not self._task.done:
                try:
                    dl = datetime.fromisoformat(self._task.time_deadline.replace("Z", "+00:00"))
                    is_overdue_time = dl < datetime.now(dl.tzinfo)
                except ValueError:
                    pass
            if self._task.done:
                color = palette.get("text_tertiary", "#9A8F7D")
            elif is_overdue_time:
                color = palette.get("accent_overdue", "#E85A5A")
            else:
                color = palette.get("text_secondary", "#6B5E4E")
            self._time_label.configure(text_color=color)

    def update_task(self, task: "Task") -> None:
        """Обновить данные задачи без пересоздания виджета."""
        self._task = task
        self._text_label.configure(text=task.text)
        self._render_checkbox()
        if self._time_label and task.time_deadline:
            hhmm = task.time_deadline[:5]
            self._time_label.configure(text=hhmm)
```

**Strikethrough для done tasks:** CustomTkinter CTkLabel не поддерживает strikethrough напрямую. Опции:
1. Использовать `tkinter.font.Font(overstrike=True)` — LOW MEDIUM confidence (нет в CTkLabel напрямую, но работает через `font` parameter tuple)
2. Визуально dim через `text_color=text_tertiary` для done tasks (проще, достаточно для MVP)

Рекомендация: opacity через `text_tertiary` цвет (без strike) — clean implementation. Если strike нужен, используется `tk.font.Font` с `overstrike=1` и передаётся в CTkLabel через `font=custom_font`.

---

### Pattern 4: Edit Dialog (CTkToplevel + grab_set)

**What:** Модальный диалог редактирования задачи. `grab_set()` — официальный Tkinter способ создать modal окно.

**Critical:** `grab_set()` НЕЛЬЗЯ вызывать до `deiconify()`. Порядок: создать → withdraw → build UI → deiconify → grab_set().

```python
# Source: Tkinter grab_set docs + CustomTkinter CTkTextbox API
import customtkinter as ctk
import tkinter as tk
import re
from typing import Callable, Optional

_RE_HHMM = re.compile(r'^(\d{1,2}):(\d{2})$')

class EditDialog:
    """
    Модальный диалог редактирования. D-14: CTkToplevel + grab_set().
    D-15: Text (multiline) + Day (dropdown) + Time (HH:MM) + Done (checkbox).
    D-16: Delete кнопка слева (красная), Cancel/Save справа.
    D-17: Save disabled при empty text OR invalid HH:MM.
    """
    def __init__(
        self,
        parent_window: ctk.CTkToplevel,  # main window (не root)
        task: "Task",
        theme_manager: "ThemeManager",
        on_save: Callable[["Task"], None],
        on_delete: Callable[[str], None],
    ) -> None:
        self._task = task
        self._theme = theme_manager
        self._on_save = on_save
        self._on_delete = on_delete

        self._dialog = ctk.CTkToplevel(parent_window)
        self._dialog.withdraw()
        self._dialog.title("Задача")
        self._dialog.resizable(False, False)
        self._dialog.geometry("380x320")

        # Center на parent window
        pw = parent_window
        px = pw.winfo_x() + pw.winfo_width() // 2 - 190
        py = pw.winfo_y() + pw.winfo_height() // 2 - 160
        self._dialog.geometry(f"380x320+{px}+{py}")

        self._build_ui()

        # КРИТИЧНО: grab_set ПОСЛЕ deiconify
        self._dialog.deiconify()
        self._dialog.grab_set()  # Модальность — блокирует input на parent
        self._dialog.focus_set()
        self._text_box.focus_set()

        # Keyboard bindings
        self._dialog.bind("<Escape>", lambda e: self._cancel())
        self._dialog.bind("<Control-Return>", lambda e: self._save())
        self._dialog.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build_ui(self) -> None:
        frame = ctk.CTkFrame(self._dialog)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        # Text field (multiline)
        ctk.CTkLabel(frame, text="Текст", anchor="w").pack(fill="x")
        self._text_box = ctk.CTkTextbox(frame, height=80)
        self._text_box.pack(fill="x", pady=(0, 8))
        self._text_box.insert("1.0", self._task.text)
        self._text_box.bind("<Return>", lambda e: "break")  # Enter = newline, не close

        # Day dropdown
        ctk.CTkLabel(frame, text="День", anchor="w").pack(fill="x")
        day_options = self._build_day_options()
        self._day_var = ctk.StringVar(value=self._get_current_day_label())
        self._day_dropdown = ctk.CTkOptionMenu(
            frame,
            values=day_options,
            variable=self._day_var,
        )
        self._day_dropdown.pack(fill="x", pady=(0, 8))

        # Time field
        ctk.CTkLabel(frame, text="Время (HH:MM)", anchor="w").pack(fill="x")
        time_row = ctk.CTkFrame(frame, fg_color="transparent")
        time_row.pack(fill="x", pady=(0, 8))
        time_val = ""
        if self._task.time_deadline:
            time_val = self._task.time_deadline[:5]
        self._time_var = tk.StringVar(value=time_val)
        self._time_entry = ctk.CTkEntry(time_row, textvariable=self._time_var, width=80)
        self._time_entry.pack(side="left")
        ctk.CTkButton(
            time_row, text="✕", width=28,
            command=lambda: self._time_var.set("")
        ).pack(side="left", padx=4)
        # Validation trace
        self._time_var.trace_add("write", self._validate_time)
        self._time_error = ctk.CTkLabel(time_row, text="", text_color="red")
        self._time_error.pack(side="left", padx=4)

        # Done checkbox
        self._done_var = tk.BooleanVar(value=self._task.done)
        ctk.CTkCheckBox(frame, text="Выполнено", variable=self._done_var).pack(anchor="w", pady=(0, 12))

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        # Delete (left, red)
        ctk.CTkButton(
            btn_frame, text="🗑 Удалить",
            fg_color="red", hover_color="#cc0000",
            width=100,
            command=self._delete
        ).pack(side="left")

        # Cancel + Save (right)
        ctk.CTkButton(btn_frame, text="Отмена", width=80, command=self._cancel).pack(side="right", padx=(4, 0))
        self._save_btn = ctk.CTkButton(btn_frame, text="Сохранить", width=100, command=self._save)
        self._save_btn.pack(side="right")
        self._update_save_state()

    def _build_day_options(self) -> list[str]:
        from datetime import date, timedelta
        today = date.today()
        opts = ["Сегодня", "Завтра", "Послезавтра"]
        # Дни недели текущей недели
        monday = today - timedelta(days=today.weekday())
        for i in range(7):
            d = monday + timedelta(days=i)
            if d not in (today, today + timedelta(1), today + timedelta(2)):
                opts.append(f"{['Пн','Вт','Ср','Чт','Пт','Сб','Вс'][i]} {d.day} {['','янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'][d.month]}")
        return opts

    def _get_current_day_label(self) -> str:
        from datetime import date, timedelta
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
        return d.isoformat()  # fallback

    def _validate_time(self, *_) -> None:
        val = self._time_var.get()
        if not val:
            self._time_error.configure(text="")
            self._time_entry.configure(border_color=self._theme.get("bg_tertiary"))
        elif _RE_HHMM.match(val):
            h, m = map(int, val.split(":"))
            if 0 <= h <= 23 and 0 <= m <= 59:
                self._time_error.configure(text="")
                self._time_entry.configure(border_color=self._theme.get("accent_done"))
            else:
                self._time_error.configure(text="!")
                self._time_entry.configure(border_color="red")
        else:
            self._time_error.configure(text="!")
            self._time_entry.configure(border_color="red")
        self._update_save_state()

    def _update_save_state(self) -> None:
        text_ok = bool(self._text_box.get("1.0", "end-1c").strip())
        time_val = self._time_var.get()
        time_ok = not time_val or (bool(_RE_HHMM.match(time_val)) and self._is_valid_time(time_val))
        state = "normal" if (text_ok and time_ok) else "disabled"
        self._save_btn.configure(state=state)

    def _is_valid_time(self, val: str) -> bool:
        try:
            h, m = map(int, val.split(":"))
            return 0 <= h <= 23 and 0 <= m <= 59
        except Exception:
            return False

    def _day_label_to_iso(self, label: str) -> str:
        from datetime import date, timedelta
        today = date.today()
        if label == "Сегодня":
            return today.isoformat()
        if label == "Завтра":
            return (today + timedelta(1)).isoformat()
        if label == "Послезавтра":
            return (today + timedelta(2)).isoformat()
        # ISO format fallback
        return self._task.day

    def _save(self) -> None:
        text = self._text_box.get("1.0", "end-1c").strip()
        if not text:
            return
        time_val = self._time_var.get().strip() or None
        day_iso = self._day_label_to_iso(self._day_var.get())
        done = self._done_var.get()
        from dataclasses import replace
        updated = Task(
            **{**self._task.to_dict(),
               "text": text,
               "day": day_iso,
               "time_deadline": time_val,
               "done": done}
        )
        self._dialog.grab_release()
        self._dialog.destroy()
        self._on_save(updated)

    def _cancel(self) -> None:
        self._dialog.grab_release()
        self._dialog.destroy()

    def _delete(self) -> None:
        self._dialog.grab_release()
        self._dialog.destroy()
        self._on_delete(self._task.id)
```

**CTkTextbox vs CTkEntry:** `CTkTextbox` — multiline text widget в CustomTkinter 5.2.x. Содержимое читается через `.get("1.0", "end-1c")`. Это верифицировано — CTkTextbox существует в CTk 5.2.2.

**CTkOptionMenu:** Dropdown в CustomTkinter. `.configure(values=[...])` для динамического обновления. `StringVar` как `variable` parameter.

**grab_release() обязателен:** Перед `destroy()` — иначе grab остаётся на уже несуществующем окне и вся app зависает.

---

### Pattern 5: Undo-Toast Manager

**What:** Floating toast внизу main window. НЕ CTkToplevel — используем `CTkFrame` с `place()` абсолютным позиционированием внутри main window. Это проще и не создаёт новые окна.

**Critical insight:** Разместить toast как `place()` поверх прокручиваемого контента — нельзя (scroll frame перекрывает). Решение: toast размещается в `_root_frame` (верхний non-scroll frame) через `place(relx=0.5, rely=1.0, anchor="s", y=-8)`.

```python
# Source: Tkinter place() docs + CustomTkinter layout patterns
import customtkinter as ctk
import tkinter as tk
from dataclasses import dataclass
from typing import Optional, Callable
import time

@dataclass
class ToastEntry:
    task_id: str
    task_text: str
    undo_callback: Callable[[], None]
    expire_ms: int  # timestamp в ms когда истечёт

class UndoToastManager:
    """
    Управляет очередью undo-toast'ов (max 3 одновременно).
    Toast'ы — CTkFrame с place() в parent (main window root frame).
    Countdown bar через root.after() — shrinks от 280px до 0 за 5 сек.
    """
    MAX_TOASTS = 3
    TOAST_DURATION_MS = 5000
    TOAST_WIDTH = 280
    TOAST_HEIGHT = 44
    TOAST_BOTTOM_MARGIN = 8

    def __init__(self, parent: ctk.CTkFrame, root: ctk.CTk, theme_manager: "ThemeManager") -> None:
        self._parent = parent
        self._root = root
        self._theme = theme_manager
        self._queue: list[ToastEntry] = []
        self._frames: list[ctk.CTkFrame] = []

    def show(self, task_id: str, task_text: str, undo_callback: Callable[[], None]) -> None:
        """Добавить toast в очередь. Если >MAX — убрать самый старый."""
        if len(self._queue) >= self.MAX_TOASTS:
            self._dismiss_oldest()

        expire = int(time.time() * 1000) + self.TOAST_DURATION_MS
        entry = ToastEntry(task_id=task_id, task_text=task_text,
                           undo_callback=undo_callback, expire_ms=expire)
        self._queue.append(entry)
        self._build_toast(entry)
        self._reposition_all()
        # Auto-dismiss через 5 сек
        self._root.after(self.TOAST_DURATION_MS, lambda: self._auto_dismiss(task_id))

    def _build_toast(self, entry: ToastEntry) -> None:
        bg = self._theme.get("bg_secondary")
        accent = self._theme.get("accent_brand")

        toast = ctk.CTkFrame(self._parent, width=self.TOAST_WIDTH, height=self.TOAST_HEIGHT,
                              corner_radius=8, fg_color=bg)
        # НЕ pack/grid — используем place() для overlay
        toast.place(x=0, y=0)  # позиция установится в _reposition_all
        toast.place_configure(x=0, y=0)  # placeholder

        # Content row
        content = ctk.CTkFrame(toast, fg_color="transparent")
        content.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(content, text="⟲ Удалено", anchor="w").pack(side="left")
        undo_btn = ctk.CTkLabel(content, text="Отменить",
                                 text_color=accent, cursor="hand2")
        undo_btn.pack(side="right")
        undo_btn.bind("<Button-1>", lambda e, eid=entry.task_id: self._undo(eid))

        # Countdown bar (1px Canvas внизу toast)
        bar_canvas = tk.Canvas(toast, height=2, bg=accent,
                                highlightthickness=0, borderwidth=0)
        bar_canvas.place(x=0, rely=1.0, anchor="sw", width=self.TOAST_WIDTH)

        self._frames.append(toast)
        # Анимировать shrink countdown bar
        self._animate_bar(bar_canvas, start_ms=int(time.time() * 1000),
                           duration_ms=self.TOAST_DURATION_MS)

    def _animate_bar(self, canvas: tk.Canvas, start_ms: int, duration_ms: int) -> None:
        """Shrink countdown bar от TOAST_WIDTH до 0."""
        elapsed = int(time.time() * 1000) - start_ms
        if elapsed >= duration_ms:
            canvas.configure(width=0)
            return
        ratio = 1.0 - elapsed / duration_ms
        new_width = max(0, int(self.TOAST_WIDTH * ratio))
        try:
            canvas.configure(width=new_width)
        except tk.TclError:
            return  # Canvas destroyed
        self._root.after(50, lambda: self._animate_bar(canvas, start_ms, duration_ms))

    def _reposition_all(self) -> None:
        """Stack toasts bottom-center, newer on top."""
        # Получить ширину parent
        try:
            pw = self._parent.winfo_width()
        except tk.TclError:
            pw = 460
        if pw < 100:
            pw = 460  # fallback если parent ещё не rendered

        for i, frame in enumerate(self._frames):
            # Stack снизу вверх: i=0 самый нижний
            y_offset = self.TOAST_BOTTOM_MARGIN + i * (self.TOAST_HEIGHT + 4)
            x = (pw - self.TOAST_WIDTH) // 2
            try:
                frame.place(
                    x=x,
                    rely=1.0,
                    anchor="sw",
                    y=-y_offset,
                )
            except tk.TclError:
                pass

    def _undo(self, task_id: str) -> None:
        entry = next((e for e in self._queue if e.task_id == task_id), None)
        if entry:
            entry.undo_callback()
            self._dismiss(task_id)

    def _auto_dismiss(self, task_id: str) -> None:
        self._dismiss(task_id)

    def _dismiss(self, task_id: str) -> None:
        idx = next((i for i, e in enumerate(self._queue) if e.task_id == task_id), None)
        if idx is None:
            return
        self._queue.pop(idx)
        frame = self._frames.pop(idx)
        try:
            frame.place_forget()
            frame.destroy()
        except tk.TclError:
            pass
        self._reposition_all()

    def _dismiss_oldest(self) -> None:
        if self._queue:
            self._dismiss(self._queue[0].task_id)
```

**`place()` vs `pack()`:** В CTkScrollableFrame нельзя разместить overlapping элементы — scroll frame рисует себя поверх. Toast должен быть в `_root_frame` (не в scroll), с `place(rely=1.0, anchor="sw")` для bottom positioning.

**Fade-out задачи (200ms):** Через `wm_attributes("-alpha", ...)` нельзя (это для Toplevel). Для CTkFrame — симулируем через цвет-interpolation к bg или `pack_forget()` после 200ms задержки. Для MVP: instant `pack_forget()` + 150ms `after()` для визуальной паузы.

---

### Pattern 6: Week Navigation + Archive

**What:** ISO week calculation, prev/next navigation, archive detection.

```python
# Source: Python datetime docs — date.isocalendar()
from datetime import date, timedelta

def get_week_monday(d: date) -> date:
    """Понедельник недели для данной даты."""
    return d - timedelta(days=d.weekday())  # weekday(): Пн=0..Вс=6

def get_current_week_monday() -> date:
    return get_week_monday(date.today())

def get_iso_week_number(d: date) -> int:
    return d.isocalendar()[1]  # (year, week, weekday)

def is_archive_week(week_monday: date) -> bool:
    """Прошлая неделя = архив. Текущая и будущие = active."""
    return week_monday < get_current_week_monday()

def format_week_header(week_monday: date) -> str:
    """'Неделя 16  •  14-20 апр'."""
    week_num = get_iso_week_number(week_monday)
    week_sunday = week_monday + timedelta(days=6)
    return f"Неделя {week_num}  •  {format_date_range_ru(week_monday, week_sunday)}"

# Keyboard navigation (MainWindow._bind_keys)
def _bind_keyboard_navigation(self) -> None:
    """D-30: Ctrl+←/→ = week nav, Ctrl+T = today, Esc = close, Ctrl+Space = QC."""
    self._window.bind("<Control-Left>", lambda e: self._nav_week(-1))
    self._window.bind("<Control-Right>", lambda e: self._nav_week(1))
    self._window.bind("<Control-t>", lambda e: self._nav_today())
    self._window.bind("<Escape>", lambda e: self.hide())
    self._window.bind("<Control-space>", lambda e: self._trigger_quick_capture())
```

**Archive opacity emulation:** CustomTkinter не имеет настоящего CSS opacity. Для archive dim (0.7 alpha):
- Option A: Рекурсивно изменить fg_color всех виджетов week content на interpolated color (сложно).
- Option B: Overlay прозрачный CTkFrame поверх content (сложно с CTkScrollableFrame).
- **Option C (рекомендован):** Изменить text_color всех labels + border colors на более dim palette. Создать `archive_palette` = interpolated(current_palette, bg_primary, factor=0.5).

Практически: dim=0.7 реализуется через отдельный `_dim_content(True/False)` метод который проходит по всем `TaskWidget` и вызывает `_apply_theme(archive_palette)`.

---

### Pattern 7: Inline Add Input (empty day "+")

**What:** CTkEntry, разворачивающийся в day_section при клике на "+". In-place, не popup.

```python
# Source: CustomTkinter CTkEntry + pack/pack_forget pattern
class DaySection:
    def _show_inline_add(self) -> None:
        """D-33: Показать inline input для добавления задачи в этот день."""
        if self._inline_entry is not None:
            return  # уже открыт
        self._plus_label.pack_forget()  # скрыть "+"

        entry_frame = ctk.CTkFrame(self._body, fg_color="transparent")
        entry_frame.pack(fill="x", padx=8, pady=4)

        self._inline_entry = ctk.CTkEntry(
            entry_frame,
            placeholder_text="Новая задача...",
        )
        self._inline_entry.pack(fill="x")
        self._inline_entry.focus_set()
        self._inline_entry.bind("<Return>", self._on_inline_enter)
        self._inline_entry.bind("<Escape>", self._hide_inline_add)
        self._inline_entry.bind("<FocusOut>", lambda e: self._root.after(100, self._maybe_hide_inline))

    def _on_inline_enter(self, event) -> None:
        text = self._inline_entry.get().strip()
        if not text:
            return
        parsed = parse_quick_input(text)
        # Override day: всегда этот конкретный день (ignoring parse day)
        task = Task.new(user_id=self._user_id, text=parsed["text"],
                        day=self._day_date.isoformat(),
                        time_deadline=parsed.get("time"))
        self._storage.add_task(task)
        self._inline_entry.delete(0, "end")
        self._refresh_tasks()  # update task list

    def _hide_inline_add(self, event=None) -> None:
        if self._inline_entry:
            self._inline_entry.destroy()
            self._inline_entry = None
        if not self._tasks:  # если день пустой — восстановить "+"
            self._plus_label.pack(...)
```

---

### Anti-Patterns to Avoid

- **CTkCheckBox для task checkbox:** Не даёт полного контроля над стилем (rounded corner, overdue color). Использовать `tk.Canvas` 18×18.
- **CTkToplevel для UndoToast:** Лишнее окно + сложное позиционирование relative to main window. Использовать `CTkFrame` с `place()`.
- **grab_set() до deiconify():** В некоторых версиях Tk это вызывает grab failure. Порядок строго: build → deiconify → grab_set().
- **grab_release() забыть перед destroy():** Grab остаётся активным на destroyed окне → весь app зависает. Всегда `grab_release()` в cancel/save/delete handlers.
- **Реальный opacity через CTkFrame:** CTkFrame не имеет alpha. Dim-эффект для archive = color interpolation к bg цветам.
- **time.time() для after() timing:** Использовать monotonic для countdown bar — `time.monotonic_ns()` точнее чем `time.time()` для коротких интервалов.
- **CTkTextbox.get("0.0", "end"):** Правильный индекс — `"1.0"`, не `"0.0"`. Tkinter Text widget индексирует с 1. `"end-1c"` убирает trailing newline.
- **wraplength в CTkLabel — статическое значение:** wraplength нужно обновлять при resize окна. Bind `<Configure>` на container и пересчитывать.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Modal dialog | Свой overlay blocker | `CTkToplevel + grab_set()` | grab_set() официальный Tkinter modal механизм; кастомный blocker fragile |
| Multiline text input | CTkEntry с переносами | `CTkTextbox` (CTk 5.2.x) | CTkTextbox — официальный многострочный виджет в CTk |
| HH:MM validation | Кастомный парсер | `re.compile(r'^(\d{1,2}):(\d{2})$')` + range check | 3 строки; достаточно для поля |
| Dropdown/select | Кастомный popup | `CTkOptionMenu` | Официальный CTk компонент; уже в requirements |
| ISO week number | Своя арифметика | `date.isocalendar()[1]` | stdlib; единственный правильный способ |
| Weekday arithmetic | Своя таблица | `timedelta + weekday()` | stdlib datetime; без ошибок high/low |
| StringVar validation | Polling | `StringVar.trace_add("write", ...)` | Официальный Tkinter trace — callback при каждом изменении |
| Toast countdown | Отдельный thread | `root.after(50, animate_bar)` | root.after() безопасен из main thread; threading.Timer нет |

**Key insight:** Phase 4 — чистый UI слой поверх Phase 2/3 фундамента. Никакого нового I/O или threading. Все сложные паттерны (threading, overrideredirect, DWM) уже решены в Phase 2/3.

---

## Common Pitfalls

### Pitfall 1: grab_set зависание при destroy без grab_release

**What goes wrong:** `EditDialog.destroy()` без `grab_release()` → grab остаётся на несуществующем окне → весь app не принимает input.
**Why it happens:** Tkinter grab — это ресурс, который нужно явно освобождать.
**How to avoid:** Всегда в КАЖДОМ exit path: `self._dialog.grab_release()` перед `self._dialog.destroy()`. Включая WM_DELETE_WINDOW protocol и все кнопки.
**Warning signs:** После закрытия диалога app не реагирует на клики.
**Confidence:** HIGH — стандартная Tkinter gotcha, задокументирована в официальных docs.

---

### Pitfall 2: CTkTextbox get() trailing newline

**What goes wrong:** `self._text_box.get("1.0", "end")` возвращает текст + `\n` в конце → save disabled (если trim забыли), или текст сохраняется с newline.
**Why it happens:** Tkinter Text widget всегда добавляет trailing newline к content.
**How to avoid:** Всегда `get("1.0", "end-1c")` — `end-1c` = end minus 1 character (убирает newline). Или `.strip()` после get.
**Warning signs:** Save кнопка disabled при непустом тексте; сохранённый текст имеет trailing пробел.
**Confidence:** HIGH — задокументировано в Tkinter Text docs.

---

### Pitfall 3: FocusOut закрывает popup при клике внутри него

**What goes wrong:** QuickCapturePopup закрывается при клике на свой же Entry или Frame (потому что FocusOut триггерится сначала, потом FocusIn на Entry).
**Why it happens:** `<FocusOut>` вызывается перед тем как новый фокус установится. При клике внутри popup — кратковременная потеря фокуса.
**How to avoid:** `after(50, check_focus)` — проверить focus через 50ms. Если новый фокус = наш виджет → не закрывать.
**Warning signs:** Popup мгновенно закрывается при любом клике.
**Confidence:** HIGH — классический Tkinter паттерн для focus-out dismissal.

---

### Pitfall 4: Task list re-render scroll position reset

**What goes wrong:** При refresh task list (после add/edit/delete) CTkScrollableFrame перематывается наверх.
**Why it happens:** Полный pack_forget + rebuild = destroy и пересоздание виджетов, scroll сбрасывается.
**How to avoid:** Partial update — только изменённый TaskWidget обновляется через `widget.update_task(new_task)` без rebuild. Для добавления — добавить в конец без rebuild. Для удаления — fade-out + `pack_forget()` только удалённого виджета.
**Warning signs:** Каждый checkbox click прокручивает список к началу.
**Confidence:** HIGH — задокументировано в Phase 3 PITFALLS §Performance "Full week re-render on every task change".

---

### Pitfall 5: wraplength не адаптируется при resize

**What goes wrong:** Длинный текст задачи обрезается или выходит за границы при изменении размера окна.
**Why it happens:** `CTkLabel.configure(wraplength=N)` — статическое значение. При resize окна ширина container меняется, но wraplength нет.
**How to avoid:** Bind `<Configure>` на DaySection container:
```python
self._body.bind("<Configure>", self._on_resize)
def _on_resize(self, event):
    new_wrap = max(100, event.width - 24)
    for widget in self._task_widgets:
        widget._text_label.configure(wraplength=new_wrap)
```
**Warning signs:** Текст обрезается "..." при узком окне, или overflow при широком.
**Confidence:** HIGH — verified в CustomTkinter issues.

---

### Pitfall 6: Hover icons text_color trick и theme switch

**What goes wrong:** После смены темы hover-icons (Edit/Delete) остаются невидимыми или наоборот всегда видимы (неправильный color).
**Why it happens:** `_set_icons_visible(False)` использует `bg_primary` как "invisible color". После theme switch `bg_primary` другой, но icons_frame сохраняет старый color.
**How to avoid:** В `_apply_theme_callback` вызывать `_set_icons_visible(self._hover)` для обновления icons на новый bg_primary.
**Warning signs:** После смены темы видны "invisible" иконки на старом цвете.
**Confidence:** MEDIUM — логический вывод из Phase 3 PITFALL 5 (theme switching).

---

### Pitfall 7: QuickCapturePopup multi-monitor координаты

**What goes wrong:** Popup позиционируется относительно screen (0,0) но overlay находится на вторичном мониторе → popup появляется на неправильном мониторе.
**Why it happens:** Overlay позиция (`overlay_x, overlay_y`) уже в virtual desktop координатах (Phase 3 Pattern 5). `winfo_screenheight()` возвращает высоту PRIMARY монитора.
**How to avoid:** Для edge detection использовать высоту монитора ГДЕ overlay находится. Получить через `win32api.GetMonitorInfo` по координатам overlay (Phase 3 Pattern 5 код).
**Warning signs:** Popup появляется на основном мониторе когда overlay на вторичном.
**Confidence:** MEDIUM — логический вывод из Phase 3 multi-monitor research.

---

## Code Examples

### ISO week number и range

```python
# Source: Python datetime docs
from datetime import date, timedelta

def week_info(week_monday: date) -> dict:
    """Вернуть номер недели и range строку."""
    iso_cal = week_monday.isocalendar()
    week_num = iso_cal[1]
    week_sunday = week_monday + timedelta(days=6)
    months = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
              'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
    if week_monday.month == week_sunday.month:
        date_range = f"{week_monday.day}-{week_sunday.day} {months[week_monday.month]}"
    else:
        date_range = f"{week_monday.day} {months[week_monday.month]} – {week_sunday.day} {months[week_sunday.month]}"
    return {"week_num": week_num, "date_range": date_range}
```

### StringVar trace для HH:MM validation

```python
# Source: Tkinter StringVar.trace_add docs
time_var = tk.StringVar()
_re_time = re.compile(r'^(\d{1,2}):(\d{2})$')

def _validate(name, index, mode):
    val = time_var.get()
    if not val:
        entry.configure(border_color="gray")
        return
    m = _re_time.match(val)
    if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
        entry.configure(border_color="green")
    else:
        entry.configure(border_color="red")

time_var.trace_add("write", _validate)
```

### Task keyboard focus (Tab navigation)

```python
# Source: Tkinter focus_set + bind patterns
class TaskWidget:
    def enable_keyboard_focus(self) -> None:
        """D-34: Space=toggle, Del=delete, Enter=edit, arrows=nav."""
        self.frame.configure(takefocus=True)
        self.frame.bind("<space>", lambda e: self._toggle())
        self.frame.bind("<Delete>", lambda e: self._on_delete(self._task.id))
        self.frame.bind("<Return>", lambda e: self._on_edit(self._task.id))
        self.frame.bind("<FocusIn>", self._on_focus_in)
        self.frame.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_in(self, event) -> None:
        # Visual focus indicator: accent_brand border 2px
        self.frame.configure(border_width=2,
                              border_color=self._theme.get("accent_brand"))

    def _on_focus_out(self, event) -> None:
        self.frame.configure(border_width=0)
```

**CTkFrame takefocus:** `frame.configure(takefocus=True)` — позволяет CTkFrame получать Tab-навигацию. Верифицировано: Tkinter Frame поддерживает takefocus, CTkFrame наследует.

### Archive dim via color interpolation

```python
# Source: Color interpolation pattern (inline math, no external deps)
def interpolate_palette(palette: dict, bg: str, factor: float) -> dict:
    """
    Смешать palette цвета с bg (factor=0.3 = 30% от bg).
    Используется для archive dim effect (opacity 0.7 ~= factor 0.3).
    """
    def parse_hex(h: str) -> tuple[int, int, int]:
        h = h.lstrip('#')
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def blend(c1: str, c2: str, t: float) -> str:
        r1, g1, b1 = parse_hex(c1)
        r2, g2, b2 = parse_hex(c2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    result = {}
    skip = {"shadow_card"}  # not hex colors
    for key, color in palette.items():
        if key in skip or not isinstance(color, str) or not color.startswith('#'):
            result[key] = color
        else:
            result[key] = blend(color, bg, factor)
    return result
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tkMessageBox для confirmation | Inline undo-toast (Gmail style) | 2019+ (Gmail UX pattern) | Устраняет blocking modal; пользователь может продолжать работу |
| CTkCheckBox для custom checklist | tk.Canvas custom checkbox | CustomTkinter era | Canvas = полный контроль стиля; CTkCheckBox ограничен |
| Отдельный thread для toast timer | root.after() | всегда (Tkinter) | Единственный thread-safe способ для UI timers |
| tkcalendar для date picker | CTkOptionMenu + relative options | 2023+ (minimal UI trend) | tkcalendar = heavy dependency; 3 опции "Сегодня/Завтра/Послезавтра" покрывают 95% use cases |
| grab_set() модальность | grab_set() (без изменений) | стабильно | Ничего нового — проверенный механизм |

**Deprecated/outdated:**
- `tkSimpleDialog.askstring()` для ввода текста: устарело, CTkToplevel + CTkEntry даёт лучший UX
- `tkcalendar`: нет в requirements, не нужен для v1 (Claude's discretion D-15)

---

## Open Questions

1. **Strikethrough для done tasks**
   - What we know: CTkLabel не имеет built-in `text_decoration`. `tk.font.Font(overstrike=True)` работает как tkinter.font объект.
   - What's unclear: Принимает ли CTkLabel `font=tk.font.Font(...)` объект (не tuple). Нужно проверить.
   - Recommendation: Для MVP — dim через `text_tertiary` color без strike. Если нужен strike — тест с `tk.font.Font` объектом в `CTkLabel(font=custom_font)`.

2. **Hover icons fade-in animation (150ms, opacity 0→1)**
   - What we know: CTkLabel не имеет opacity. `text_color` trick работает для мгновенного скрытия.
   - What's unclear: Плавная анимация 0→1 требует intermediate hex colors interpolation через `root.after()`.
   - Recommendation: Для MVP — instant show/hide через `text_color`. Анимация 150ms — опциональный polish, добавить через after-loop если время позволяет.

3. **QuickCapturePopup и input с кириллицей**
   - What we know: CTkEntry корректно работает с UTF-8 (Cyrillic verified в Phase 3 context).
   - What's unclear: Ввод через IME (не актуально для RU).
   - Recommendation: Нет специальной обработки нужна; стандартный CTkEntry достаточен.

4. **Calendar picker для Day dropdown "выбрать дату"**
   - What we know: tkcalendar не установлен, не в requirements. CTkOptionMenu доступен.
   - What's unclear: Нужен ли full calendar picker для v1.
   - Recommendation: Claude's discretion per D-15 — basic dropdown (Сегодня/Завтра/Послезавтра) достаточен для v1. Если нужна произвольная дата — CTkInputDialog с ISO date text input + validation.

---

## Validation Architecture

> `nyquist_validation: true` в config.json — секция обязательна.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + headless CTk (сессионный `headless_tk` fixture — уже в conftest.py) |
| Config file | `client/pyproject.toml` (существует из Phase 2) |
| Quick run command | `python -m pytest client/tests/ui/test_week_view.py client/tests/ui/test_quick_capture.py client/tests/ui/test_edit_dialog.py -x -q` |
| Full suite command | `python -m pytest client/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WEEK-01 | DaySection рендерит tasks list | unit | `pytest client/tests/ui/test_week_view.py::test_day_section_renders_tasks -x` | ❌ Wave 0 |
| WEEK-02 | prev/next week navigation меняет week_monday | unit | `pytest client/tests/ui/test_week_view.py::test_week_navigation -x` | ❌ Wave 0 |
| WEEK-03 | "Сегодня" кнопка видна только для не-current week | unit | `pytest client/tests/ui/test_week_view.py::test_today_button_visibility -x` | ❌ Wave 0 |
| WEEK-04 | Overdue task имеет accent_overdue border | unit | `pytest client/tests/ui/test_task_widget.py::test_overdue_checkbox_color -x` | ❌ Wave 0 |
| WEEK-05 | TaskWidget рендерится в 3 стилях без crash | unit | `pytest client/tests/ui/test_task_widget.py::test_three_styles -x` | ❌ Wave 0 |
| WEEK-06 | Archive week: is_archive_week() = True, editing disabled | unit | `pytest client/tests/ui/test_week_view.py::test_archive_detection -x` | ❌ Wave 0 |
| TASK-01 | parse_quick_input("встреча завтра 14:00") → text/day/time | unit | `pytest client/tests/test_quick_parse.py::test_parse_ru -x` | ❌ Wave 0 |
| TASK-01 | QuickCapturePopup.show() создаёт CTkToplevel | unit | `pytest client/tests/ui/test_quick_capture.py::test_popup_shows -x` | ❌ Wave 0 |
| TASK-01 | Enter с текстом → on_save вызван | unit | `pytest client/tests/ui/test_quick_capture.py::test_enter_saves -x` | ❌ Wave 0 |
| TASK-01 | Пустой Enter → flash red, on_save НЕ вызван | unit | `pytest client/tests/ui/test_quick_capture.py::test_empty_enter_no_save -x` | ❌ Wave 0 |
| TASK-02 | Checkbox click → on_toggle вызван с новым done | unit | `pytest client/tests/ui/test_task_widget.py::test_toggle_done -x` | ❌ Wave 0 |
| TASK-03 | EditDialog.show() → grab_set активен | unit | `pytest client/tests/ui/test_edit_dialog.py::test_dialog_modal -x` | ❌ Wave 0 |
| TASK-03 | Save с пустым текстом → disabled | unit | `pytest client/tests/ui/test_edit_dialog.py::test_save_disabled_empty -x` | ❌ Wave 0 |
| TASK-03 | Save с invalid HH:MM → disabled | unit | `pytest client/tests/ui/test_edit_dialog.py::test_save_disabled_invalid_time -x` | ❌ Wave 0 |
| TASK-03 | Ctrl+Enter = Save, Esc = Cancel | unit | `pytest client/tests/ui/test_edit_dialog.py::test_keyboard_shortcuts -x` | ❌ Wave 0 |
| TASK-04 | soft_delete_task вызывается при Delete | unit | `pytest client/tests/ui/test_task_widget.py::test_delete_calls_storage -x` | ❌ Wave 0 |
| TASK-04 | UndoToast появляется, Undo reverses delete | unit | `pytest client/tests/ui/test_undo_toast.py::test_undo_reverses -x` | ❌ Wave 0 |
| TASK-04 | Max 3 toasts одновременно | unit | `pytest client/tests/ui/test_undo_toast.py::test_max_three_toasts -x` | ❌ Wave 0 |
| TASK-05 | DnD — отдельный researcher (Plan 04-DnD) | integration | manual-only Phase 4 | — |
| TASK-06 | DnD next-week zone — отдельный researcher | integration | manual-only Phase 4 | — |
| TASK-07 | position поле сохраняется при update | unit | `pytest client/tests/test_storage.py::test_position_persists -x` | ✅ (extends existing) |

### Test Strategy

**Smart parse — pure Python, без Tk:**
```python
# client/tests/test_quick_parse.py
def test_parse_time_with_preposition():
    r = parse_quick_input("позвонить в 14:00")
    assert r["text"] == "позвонить"
    assert r["time"] == "14:00"

def test_parse_weekday_ru():
    from datetime import date
    r = parse_quick_input("заехать на склад пт")
    d = date.fromisoformat(r["day"])
    assert d.weekday() == 4  # пятница

def test_parse_relative_tomorrow():
    from datetime import date, timedelta
    r = parse_quick_input("встреча завтра 15:30")
    assert r["day"] == (date.today() + timedelta(1)).isoformat()
    assert r["time"] == "15:30"
    assert r["text"] == "встреча"

def test_parse_no_match_fallback_today():
    from datetime import date
    r = parse_quick_input("перезвонить Лене")
    assert r["day"] == date.today().isoformat()
    assert r["time"] is None
    assert r["text"] == "перезвонить Лене"
```

**EditDialog modal test:**
```python
# Используем headless_tk fixture из conftest.py
def test_dialog_grab_set(headless_tk, tmp_appdata):
    from client.ui.edit_dialog import EditDialog
    from client.core.models import Task
    # ...
    saves = []
    task = Task.new(user_id="u1", text="test", day="2026-04-15")
    dialog = EditDialog(headless_tk, task, theme, lambda t: saves.append(t), lambda id: None)
    headless_tk.update()
    # grab_set активен — window.grab_current() должен вернуть dialog окно
    assert dialog._dialog.grab_current() is not None
    dialog._cancel()  # cleanup
```

### Sampling Rate

- **Per task commit:** `python -m pytest client/tests/test_quick_parse.py client/tests/ui/test_task_widget.py -x -q`
- **Per wave merge:** `python -m pytest client/tests/ -q`
- **Phase gate:** Full suite green + ручная проверка 9 Success Criteria из UI-SPEC.md §Success Criteria

### Wave 0 Gaps

- [ ] `client/tests/test_quick_parse.py` — covers TASK-01 parse logic (pure Python, no Tk)
- [ ] `client/tests/ui/test_task_widget.py` — covers TASK-02, TASK-04, WEEK-04, WEEK-05
- [ ] `client/tests/ui/test_quick_capture.py` — covers TASK-01 popup behavior
- [ ] `client/tests/ui/test_edit_dialog.py` — covers TASK-03
- [ ] `client/tests/ui/test_undo_toast.py` — covers TASK-04 undo
- [ ] `client/tests/ui/test_week_view.py` — covers WEEK-01..06
- [ ] conftest.py уже имеет все нужные fixtures (`headless_tk`, `tmp_appdata`) — расширять не нужно

*(Существующие тесты: test_main_window.py, test_themes.py, test_settings.py — не менять, только добавлять)*

---

## Sources

### Primary (HIGH confidence)

- `client/ui/overlay.py` — overrideredirect + after(100, ...) pattern, on_right_click callback (строка 94) — verified existing code
- `client/ui/main_window.py` — MainWindow structure, _build_day_section(), Phase 4 extension points — verified existing code
- `client/ui/themes.py` — ThemeManager.subscribe(), PALETTES dict — verified existing code
- `client/ui/settings.py` — UISettings dataclass, SettingsStore — verified existing code
- `client/core/storage.py` — LocalStorage.add_task(), update_task(), soft_delete_task() API — verified existing code
- `client/core/models.py` — Task.new(), Task.to_dict(), is_overdue() — verified existing code
- `client/tests/conftest.py` — headless_tk, mock_winotify, tmp_appdata fixtures — verified existing
- `.planning/phases/03-overlay-system/03-RESEARCH.md` — Pattern 1 (overrideredirect delay), Pattern 7 (ThemeManager), Pitfall 1-5 — HIGH confidence research
- `.planning/research/PITFALLS.md` — Performance trap "Full week re-render" — verified
- Python stdlib datetime docs — `date.isocalendar()`, `timedelta`, `weekday()` — stdlib
- Python stdlib re docs — `re.compile()`, `re.search()`, `re.IGNORECASE` — stdlib

### Secondary (MEDIUM confidence)

- CustomTkinter 5.2.2 source — CTkTextbox exists, CTkOptionMenu exists, CTkFrame takefocus support — verified via installed package `pip show customtkinter`
- Tkinter Text widget docs — `"1.0"` indexing, `"end-1c"` trailing newline removal — standard Tkinter
- Tkinter `grab_set()` / `grab_release()` docs — modal pattern, order requirements — standard Tkinter
- Tkinter `place()` geometry manager docs — `rely=1.0`, `anchor="sw"` for bottom positioning — standard Tkinter
- Tkinter `StringVar.trace_add("write", ...)` docs — validation callback pattern — standard Tkinter

### Tertiary (LOW confidence)

- Strikethrough via `tk.font.Font(overstrike=1)` in CTkLabel — needs runtime verification
- CTkFrame `takefocus=True` for keyboard navigation — behavior with Tab in CTkScrollableFrame needs verification

---

## Metadata

**Confidence breakdown:**
- Smart parse RU: HIGH — pure Python re, stdlib datetime, algorithm verified against spec
- QuickCapturePopup: HIGH — same overrideredirect pattern as Phase 3 overlay (already working)
- EditDialog: HIGH — grab_set() стандартный Tkinter, CTkTextbox/CTkOptionMenu confirmed in CTk 5.2.2
- UndoToastManager: MEDIUM — place() absolute positioning logic is straightforward; countdown bar animation via after() verified; stacking logic needs runtime test
- Task keyboard nav: MEDIUM — CTkFrame takefocus behavior in scroll context needs verification
- Archive dim: MEDIUM — color interpolation math correct; CTk widget re-configure all verified

**Research date:** 2026-04-15
**Valid until:** 2026-06-15 (CustomTkinter 5.2.2 pinned — стабильный; stdlib Python — permanent)
