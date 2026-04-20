# Phase 3: Оверлей и системная интеграция — Research

**Researched:** 2026-04-16
**Domain:** Windows desktop overlay (CustomTkinter + ctypes DWM) + pystray tray + winotify toast + Pillow icon composition
**Confidence:** HIGH (большинство паттернов верифицированы через официальные источники и PITFALLS.md, написанные ранее)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Visual design (все детали в UI-SPEC.md)**
- D-01: Квадрат вместо кружка — синий градиент `#4EA1FF → #1E73E8`, 56×56, rounded 12px, белая галочка / плюс / badge
- D-02: Overdue signal — весь квадрат пульсирует (blue→red→blue, 2.5s loop)
- D-03: Badge с числом задач сегодня в правом верхнем углу
- D-04: Empty state — белый "+" вместо галочки
- D-05: Tray-иконка = тот же квадрат (упрощённый для 16px)
- D-06: Окно — аккордеон по дням, сегодня раскрыт по умолчанию
- D-07: Today-indicator: синяя вертикальная полоска слева + bold заголовок (оба)
- D-08: Окно ресайзабельное, размер+позиция персистят
- D-09: Три темы: светлая (кремовая), тёмная (warm dark), бежевая (sepia) + опция "системная"
- D-10: Синий акцент только для CTA/focus/квадрата
- D-11: Task-block — 3 стиля (карточки / строки / минимализм), переключение мгновенное
- D-12: Tray-меню структура: Открыть → Добавить → Настройки(5 toggles) → Sync → Logout → Выход
- D-13: Toast-режимы: звук+pulse / только pulse / тихо

**Library choices (зафиксировано)**
- D-14: CustomTkinter 5.2.2 (pinned)
- D-15: pystray с `run_detached()` + `root.after(0, ...)` callbacks
- D-16: Overlay через `overrideredirect(True)` + `after(100, ...)` delay
- D-17: Toast — winotify (active maintenance)
- D-18: Icon composition через Pillow в памяти
- D-19: Multi-monitor через ctypes `EnumDisplayMonitors` + `GetSystemMetrics`
- D-20: Global hotkey — отложен в v2 (D-20 out-of-scope)
- D-21: Font — `Segoe UI Variable` + `Cascadia Code` mono

**Integration с Phase 2**
- D-22: Overlay читает `LocalStorage.get_visible_tasks()` — не дублирует state
- D-23: Tray "Обновить" вызывает `SyncManager.force_sync()`
- D-25: Настройки в `settings.json` через Phase 2 `LocalStorage.save_settings()` / `load_settings()`

**Thread safety**
- D-26: `pystray.Icon.run_detached()` — НЕ `run()`
- D-27: Все tray-callbacks через `root.after(0, fn)`
- D-28: Pulse animation — через `root.after()` цикл, не `threading.Timer`
- D-29: UI обновляется через `root.after(0, refresh_overlay)` из sync-потока

**Autostart**
- D-30: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` через `winreg`

### Claude's Discretion

- Конкретная структура файлов `client/ui/` (overlay.py, main_window.py и т.д.)
- Точные значения anim-timings
- Способ реализации pulse: `after()` loop vs canvas blending
- Реализация "empty state dim opacity" для "не беспокоить"
- Структура unit/integration тестов
- Конкретная dataclass-схема для settings.json

### Deferred Ideas (OUT OF SCOPE)

- Drag-and-drop задач — Phase 4
- Inline add-task input — Phase 4
- Редактирование текста задачи — Phase 4
- Global hotkey (Win+Q) — v2 (UXI-01)
- Sync status visual indicator — v2
- Mini-preview в overlay при hover — v2
- Keyboard shortcuts внутри окна — v2
- Window transparency settings — v2
- Multi-workspace/virtual-desktops Windows — изучим на практике
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OVR-01 | Перетаскиваемый квадратный оверлей на рабочем столе Windows (overrideredirect + topmost) | §Overlay Creation — `overrideredirect(True)` + `after(100, ...)` + DWM rounded corners |
| OVR-02 | Позиция квадрата запоминается между запусками (`settings.json`) | §Settings Persistence — `LocalStorage.load_settings()` / `save_settings()` |
| OVR-03 | Работает на multi-monitor setup (ctypes EnumDisplayMonitors) | §Multi-Monitor Positioning |
| OVR-04 | Клик по квадрату открывает/закрывает главное окно | §Click Behavior — single-click toggle, CTkToplevel |
| OVR-05 | Квадрат визуально пульсирует при наличии просроченных задач | §Pulse Animation — after() 60fps loop, color interpolation |
| OVR-06 | Режим "всегда поверх всех окон" — переключаемый (кружок + окно) | §Always-On-Top — `wm_attributes("-topmost", ...)` |
| TRAY-01 | Иконка в system tray (pystray) с контекстным меню | §Tray Icon — pystray 0.19.5, run_detached() |
| TRAY-02 | Через меню — toggle Поверх всех окон, Не беспокоить, theme, task-style, logout, exit | §Tray Menu — dynamic menu items через callable properties |
| TRAY-03 | Настройки сохраняются в `settings.json` мгновенно | §Settings Persistence |
| TRAY-04 | pystray использует `run_detached()` + `root.after(0, ...)` | §Thread Safety — канонический паттерн |
| NOTIF-01 | Настраиваемый режим: pulse / pulse+toast / тихо | §Notification Modes |
| NOTIF-02 | Toast через Windows 10/11 (winotify) | §winotify API — `Notification(app_id, title, msg).show()` |
| NOTIF-03 | Уведомления при наступлении time_deadline задачи | §Deadline Checker — фоновый `after()` таймер |
| NOTIF-04 | "Не беспокоить" блокирует toast | §Do-Not-Disturb State |
</phase_requirements>

---

## Summary

Phase 3 строит визуальный каркас клиента: квадрат-оверлей на рабочем столе, аккордеон-окно с неделей, system tray иконку и toast-уведомления. Все технические решения уже приняты в CONTEXT.md на основе предыдущих research-фаз. Риск Phase 3 — не выбор библиотек, а корректная интеграция нескольких Windows-специфичных механизмов с Tk mainloop: DWM overrideredirect, pystray threading и winotify subprocess.

Три критических угрозы стабильности: (1) `overrideredirect(True)` без `after(100, ...)` delay ронит окно за другие на Win11, (2) tray callbacks без `root.after(0, fn)` вызывают `RuntimeError` при 20+ кликах, (3) winotify блокирует вызывающий поток если запускается синхронно — нужен фоновый thread или `after()`.

**Primary recommendation:** Overlay = `CTkToplevel` с Canvas 56×56 (Pillow-rendered image), tray = `pystray.Icon.run_detached()`, toast = `winotify.Notification.show()` из daemon thread, pulse = `root.after(16, ...)` с float-интерполяцией hex-цветов.

---

## Standard Stack

### Core (pinned — менять нельзя)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| customtkinter | ==5.2.2 | GUI framework — overlay, main window, all widgets | Pinned per STACK.md; только стабильный modern-Tk wrapper для PyInstaller |
| pystray | ==0.19.5 | System tray icon | Pinned; 0.19.5 содержит критический Pillow-compat fix |
| Pillow | >=11.0.0 | Tray icon composition, badge drawing | Требуется pystray для Windows backend; `ImageDraw.rounded_rectangle()` с Pillow 8.2+ |
| pywin32 | >=306 | DWM rounded corners, SetWindowPos, EnumDisplayMonitors | ctypes wrapping Win32 — без pywin32 нужен сырой ctypes |
| winotify | ==1.1.0 | Windows 10/11 toast notifications | Последний релиз Feb 2022; active maintenance; pure Python + PowerShell; no deps |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| winreg | stdlib | Autostart registry read/write | TRAY-03 autostart toggle; уже в autostart.py skeleton |
| ctypes | stdlib | DwmSetWindowAttribute rounded corners, GetMonitorInfo | Overlay win shape; multi-monitor positioning |
| threading | stdlib | winotify async send (нельзя блокировать Tk mainloop) | NOTIF-02 toast отправляется из daemon thread |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| winotify | win10toast-click | win10toast-click стагнантный (последний PyPI release 2021); winotify активнее поддерживается |
| winotify | win11toast | win11toast требует `pytoast` С-extension; сложнее в PyInstaller; winotify pure-Python |
| winotify | plyer | plyer — кроссплатформенный, но на Windows делает WinRT через COM что ненадёжно в PyInstaller --onefile |
| Pillow draw | cairosvg | cairosvg требует Cairo системную библиотеку; Pillow достаточен для 56×56 |
| CTkToplevel | raw Toplevel | CTkToplevel поддерживает темизацию автоматически; raw Toplevel нужно стилизовать вручную |

**Installation:**
```bash
pip install customtkinter==5.2.2 pystray==0.19.5 Pillow>=11.0.0 pywin32>=306 winotify==1.1.0
```

**Version verification (выполнено 2026-04-16):**
- customtkinter 5.2.2 — PyPI (Jan 2024) — PINNED
- pystray 0.19.5 — PyPI (Sep 2023) — PINNED
- winotify 1.1.0 — PyPI (Feb 2022) — PINNED (последний релиз)
- Pillow 12.2.0 — PyPI (Apr 2026) — ACTIVE

---

## Architecture Patterns

### Recommended File Structure

```
client/
├── app.py                  ← WeeklyPlannerApp (точка интеграции — ПЕРЕПИСАТЬ)
├── ui/
│   ├── overlay.py          ← OverlayManager (квадрат на рабочем столе)
│   ├── main_window.py      ← MainWindow (аккордеон с неделями)
│   ├── day_section.py      ← DaySection (сворачиваемая секция дня)
│   ├── task_widget.py      ← TaskWidget (один элемент задачи — 3 стиля)
│   ├── tray_icon.py        ← TrayManager (pystray wrapper)
│   ├── notifications.py    ← NotificationManager (winotify + deadline checker)
│   └── themes.py           ← ThemeManager (3 темы + live switching)
├── core/
│   ├── storage.py          ← LocalStorage (Phase 2, API surfaces для Phase 3)
│   ├── sync.py             ← SyncManager (Phase 2, force_sync())
│   ├── auth.py             ← AuthManager (Phase 2, logout())
│   └── models.py           ← Task, AppState (Phase 2)
└── utils/
    └── autostart.py        ← enable/disable_autostart (skeleton — дополнить)
```

Phase 3 создаёт: `overlay.py`, `main_window.py`, `day_section.py`, `task_widget.py`, `tray_icon.py`, `notifications.py`, переписывает `themes.py`, `app.py`.

---

### Pattern 1: Overlay Creation (overrideredirect + DWM delay)

**What:** Создание borderless topmost окна с DWM-скруглёнными углами на Windows 11.

**When to use:** При создании квадрата-оверлея (OverlayManager.__init__).

**Critical:** `overrideredirect(True)` НЕЛЬЗЯ вызывать в `__init__`. Нужен `after(100, ...)` delay.

```python
# Source: PITFALLS.md Pitfall 1 + CustomTkinter Discussion #1302
import ctypes
import customtkinter as ctk

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2  # Windows 11 rounded corners

class OverlayManager:
    def __init__(self, root: ctk.CTk, storage: LocalStorage):
        self._root = root
        self._storage = storage
        self._overlay = ctk.CTkToplevel(root)
        self._overlay.withdraw()  # скрыть сразу
        
        # КРИТИЧНО: задержка 100ms для Win11 DWM
        self._overlay.after(100, self._init_overlay_style)
    
    def _init_overlay_style(self):
        self._overlay.overrideredirect(True)  # убрать рамку
        self._overlay.attributes("-topmost", True)
        self._overlay.geometry("56x56+100+100")  # начальная позиция
        
        # DWM rounded corners (Windows 11 only — тихо игнорируется на Win10)
        try:
            hwnd = ctypes.windll.user32.GetParent(
                self._overlay.winfo_id()
            )
            value = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception:
            pass  # Win10 — не страшно, используем Pillow-rounded canvas
        
        self._overlay.deiconify()
        self._render_overlay()
```

**Note:** На Windows 10 DwmSetWindowAttribute(33) не работает (атрибут добавлен в Win11). Скруглённые углы на Win10 реализуются через Pillow image с прозрачными пикселями в углах (RGBA) + `wm_attributes("-transparentcolor", ...)`.

---

### Pattern 2: pystray + Tkinter Threading (TRAY-04)

**What:** Tray icon в фоновом потоке, все UI callbacks через root.after(0, ...).

**When to use:** TrayManager.start() — однократно при запуске app.

```python
# Source: PITFALLS.md Pitfall 2 + pystray Issue #94
import pystray

class TrayManager:
    def __init__(self, root: ctk.CTk, on_show, on_hide, on_sync, on_logout, on_quit):
        self._root = root
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon: pystray.Icon = None
        # Динамические состояния (для callable menu items)
        self._on_top: bool = True
        self._do_not_disturb: bool = False
    
    def _make_menu(self) -> pystray.Menu:
        # pystray поддерживает callable для динамического состояния
        return pystray.Menu(
            pystray.MenuItem("Открыть окно", self._cb_show, default=True),
            pystray.MenuItem("Скрыть", self._cb_hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Добавить задачу", self._cb_add_task),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Настройки", pystray.Menu(
                pystray.MenuItem("Тема", pystray.Menu(
                    pystray.MenuItem("Светлая", lambda i, item: self._cb_theme("light")),
                    pystray.MenuItem("Тёмная", lambda i, item: self._cb_theme("dark")),
                    pystray.MenuItem("Бежевая", lambda i, item: self._cb_theme("beige")),
                    pystray.MenuItem("Системная", lambda i, item: self._cb_theme("system")),
                )),
                pystray.MenuItem(
                    "Поверх всех окон",
                    self._cb_toggle_ontop,
                    checked=lambda item: self._on_top,  # callable → dynamic checkmark
                ),
                pystray.MenuItem(
                    "Автозапуск",
                    self._cb_toggle_autostart,
                    checked=lambda item: autostart.is_autostart_enabled(),
                ),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Обновить синхронизацию", self._cb_sync),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Разлогиниться", self._cb_logout),
            pystray.MenuItem("Выход", self._cb_quit),
        )
    
    def start(self, icon_image):
        self._icon = pystray.Icon(
            "weekly-planner", icon_image,
            title="Личный Еженедельник",
            menu=self._make_menu(),
        )
        self._icon.run_detached()  # КРИТИЧНО: не run()!
    
    # Callbacks — все через root.after(0, ...) для Tk thread safety
    def _cb_show(self, icon, item):
        self._root.after(0, self._on_show)
    
    def _cb_toggle_ontop(self, icon, item):
        self._on_top = not self._on_top
        self._root.after(0, lambda: self._apply_ontop(self._on_top))
        self._icon.update_menu()  # обновить checkmark
    
    def _cb_sync(self, icon, item):
        self._root.after(0, self._on_sync)
    
    def update_icon(self, new_image):
        """Вызывать из main thread (after() callback) при изменении задач."""
        if self._icon:
            self._icon.icon = new_image
```

**Warning:** `self._icon.update_menu()` МОЖНО вызывать из pystray-потока (это pystray-internal). Но любой вызов к Tkinter виджетам — только через `root.after(0, fn)`.

---

### Pattern 3: Pillow Icon Composition

**What:** Рендер квадрат+галочка+badge в RAM → передача в pystray и overlay canvas.

**When to use:** При старте и при изменении числа задач / состояния overdue.

```python
# Source: Pillow docs (ImageDraw.rounded_rectangle added Pillow 8.2+)
from PIL import Image, ImageDraw, ImageFont

def render_overlay_image(
    size: int,           # 56 для overlay, 16/32 для tray
    state: str,          # "default", "overdue", "empty"
    task_count: int,
    overdue_count: int,
    pulse_t: float = 0.0,  # 0.0..1.0 — позиция в цикле pulse
) -> Image.Image:
    
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Цвет фона (с учётом pulse-анимации)
    if state == "overdue" and pulse_t > 0:
        blue = (30, 115, 232)    # #1E73E8
        red  = (232, 90, 90)     # #E85A5A
        t = abs(pulse_t * 2 - 1)  # triangle wave 0→1→0
        bg_color = tuple(int(b + (r - b) * t) for b, r in zip(blue, red))
    else:
        bg_color = (30, 115, 232)  # #1E73E8 solid
    
    # Основной квадрат со скруглением
    radius = max(2, int(size * 0.214))  # 12px для 56px
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=(*bg_color, 255),
    )
    
    # Тень (простой drop shadow через alpha-blur — опционально для overlay)
    # ...для tray не нужна
    
    # Иконка (галочка / плюс)
    icon_size = int(size * 0.5)
    icon_x = (size - icon_size) // 2
    icon_y = (size - icon_size) // 2
    if state == "empty":
        _draw_plus(draw, icon_x, icon_y, icon_size)
    else:
        _draw_checkmark(draw, icon_x, icon_y, icon_size)
    
    # Badge (правый верхний угол)
    count = overdue_count if state == "overdue" else task_count
    if count > 0 and size >= 32:  # badge только для крупных иконок
        badge_size = max(8, int(size * 0.286))  # 16px для 56px
        bx = size - badge_size
        by = 0
        draw.ellipse([(bx, by), (bx + badge_size, by + badge_size)], fill=(255, 255, 255, 255))
        text = str(min(count, 99))
        # font = ImageFont.truetype("segoeui.ttf", ...)
        draw.text((bx + badge_size // 2, by + badge_size // 2), text,
                  fill=(30, 30, 30), anchor="mm")
    
    return img
```

**Confidence:** HIGH — `ImageDraw.rounded_rectangle()` stable с Pillow 8.2; проверено в Pillow docs.

---

### Pattern 4: Pulse Animation (OVR-05)

**What:** 2.5-секундный цикл blue→red→blue через `root.after(16, ...)` (60fps).

**When to use:** Когда `any(t.is_overdue() for t in get_visible_tasks())`.

```python
# Source: CONTEXT.md D-02, D-28; UI-SPEC Animations section
class OverlayManager:
    PULSE_INTERVAL_MS = 16        # ~60fps
    PULSE_CYCLE_MS = 2500         # полный цикл 2.5 секунды
    PULSE_PHASE_TIMINGS = [       # [нормальный, красный, возврат] ms
        (0,    1000),             # 0..1000ms: синий (100% синий)
        (1000, 1750),             # 1000..1750ms: синий → красный
        (1750, 2500),             # 1750..2500ms: красный → синий
    ]
    
    def _start_pulse(self):
        self._pulse_active = True
        self._pulse_start_ms = 0
        self._pulse_tick()
    
    def _stop_pulse(self):
        self._pulse_active = False
        self._render_overlay()  # вернуть нормальный цвет
    
    def _pulse_tick(self):
        if not self._pulse_active:
            return
        t_ms = (int(self._overlay.tk.call("clock", "milliseconds")) 
                % self.PULSE_CYCLE_MS)
        t_norm = t_ms / self.PULSE_CYCLE_MS  # 0.0..1.0
        new_image = render_overlay_image(
            size=56,
            state="overdue",
            task_count=self._current_task_count,
            overdue_count=self._current_overdue_count,
            pulse_t=t_norm,
        )
        self._canvas.itemconfig(self._canvas_image_id, image=new_image)
        self._overlay.after(self.PULSE_INTERVAL_MS, self._pulse_tick)
```

**Упрощённый вариант pulse_t (рекомендован для MVP):** Вместо `clock milliseconds` — инкрементный счётчик умноженный на PULSE_INTERVAL_MS. Точнее: накапливать elapsed = counter * 16ms, брать elapsed % 2500 / 2500.

**Performance:** 60fps при размере 56×56 px — Python генерирует <1KB Pillow image каждые 16ms. На современном CPU (Ryzen/Core) этот паттерн потребляет <1% CPU по данным сообщества CustomTkinter (issue #1461). Приемлемо.

**Alternative (если CPU-bound):** Пре-рендер 30-60 Pillow frames при старте + cycle through list. Минус: ~3MB RAM, плюс: zero CPU в анимации. Для MVP — live-рендер проще.

---

### Pattern 5: Drag Behavior (OVR-01, OVR-02, OVR-03)

**What:** Перетаскивание overlay с сохранением позиции и multi-monitor поддержкой.

```python
# Source: Tkinter button-1 event binding + ctypes GetMonitorInfo
class OverlayManager:
    def _setup_drag(self):
        self._overlay.bind("<ButtonPress-1>", self._on_drag_start)
        self._overlay.bind("<B1-Motion>", self._on_drag_motion)
        self._overlay.bind("<ButtonRelease-1>", self._on_drag_end)
        self._drag_x = 0
        self._drag_y = 0
    
    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self._overlay.winfo_x()
        self._drag_y = event.y_root - self._overlay.winfo_y()
    
    def _on_drag_motion(self, event):
        new_x = event.x_root - self._drag_x
        new_y = event.y_root - self._drag_y
        # Clamp к виртуальному рабочему столу (all monitors)
        new_x = max(self._vscreen_left, min(new_x, self._vscreen_right - 56))
        new_y = max(self._vscreen_top, min(new_y, self._vscreen_bottom - 56))
        self._overlay.geometry(f"56x56+{new_x}+{new_y}")
    
    def _on_drag_end(self, event):
        pos = {"x": self._overlay.winfo_x(), "y": self._overlay.winfo_y()}
        # Сохранить асинхронно (не блокировать UI)
        self._root.after(0, lambda: self._save_position(pos))
    
    def _get_virtual_screen_bounds(self):
        """ctypes EnumDisplayMonitors для virtual desktop bounds."""
        monitors = []
        def callback(hmon, hdc, lprect, lparam):
            monitors.append((lprect.contents.left, lprect.contents.top,
                             lprect.contents.right, lprect.contents.bottom))
            return True
        # win32api.EnumDisplayMonitors возвращает [(hmon, hdc, rect), ...]
        import win32api
        for monitor in win32api.EnumDisplayMonitors():
            info = win32api.GetMonitorInfo(monitor[0])
            r = info["Monitor"]
            monitors.append(r)
        if not monitors:
            return 0, 0, self._root.winfo_screenwidth(), self._root.winfo_screenheight()
        left = min(m[0] for m in monitors)
        top  = min(m[1] for m in monitors)
        right  = max(m[2] for m in monitors)
        bottom = max(m[3] for m in monitors)
        return left, top, right, bottom
```

**Multi-monitor coordinate system:** Виртуальный рабочий стол Windows — все мониторы образуют единое coordinate space. Первичный монитор начинается в (0,0). Вторичный слева — отрицательные X. Сохранять нужно абсолютные координаты (работает корректно если мониторы не меняются между сессиями).

**Position validation при restore:** При загрузке `settings.json` проверить что сохранённая позиция попадает в текущий виртуальный рабочий стол. Если нет — fallback (100, 100).

---

### Pattern 6: Settings Schema и Persistence

**What:** Единая схема settings.json для всех Phase 3 preferences.

```python
# Рекомендуемая схема settings.json (Claude's discretion D-25)
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class UISettings:
    """Сериализуется через dataclasses.asdict() в settings.json."""
    theme: str = "light"                    # "light" | "dark" | "beige" | "system"
    task_style: str = "card"                # "card" | "line" | "minimal"
    notifications_mode: str = "pulse_toast" # "pulse_toast" | "pulse_only" | "silent"
    on_top: bool = True
    autostart: bool = False
    overlay_x: int = 100                   # позиция overlay
    overlay_y: int = 100
    window_x: Optional[int] = None         # позиция main window (None = auto-center)
    window_y: Optional[int] = None
    window_width: int = 460
    window_height: int = 600
    version: int = 1                        # для будущих миграций
```

**LocalStorage integration:** Phase 2 уже имеет `LocalStorage.load_settings()` / `save_settings()` — используем их. Дополнительный `SettingsStore`-класс не нужен.

---

### Pattern 7: Theme Manager (D-09)

**What:** ThemeManager с 3 кастомными темами + live switching.

**Critical insight:** `ctk.set_appearance_mode("light"/"dark")` переключает только встроенные CTk-темы. Кастомная "beige" требует явного `.configure()` на каждом виджете. Это означает: либо хранить список всех виджетов, либо использовать refresh-метод который пересоздаёт компоненты.

**Рекомендованный подход:** Callback-registration pattern.

```python
# Source: CustomTkinter Discussion #2373 + PITFALLS.md "Theme switching requires restart"
PALETTES = {
    "light": {
        "bg_primary": "#F5EFE6",
        "bg_secondary": "#EDE6D9",
        "text_primary": "#2B2420",
        "accent_brand": "#1E73E8",
        "accent_done": "#38A169",
        "accent_overdue": "#E85A5A",
        ...
    },
    "dark": {
        "bg_primary": "#1F1B16",
        ...
    },
    "beige": {
        "bg_primary": "#E8DDC4",
        ...
    },
}

class ThemeManager:
    def __init__(self):
        self._theme = "light"
        self._callbacks: list[callable] = []
    
    def subscribe(self, callback: callable) -> None:
        """Каждый виджет/менеджер регистрирует refresh-callback."""
        self._callbacks.append(callback)
    
    def set_theme(self, theme: str) -> None:
        if theme == "system":
            # Определить системную тему через winreg
            theme = self._detect_system_theme()
        self._theme = theme
        # CTk built-in mode
        ctk.set_appearance_mode("dark" if theme == "dark" else "light")
        # Оповестить все подписчики
        for cb in self._callbacks:
            cb(PALETTES[theme])
    
    def get(self, key: str) -> str:
        return PALETTES.get(self._theme, PALETTES["light"]).get(key, "#ffffff")
    
    @staticmethod
    def _detect_system_theme() -> str:
        """Registry read для системной темы Windows."""
        import winreg
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"
        except Exception:
            return "light"
```

---

### Pattern 8: winotify Toast (NOTIF-02)

**What:** Простой toast через winotify без callback (Phase 3) — достаточно для deadline notifications.

**Critical:** `winotify.Notification.show()` является blocking call (использует PowerShell subprocess). Никогда не вызывать из Tk mainloop напрямую — только из daemon thread.

```python
# Source: winotify PyPI README, Documentation
import threading
from winotify import Notification

class NotificationManager:
    def __init__(self, app_paths):
        self._mode = "pulse_toast"  # из settings
        self._do_not_disturb = False
        self._icon_path = str(app_paths.base_dir / "icon.png")  # абс. путь обязателен!
    
    def send_toast(self, title: str, body: str) -> None:
        """Отправить toast в daemon thread (не блокировать mainloop)."""
        if self._do_not_disturb or self._mode == "pulse_only" or self._mode == "silent":
            return
        thread = threading.Thread(
            target=self._do_show_toast,
            args=(title, body),
            daemon=True,
        )
        thread.start()
    
    def _do_show_toast(self, title: str, body: str) -> None:
        try:
            toast = Notification(
                app_id="Личный Еженедельник",
                title=title,
                msg=body,
                icon=self._icon_path,  # ДОЛЖЕН быть абсолютный путь!
            )
            toast.show()  # blocking — OK, мы в daemon thread
        except Exception as exc:
            logger.warning("Toast failed: %s", exc)
    
    def check_deadlines(self, tasks: list[Task], root: ctk.CTk) -> None:
        """Проверить approaching deadlines. Вызывать через root.after(60000, ...)."""
        now = datetime.now()
        for task in tasks:
            if task.done or not task.time_deadline:
                continue
            try:
                deadline = datetime.fromisoformat(task.time_deadline.replace("Z", "+00:00"))
            except ValueError:
                continue
            delta_min = (deadline - now).total_seconds() / 60
            if 0 <= delta_min <= 5:
                self.send_toast(
                    "Задача через 5 минут",
                    f"{task.text} — {deadline.strftime('%H:%M')}",
                )
```

**winotify icon path:** Должен быть **абсолютным путём** к PNG/ICO файлу. Если путь относительный — уведомление показывается без иконки (не crash). Это важно для PyInstaller (Phase 6) — нужно `sys._MEIPASS / "client/assets/icon.png"`.

**winotify click-to-open:** Для простого click → open window нужен `Notifier` + `register_callback`. Это "advanced feature" требующее running subprocess. Для Phase 3 — пропустить (click просто закроет toast). Можно добавить в Phase 4 если захочется.

---

### Pattern 9: Autostart (D-30, TRAY-03)

**What:** `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` через winreg.

Skeleton `client/utils/autostart.py` уже корректный. Единственное уточнение:

```python
# Source: client/utils/autostart.py (existing skeleton) — уже правильно
# PITFALLS Integration Table: "Write to HKCU (no elevation needed)"

def enable_autostart():
    exe_path = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{sys.argv[0]}"'
    # sys.frozen = True в PyInstaller-собранном exe
    # В dev: python.exe main.py — оба в кавычках на случай пробелов в пути
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
```

**ASCII vs Cyrillic APP_NAME в реестре:** Реестр Windows UTF-16 — кириллица работает. Но для совместимости с `winreg.QueryValueEx` в Python — тест на реальной машине. Skeleton использует `APP_NAME = "ЛичныйЕженедельник"` — оставить как есть.

---

### Pattern 10: WeeklyPlannerApp Integration (app.py rewrite)

**What:** Правильная последовательность инициализации всех Phase 3 компонентов.

```python
# Source: CONTEXT.md Integration Points
class WeeklyPlannerApp:
    def _setup(self):
        # 1. Theme (до создания любых виджетов)
        self.theme = ThemeManager()
        
        # 2. Paths + Storage (Phase 2)
        self.storage = LocalStorage()
        self.storage.init()
        settings_dict = self.storage.load_settings()
        self.settings = UISettings(**settings_dict) if settings_dict else UISettings()
        self.theme.set_theme(self.settings.theme)
        
        # 3. Auth check
        self.auth = AuthManager()
        if not self.auth.load_saved_token():
            self._show_login_placeholder()
            return  # синхронизация стартует после логина
        
        # 4. Sync (Phase 2)
        self.sync = SyncManager(self.storage, self.auth)
        self.sync.start()
        
        # 5. Overlay (создать ПОСЛЕ root — CTkToplevel требует parent)
        self.overlay = OverlayManager(self.root, self.storage, self.theme, self.settings)
        
        # 6. Main window (hidden по умолчанию)
        self.main_window = MainWindow(self.root, self.storage, self.theme, self.settings)
        
        # 7. Connect overlay → main_window
        self.overlay.on_click = self.main_window.toggle
        
        # 8. Notifications
        self.notifications = NotificationManager(AppPaths())
        self._schedule_deadline_check()
        
        # 9. Tray (ПОСЛЕДНИМ — требует icon image уже готовую)
        tray_image = render_overlay_image(size=16, state="default", task_count=0, overdue_count=0)
        self.tray = TrayManager(
            root=self.root,
            on_show=self.main_window.show,
            on_hide=self.main_window.hide,
            on_sync=self.sync.force_sync,
            on_logout=self._handle_logout,
            on_quit=self._handle_quit,
        )
        self.tray.start(tray_image)
        
        # 10. Periodic overlay refresh (каждые 30с обновить badge + overdue state)
        self._schedule_overlay_refresh()
    
    def _schedule_deadline_check(self):
        tasks = self.storage.get_visible_tasks()
        self.notifications.check_deadlines(tasks, self.root)
        self.root.after(60_000, self._schedule_deadline_check)  # каждую минуту
    
    def _schedule_overlay_refresh(self):
        tasks = self.storage.get_visible_tasks()
        self.overlay.refresh(tasks)
        self.root.after(30_000, self._schedule_overlay_refresh)
```

---

### Anti-Patterns to Avoid

- **`icon.run()` вместо `run_detached()`:** Блокирует main thread — Tk mainloop никогда не запустится. Всегда `run_detached()`.
- **Tkinter вызовы из pystray callback напрямую:** `RuntimeError: main thread is not in main loop` при 20+ кликах. Всегда `root.after(0, fn)`.
- **`overrideredirect(True)` в `__init__` без delay:** На Windows 11 окно рендерится за другими. Обязателен `after(100, ...)`.
- **`winotify.Notification.show()` в Tk mainloop:** PowerShell subprocess блокирует mainloop на 1-3 секунды — UI freezes. Только в daemon thread.
- **`set_appearance_mode()` как единственный способ переключить тему:** Не обновляет виджеты которые уже созданы с explicit colors. Нужен `.configure()` loop через callback subscribers.
- **Хранить только (x, y) без bounds validation при restore:** После unplugging монитора overlay улетает off-screen без recovery.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| System tray icon | Своя Win32 Shell_NotifyIcon обёртка | `pystray==0.19.5` | pystray покрывает иконку, меню, tooltip; Win32 API требует WNDPROC loop |
| Windows toast notifications | win10toast / ctypes WinRT | `winotify==1.1.0` | winotify pure Python + PowerShell; корректно для Windows 10/11; нет C-extensions |
| Rounded window | transparentcolor + shapeMask хаки | DwmSetWindowAttribute(33) на Win11; Pillow RGBA на Win10 | DWM официальный способ; Pillow безопаснее чем shapeMask на Tk |
| Gradient background | CTkFrame с custom bg | Pillow draw на Canvas image | CTk не поддерживает градиенты; Canvas ItemImage + Pillow — правильный паттерн |
| Multi-monitor enumeration | Пытаться через winfo_screenwidth() | `win32api.EnumDisplayMonitors()` + `GetMonitorInfo()` | winfo_screenwidth() возвращает только primary monitor на большинстве конфигов |
| Color interpolation for pulse | Своя math библиотека | Inline linear interpolation (3 строки) | Достаточно прямолинейного `int(a + (b - a) * t)` per channel |
| Settings serialization | Своя XML/INI parser | `dataclasses.asdict()` + `json.dump()` | LocalStorage.save_settings() уже это делает |
| Autostart detection | Свои Registry heuristics | `winreg.QueryValueEx` (уже в skeleton) | winreg stdlib, надёжен, уже работает в skeleton |

**Key insight:** В Windows overlay domain большинство "простых" задач (тень, градиент, rounded corners) требуют либо низкоуровневого Win32 либо Pillow compositing. Не пытаться сделать через Tkinter-only атрибуты.

---

## Common Pitfalls

### Pitfall 1: overrideredirect без delay на Windows 11
**What goes wrong:** Overlay рендерится позади других окон, пользователь не видит.
**Why it happens:** Win11 DWM асинхронно настраивает window composition при создании. `overrideredirect(True)` в `__init__` мешает этому процессу.
**How to avoid:** `self._overlay.after(100, lambda: self._overlay.overrideredirect(True))`
**Warning signs:** App запускается, tray появляется, overlay невидим. Иногда появляется после клика на рабочий стол.
**Confidence:** HIGH — источник: CustomTkinter Discussion #1219, #1302

---

### Pitfall 2: pystray RuntimeError при быстрых tray кликах
**What goes wrong:** `RuntimeError: main thread is not in main loop` после 5-20 кликов по tray меню.
**Why it happens:** pystray callback вызывается из своего WIN32-потока. Любое обращение к Tk widget из чужого потока нарушает Tcl apartment-threading.
**How to avoid:** Все callbacks: `root.after(0, lambda: actual_work())`. Никогда не `.configure()` или `.pack()` напрямую.
**Warning signs:** Работает при медленных кликах, падает при быстрых.
**Confidence:** HIGH — источник: PITFALLS.md Pitfall 2, pystray Issue #94

---

### Pitfall 3: winotify блокирует mainloop
**What goes wrong:** UI freezes на 1-3 секунды при наступлении deadline.
**Why it happens:** winotify использует `subprocess.run(["powershell", ...])` — это блокирующий call.
**How to avoid:** Всегда `threading.Thread(target=send_toast, daemon=True).start()`.
**Warning signs:** Cursor freezes на момент toast; keyboard input не обрабатывается.
**Confidence:** HIGH — winotify source code (uses subprocess.run)

---

### Pitfall 4: Pillow image ownership в Tkinter Canvas
**What goes wrong:** Overlay показывает пустой белый прямоугольник после первого рендера.
**Why it happens:** Tkinter Canvas не удерживает PhotoImage от garbage collection. Если `img` создан в локальной функции — Python его удалит.
**How to avoid:** Хранить reference к ImageTk.PhotoImage в instance variable.
```python
self._tk_image = ImageTk.PhotoImage(pillow_img)  # сохранить!
self._canvas.itemconfig(self._img_id, image=self._tk_image)
```
**Warning signs:** Серый/белый overlay сразу после старта или после темы-switch.
**Confidence:** HIGH — стандартная Tkinter gotcha, хорошо известна

---

### Pitfall 5: Theme switch не применяется к custom-colored виджетам
**What goes wrong:** После смены темы light→dark часть виджетов остаётся со старыми цветами.
**Why it happens:** `ctk.set_appearance_mode()` переключает CTk built-in color tokens. Виджеты с `fg_color="#F5EFE6"` (hardcoded) не реагируют.
**How to avoid:** Никогда не хардкодить hex в виджетах. Всегда через ThemeManager.get(). Регистрировать refresh-callback в ThemeManager.subscribe().
**Warning signs:** После смены темы часть фреймов светлые, часть тёмные.
**Confidence:** MEDIUM — источник: CustomTkinter Discussion #2373 (пользователи жалуются), PITFALLS.md "Theme switching"

---

### Pitfall 6: Multi-monitor сохранённая позиция off-screen
**What goes wrong:** После unplug монитора overlay рендерится где-то off-screen — невидим. Нет способа вернуть без "Reset position" в tray.
**Why it happens:** Сохранённые (x, y) координаты выходят за пределы актуального virtual desktop.
**How to avoid:** При загрузке позиции из settings.json — validate против текущего virtual desktop bounds. Fallback: `(100, 100)`.
**Warning signs:** Overlay невидим при старте, хотя tray появился.
**Confidence:** MEDIUM — логический вывод, не воспроизведено в репорте

---

### Pitfall 7: winotify icon path должен быть абсолютным
**What goes wrong:** Toast показывается без иконки (молча, не crash).
**Why it happens:** winotify передаёт путь в PowerShell. Относительные пути не резолвятся в PowerShell context.
**How to avoid:** Всегда `str(Path(icon_path).resolve())` перед передачей в `Notification(icon=...)`.
**Warning signs:** Toast работает, но без иконки приложения.
**Confidence:** HIGH — winotify README явно упоминает это требование

---

## Code Examples

### Pillow draw checkmark

```python
# Source: Pillow ImageDraw docs — line с width для "chunky" стиля
def _draw_checkmark(draw: ImageDraw.Draw, x: int, y: int, size: int):
    """Белая галочка Things 3 стиля — stroke_width ~15% от size."""
    w = max(2, size // 7)
    pts = [
        (x + size * 0.15, y + size * 0.55),
        (x + size * 0.40, y + size * 0.75),
        (x + size * 0.85, y + size * 0.25),
    ]
    draw.line(pts, fill=(255, 255, 255, 255), width=w)

def _draw_plus(draw: ImageDraw.Draw, x: int, y: int, size: int):
    """Белый плюс для empty state."""
    w = max(2, size // 7)
    cx, cy = x + size // 2, y + size // 2
    draw.line([(cx, y + size * 0.2), (cx, y + size * 0.8)], fill=(255, 255, 255, 255), width=w)
    draw.line([(x + size * 0.2, cy), (x + size * 0.8, cy)], fill=(255, 255, 255, 255), width=w)
```

### Pystray icon update из Tk thread

```python
# Source: pystray Issue #14 — update_menu() usage
def refresh_tray_icon(self, tasks: list[Task]) -> None:
    """Вызывать из main Tk thread через root.after(0, ...)."""
    overdue = [t for t in tasks if t.is_overdue()]
    today_tasks = [t for t in tasks if t.day == date.today().isoformat() and not t.done]
    
    state = "overdue" if overdue else ("empty" if not today_tasks else "default")
    new_image = render_overlay_image(
        size=16,
        state=state,
        task_count=len(today_tasks),
        overdue_count=len(overdue),
    )
    if self._icon:
        self._icon.icon = ImageTk.PhotoImage(new_image)  # pystray принимает PIL Image напрямую
        count = len(overdue) if overdue else len(today_tasks)
        self._icon.title = (
            f"Личный Еженедельник — {count} просрочено" if overdue
            else f"Личный Еженедельник — {count} задач сегодня"
        )
```

### Always-on-top toggle

```python
# Source: CustomTkinter docs + Tkinter wm_attributes
def set_always_on_top(self, enabled: bool) -> None:
    """Применяется к обоим окнам — overlay и main window."""
    self._overlay.attributes("-topmost", enabled)
    if self._main_window.winfo_exists():
        self._main_window.attributes("-topmost", enabled)
    # Сохранить в settings
    self._settings.on_top = enabled
    self._storage.save_settings(asdict(self._settings))
```

### Do-not-disturb overlay opacity

```python
# Source: Tkinter wm_attributes -alpha
def set_do_not_disturb(self, enabled: bool) -> None:
    self._do_not_disturb = enabled
    self._overlay.attributes("-alpha", 0.6 if enabled else 1.0)
    # Остановить pulse если DnD включён
    if enabled and self._pulse_active:
        self._stop_pulse()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `win10toast` | `winotify` | 2022 | winotify активнее, win10toast стагнантный |
| `keyboard` library для hotkeys | `pynput` | 2022+ | keyboard требует elevation, pynput нет |
| `python-jose` для JWT | `PyJWT` | 2024 | python-jose abandoned, FastAPI мигрировал |
| `icon.run()` в отдельном thread | `icon.run_detached()` | pystray 0.17+ | run_detached() официальный способ не блокировать caller |
| Tkinter `Canvas.create_rectangle()` | Pillow → Canvas ImageItem | всегда | Pillow даёт gradient + антиалиасинг; Canvas shapes без них |

**Deprecated/outdated:**
- `win10toast`: последний релиз 2020, не поддерживается
- `python-jose`: abandoned 2021, CVE-риски
- `keyboard` library для global hotkeys: stagnant 2022+, elevation issues

---

## Open Questions

1. **Rounded corners на Windows 10**
   - What we know: `DwmSetWindowAttribute(33)` работает только на Windows 11 (атрибут добавлен в 11)
   - What's unclear: Насколько критично для Никиты (он на Win 11 на работе)
   - Recommendation: Использовать DWM для Win11, Pillow RGBA transparent corners для Win10 как fallback. Определять через `sys.getwindowsversion().build >= 22000`.

2. **winotify click handler (открыть окно по клику на toast)**
   - What we know: `winotify.Notifier.register_callback()` поддерживает это, но требует running subprocess и `__main__` guard
   - What's unclear: Работает ли в PyInstaller frozen exe (Phase 6 concern)
   - Recommendation: Пропустить для Phase 3. Клик просто закрывает toast (нативное Windows поведение). NOTIF требования не требуют click-to-open.

3. **winotify maintenance status**
   - What we know: Последний релиз 1.1.0 был Feb 2022 (4 года назад)
   - What's unclear: Совместимость с будущими Windows updates
   - Recommendation: Использовать в Phase 3-5. Для Phase 6 добавить try/except с fallback на tray balloon tip через `win32gui.Shell_NotifyIcon`.

4. **Pillow performance при 60fps pulse на слабом CPU**
   - What we know: Создание PIL Image 56×56 каждые 16ms — теоретически <1% CPU
   - What's unclear: Реальные числа на Intel HD Graphics без dedicate GPU
   - Recommendation: Пре-рендерить 30 frames при старте если жалобы. Начать с live-render.

---

## Validation Architecture

> `nyquist_validation: true` в config.json — секция обязательна.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + customtkinter headless (Tk supports update() without mainloop) |
| Config file | `client/pyproject.toml` (уже существует из Phase 2) |
| Quick run command | `python -m pytest client/tests/test_overlay.py client/tests/test_tray.py -x -q` |
| Full suite command | `python -m pytest client/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OVR-01 | OverlayManager создаётся без crash | unit | `pytest client/tests/test_overlay.py::test_overlay_creates -x` | ❌ Wave 0 |
| OVR-02 | Позиция сохраняется в settings.json | unit | `pytest client/tests/test_overlay.py::test_position_persists -x` | ❌ Wave 0 |
| OVR-03 | Multi-monitor bounds calculation корректна | unit | `pytest client/tests/test_overlay.py::test_virtual_bounds -x` | ❌ Wave 0 |
| OVR-04 | Клик toggle открывает/закрывает main_window | unit | `pytest client/tests/test_overlay.py::test_click_toggles_window -x` | ❌ Wave 0 |
| OVR-05 | Pulse start при is_overdue, stop при cleared | unit | `pytest client/tests/test_overlay.py::test_pulse_state -x` | ❌ Wave 0 |
| OVR-06 | always_on_top применяется к обоим окнам | unit | `pytest client/tests/test_overlay.py::test_always_on_top -x` | ❌ Wave 0 |
| TRAY-01 | TrayManager.start() без crash (mock pystray) | unit | `pytest client/tests/test_tray.py::test_tray_starts -x` | ❌ Wave 0 |
| TRAY-02 | Callbacks через root.after(0, ...) — не напрямую | unit | `pytest client/tests/test_tray.py::test_callbacks_via_after -x` | ❌ Wave 0 |
| TRAY-03 | Настройка theme сохраняется в settings.json | integration | `pytest client/tests/test_tray.py::test_theme_persists -x` | ❌ Wave 0 |
| TRAY-04 | 20 быстрых кликов без RuntimeError (mock) | integration | `pytest client/tests/test_tray.py::test_rapid_clicks -x` | ❌ Wave 0 |
| NOTIF-01 | do_not_disturb=True блокирует send_toast | unit | `pytest client/tests/test_notifications.py::test_dnd_blocks_toast -x` | ❌ Wave 0 |
| NOTIF-02 | winotify.Notification.show() вызывается (mock) | unit | `pytest client/tests/test_notifications.py::test_toast_sends -x` | ❌ Wave 0 |
| NOTIF-03 | check_deadlines находит задачу в [-5min, 0] | unit | `pytest client/tests/test_notifications.py::test_deadline_detection -x` | ❌ Wave 0 |
| NOTIF-04 | silent режим блокирует toast | unit | `pytest client/tests/test_notifications.py::test_silent_mode -x` | ❌ Wave 0 |

### Test Strategy для Tkinter Code

**Tkinter headless approach:** CustomTkinter/Tk поддерживает создание виджетов и вызов `update()` без `mainloop()`. Это позволяет тестировать:

```python
# Source: Tk headless testing pattern
import pytest
import customtkinter as ctk

@pytest.fixture(scope="session")
def tk_root():
    """Одиночный CTk root для всей test session."""
    root = ctk.CTk()
    root.withdraw()  # скрыть окно
    yield root
    root.destroy()

def test_overlay_creates(tk_root, tmp_appdata):
    from client.ui.overlay import OverlayManager
    from client.core.storage import LocalStorage
    storage = LocalStorage(AppPaths())
    storage.init()
    overlay = OverlayManager(tk_root, storage, ...)
    tk_root.update()  # процессировать pending events
    assert overlay._overlay.winfo_exists()
```

**Mock pystray:**
```python
# Полный mock без реального tray (для CI без display)
@pytest.fixture
def mock_pystray(monkeypatch):
    class FakeIcon:
        def __init__(self, *a, **kw): self.icon = None; self.title = ""
        def run_detached(self): pass
        def stop(self): pass
        def update_menu(self): pass
    monkeypatch.setattr("pystray.Icon", FakeIcon)
```

**Mock winotify:**
```python
@pytest.fixture
def mock_winotify(monkeypatch):
    calls = []
    class FakeNotification:
        def __init__(self, **kw): self._kw = kw
        def show(self): calls.append(self._kw)
    monkeypatch.setattr("winotify.Notification", FakeNotification)
    return calls
```

### Sampling Rate

- **Per task commit:** `python -m pytest client/tests/test_overlay.py client/tests/test_tray.py client/tests/test_notifications.py -x -q`
- **Per wave merge:** `python -m pytest client/tests/ -q`
- **Phase gate:** Full suite green + manual verify success criteria из UI-SPEC.md §Success Criteria

### Wave 0 Gaps

- [ ] `client/tests/test_overlay.py` — covers OVR-01..06
- [ ] `client/tests/test_tray.py` — covers TRAY-01..04
- [ ] `client/tests/test_notifications.py` — covers NOTIF-01..04
- [ ] `client/tests/conftest.py` обновить: добавить `tk_root`, `mock_pystray`, `mock_winotify` fixtures

*(Существующий `client/tests/conftest.py` из Phase 2 имеет `tmp_appdata` + `mock_api` — расширить, не заменять)*

---

## Sources

### Primary (HIGH confidence)
- [PITFALLS.md](/planning/research/PITFALLS.md) — Pitfall 1 (overrideredirect delay), Pitfall 2 (pystray threading)
- [STACK.md](/planning/research/STACK.md) — версии библиотек, Gotcha 1 (DWM attribute), Gotcha 2 (pystray threading)
- [CustomTkinter Discussion #1302](https://github.com/TomSchimansky/CustomTkinter/discussions/1302) — rounded corners с overrideredirect на Win11
- [pystray Issue #94](https://github.com/moses-palmer/pystray/issues/94) — threading model (run_detached)
- [pystray docs 0.19.5](https://pystray.readthedocs.io/en/latest/reference.html) — update_menu(), run_detached(), callable menu properties
- [Pillow ImageDraw docs](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html) — rounded_rectangle() (Pillow 8.2+), line(), ellipse()
- [winotify PyPI](https://pypi.org/project/winotify/) — version 1.1.0, Feb 2022, pure Python + PowerShell
- [winotify README](https://github.com/versa-syahptr/winotify/blob/master/README.md) — absolute icon path requirement
- [Microsoft Learn: Multiple Monitor System Metrics](https://learn.microsoft.com/en-us/windows/win32/gdi/multiple-monitor-system-metrics) — virtual desktop coordinates
- [Microsoft Learn: DwmSetWindowAttribute](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmsetwindowattribute) — DWMWA_WINDOW_CORNER_PREFERENCE = 33, Windows 11 only
- [client/core/storage.py](/client/core/storage.py) — LocalStorage.load_settings() / save_settings() API
- [client/core/sync.py](/client/core/sync.py) — SyncManager.force_sync() API
- [client/core/auth.py](/client/core/auth.py) — AuthManager.logout() API

### Secondary (MEDIUM confidence)
- [CustomTkinter Discussion #2373](https://github.com/TomSchimansky/CustomTkinter/discussions/2373) — live theme switching limitations; requires configure() loop
- [CustomTkinter Issue #1461](https://github.com/TomSchimansky/CustomTkinter/issues/1461) — GUI performance; 60fps after() loop acceptable for small widgets
- [hPyT GitHub](https://github.com/Zingzy/hPyT) — альтернативный wrapper для DwmSetWindowAttribute
- [screeninfo GitHub](https://github.com/rr-/screeninfo/blob/master/screeninfo/enumerators/windows.py) — пример EnumDisplayMonitors через ctypes
- CustomTkinter Scaling Wiki — SetProcessDpiAwareness(2) default в CTk

### Tertiary (LOW confidence)
- Pillow gradient performance claims — extrapolated from community benchmarks, not formally measured для 56×56 @60fps

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — все библиотеки pinned в предыдущих research-фазах и верифицированы
- Architecture patterns: HIGH — pystray + Tk threading и overrideredirect delay верифицированы в официальных issues
- Pillow icon composition: HIGH — ImageDraw.rounded_rectangle stable с Pillow 8.2 (2021)
- winotify behavior: MEDIUM — API верифицирован через docs; subprocess-блокирующий характер выведен из source code, не измерен формально
- Multi-monitor positioning: MEDIUM — паттерн win32api.EnumDisplayMonitors верифицирован в Microsoft docs; edge cases (4+ monitors, vertical stacking) не тестировались
- Theme live switching: MEDIUM — limitation верифицирован в CustomTkinter discussions; callback-subscriber pattern — логический вывод

**Research date:** 2026-04-16
**Valid until:** 2026-06-16 (CustomTkinter и pystray стагнантны — долгий срок; winotify тоже)
