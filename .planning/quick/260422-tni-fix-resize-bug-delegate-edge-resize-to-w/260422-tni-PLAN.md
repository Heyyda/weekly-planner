---
phase: quick-260422-tni
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/main_window.py
autonomous: false
requirements:
  - RESIZE-FIX-01
must_haves:
  truths:
    - "Тяга мышью за правый/левый edge реально меняет ширину окна"
    - "Тяга мышью за нижний/верхний edge меняет высоту окна"
    - "Тяга за угол (nw/ne/sw/se) меняет оба измерения одновременно"
    - "Окно можно и увеличить, и уменьшить обратно через drag любого edge"
    - "MIN_SIZE (минимальный размер окна) уважается — окно не сжимается меньше минимума"
    - "После resize новая геометрия сохраняется в settings.json при закрытии окна"
  artifacts:
    - path: "client/ui/main_window.py"
      provides: "Edge-resize через нативный Win32 WM_NCLBUTTONDOWN"
      contains: "SendMessageW"
  key_links:
    - from: "client/ui/main_window.py:_on_edge_press"
      to: "user32.SendMessageW"
      via: "ctypes.windll.user32.ReleaseCapture() + SendMessageW(hwnd, WM_NCLBUTTONDOWN, ht, 0)"
      pattern: "SendMessageW.*0x00A1"
    - from: "<ButtonPress-1> на edge-zone"
      to: "_on_edge_press(event, edge)"
      via: "существующий bind в _build_edge_resizers"
      pattern: "ButtonPress-1.*_on_edge_press"
    - from: "Win32 resize → Configure event"
      to: "_on_configure → settings.window_size/position"
      via: "существующий <Configure> bind обновляет in-memory state, flush в _save_window_state при закрытии"
      pattern: "_on_configure"
---

<objective>
Фикс бага: resize главного окна через Python event handlers (`<B1-Motion>`) ненадёжен на `overrideredirect(True)` окне — окно увеличивается только по y, не уменьшается обратно, event coords drift между zones. Заменить кастомный drag-цикл на нативный Win32 `SendMessage(WM_NCLBUTTONDOWN, HT_*)` — Windows сам перехватит мышь и выполнит resize как для native-рамки.

Purpose: speed-of-capture требует стабильного UI окна. Сломанный resize — визуальный раздражитель, владелец упирается в него при каждом запуске.
Output: упрощённый `_on_edge_press`, удалённые `_on_edge_drag`/`_on_edge_release`, удалённые атрибуты `_resize_edge`/`_resize_start_*`. Resize работает нативно через Win32.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@client/ui/main_window.py

<interfaces>
<!-- Текущая структура атрибутов/методов в MainWindow, релевантных задаче. -->
<!-- Executor использует напрямую — дополнительной разведки не нужно. -->

Атрибуты в __init__ (строки 114-122), которые УДАЛЯЮТСЯ:
```python
self._resize_start_w = 0
self._resize_start_h = 0
self._resize_start_x = 0
self._resize_start_y = 0
self._resize_edge: Optional[str] = None
self._resize_start_win_x = 0
self._resize_start_win_y = 0
```
Оставить: `self._edge_zones: list = []` — используется в `_build_edge_resizers`.

Существующие bindings в `_build_edge_resizers` (строки 472-477):
```python
zone.bind("<ButtonPress-1>", lambda e, edge=edge_name: self._on_edge_press(e, edge))
zone.bind("<B1-Motion>", self._on_edge_drag)        # УДАЛИТЬ
zone.bind("<ButtonRelease-1>", self._on_edge_release)  # УДАЛИТЬ
```

Текущий `_on_edge_press` (строки 481-492) — ПЕРЕПИСАТЬ целиком (см. action Task 1).
Текущие `_on_edge_drag` (494-519) и `_on_edge_release` (521-526) — УДАЛИТЬ.

Модуль уже импортирует:
- `import ctypes` (строка 21)
- `import logging` (строка 22) — logger инициализируется внутри модуля; если не инициализирован, проверить и добавить `logger = logging.getLogger(__name__)` на уровне модуля.

Константа MIN_SIZE уже существует на уровне класса; `self._window.minsize(*MIN_SIZE)` вызывается в `__init__` — Windows WM_GETMINMAXINFO увидит это значение автоматически.

Класс MainWindow уже имеет `_on_configure` bind на `<Configure>`, который обновляет `self._settings.window_size/position` в памяти при любом изменении geometry (в том числе native-resize через Windows). `_save_window_state()` вызывается в `_on_close`.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Delegate edge-resize к Win32 через WM_NCLBUTTONDOWN</name>
  <files>client/ui/main_window.py</files>
  <action>
Делегируем resize Windows-у, удаляем Python-овый drag-цикл.

1. **Добавить константу `HT_MAP`** на уровне класса `MainWindow` (рядом с `MIN_SIZE`):
```python
# Win32 hit-test codes для WM_NCLBUTTONDOWN
HT_MAP = {
    "n":  12,  # HT_TOP
    "s":  15,  # HT_BOTTOM
    "w":  10,  # HT_LEFT
    "e":  11,  # HT_RIGHT
    "nw": 13,  # HT_TOPLEFT
    "ne": 14,  # HT_TOPRIGHT
    "sw": 16,  # HT_BOTTOMLEFT
    "se": 17,  # HT_BOTTOMRIGHT
}
_WM_NCLBUTTONDOWN = 0x00A1
```

2. **Удалить атрибуты из `__init__`** (строки 114-122):
```python
# УДАЛИТЬ ВСЕ 7 строк:
self._resize_start_w = 0
self._resize_start_h = 0
self._resize_start_x = 0
self._resize_start_y = 0
self._resize_edge: Optional[str] = None
self._resize_start_win_x = 0
self._resize_start_win_y = 0
```
Оставить только `self._edge_zones: list = []` — используется в `_build_edge_resizers`.

3. **Заменить `_on_edge_press`** на Win32-делегацию:
```python
def _on_edge_press(self, event, edge: str) -> None:
    """Делегировать resize Windows-у: WM_NCLBUTTONDOWN(HT_*).

    Custom <B1-Motion> ресайз на overrideredirect окне ненадёжен:
    event-coords drift между edge-zones, motion events теряются.
    Win32-способ: отпустить Tk capture + отправить WM_NCLBUTTONDOWN с
    hit-test кодом — Windows сам перехватит мышь и отресайзит окно с
    respect к minsize (через WM_GETMINMAXINFO).
    """
    ht = self.HT_MAP.get(edge)
    if ht is None:
        return
    try:
        user32 = ctypes.windll.user32
        # winfo_id() возвращает hwnd виджета; для toplevel = hwnd окна.
        # GetParent может вернуть настоящий Windows-hwnd (Tk иногда оборачивает).
        widget_hwnd = self._window.winfo_id()
        parent_hwnd = user32.GetParent(widget_hwnd)
        hwnd = parent_hwnd if parent_hwnd else widget_hwnd
        if not hwnd:
            return
        # ReleaseCapture обязателен: без него Windows не видит button-state.
        user32.ReleaseCapture()
        # SendMessageW возвращается сразу; resize продолжается асинхронно.
        user32.SendMessageW(hwnd, self._WM_NCLBUTTONDOWN, ht, 0)
    except Exception as exc:
        logger.debug("Win32 edge-resize failed (edge=%s): %s", edge, exc)
```

4. **Удалить методы** `_on_edge_drag` (строки 494-519) и `_on_edge_release` (строки 521-526) целиком.

5. **В `_build_edge_resizers`** (строки 472-477) удалить 2 bind-а:
```python
# УДАЛИТЬ:
zone.bind("<B1-Motion>", self._on_edge_drag)
zone.bind("<ButtonRelease-1>", self._on_edge_release)
```
Оставить только `zone.bind("<ButtonPress-1>", lambda e, edge=edge_name: self._on_edge_press(e, edge))`.

6. **Проверить `logger`**: если в начале файла нет `logger = logging.getLogger(__name__)`, добавить его после `import`-ов (модуль уже импортирует `logging` — строка 22).

7. **Persistence**: ничего не трогаем. `<Configure>` bind + `_on_configure` уже обновляют `settings.window_size/position` в памяти при любом resize (включая Win32-initiated). `_save_window_state` вызывается в `_on_close` — этого достаточно. НЕ добавлять новый hook на "конец resize" — Win32 не даёт такого события в Tkinter напрямую, а sync при close закрывает проблему.

**Pitfalls для executor:**
- `GetParent(widget_hwnd)` на Toplevel может вернуть 0 — в этом случае fallback на сам `widget_hwnd`. В коде это уже учтено через `hwnd = parent_hwnd if parent_hwnd else widget_hwnd`.
- `ReleaseCapture()` ДО `SendMessageW` — иначе Windows не переключится в resize-mode.
- `ctypes.windll.user32` доступен только на Windows; весь код уже в Windows-specific модуле (see CLAUDE.md platform requirements).
- Никаких импортов дополнять не надо — `ctypes` уже импортирован (строка 21).
  </action>
  <verify>
  <automated>python -m py_compile client/ui/main_window.py</automated>
  Дополнительная проверка: `grep -c "_on_edge_drag\|_on_edge_release\|_resize_edge\|_resize_start" client/ui/main_window.py` должен вернуть `0`.
  Также: `grep -c "SendMessageW\|WM_NCLBUTTONDOWN\|HT_MAP" client/ui/main_window.py` должен вернуть `>=3`.
  </verify>
  <done>
  - `_on_edge_press` использует `ctypes.windll.user32.SendMessageW` с `WM_NCLBUTTONDOWN` (0x00A1).
  - `_on_edge_drag`, `_on_edge_release` — удалены.
  - Атрибуты `_resize_edge`, `_resize_start_w/h/x/y`, `_resize_start_win_x/y` — удалены из `__init__`.
  - В `_build_edge_resizers` остался только `<ButtonPress-1>` bind (без `<B1-Motion>` и `<ButtonRelease-1>`).
  - `HT_MAP` и `_WM_NCLBUTTONDOWN` константы на уровне класса MainWindow.
  - Модуль компилируется без ошибок.
  - `logger = logging.getLogger(__name__)` присутствует в модуле.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: UAT — проверить resize по всем 8 edge-zones</name>
  <what-built>
  Edge-resize главного окна делегирован Windows через `SendMessage(WM_NCLBUTTONDOWN, HT_*)`. Custom Python drag-цикл удалён. Windows теперь управляет ресайзом на уровне OS — как для обычных окон с рамкой.
  </what-built>
  <how-to-verify>
  1. Запустить: `python main.py`
  2. Дождаться появления главного окна (выезжает из правого края или открывается).
  3. Навести мышь на **правый edge** (курсор → ↔). Зажать левую кнопку, перетащить влево → окно должно **уменьшить ширину**. Перетащить вправо → окно должно **увеличить ширину**.
  4. Повторить для **левого edge** (тяга вправо = ужимаем, влево = расширяем; при этом окно должно оставаться прижатым правым краем).
  5. Повторить для **нижнего edge** (↕) — тяга вверх/вниз меняет высоту.
  6. Повторить для **верхнего edge** — тяга вверх/вниз меняет высоту; окно должно оставаться прижатым нижним краем (top растёт/ужимается).
  7. Проверить **4 угла** (nw/ne/sw/se): диагональная тяга меняет оба измерения.
  8. Проверить **MIN_SIZE**: попробовать сжать окно сильно внутрь — оно должно остановиться на минимальном размере (не схлопнуться в 0).
  9. Закрыть окно (X или Alt+F4). Запустить снова — новый размер/позиция должны сохраниться.
  10. Проверить что **drag title-bar** (перетаскивание окна за шапку) всё ещё работает — мы не трогали этот код, но убедиться.

  Ожидаемое поведение: resize плавный, без рывков, без "залипания", окно свободно увеличивается И уменьшается в любом направлении.
  </how-to-verify>
  <resume-signal>Ответить "approved" если всё работает, или описать проблему (какой edge/угол не работает, какое поведение наблюдается).</resume-signal>
</task>

</tasks>

<verification>
Grep-проверки после Task 1:
- `grep -n "SendMessageW" client/ui/main_window.py` → найти вызов в `_on_edge_press`.
- `grep -n "_on_edge_drag\|_on_edge_release" client/ui/main_window.py` → 0 совпадений.
- `grep -n "_resize_start\|_resize_edge" client/ui/main_window.py` → 0 совпадений.
- `python -m py_compile client/ui/main_window.py` → без ошибок.

Manual UAT (Task 2): resize работает во всех 8 направлениях, MIN_SIZE соблюдается, persist через close.
</verification>

<success_criteria>
- Resize окна через любой из 8 edges работает стабильно (увеличение И уменьшение).
- Окно не уходит ниже MIN_SIZE.
- Геометрия сохраняется между запусками.
- Drag title-bar не регрессировал.
- Код упрощён: 3 метода → 1 метод, 7 атрибутов → 0 атрибутов.
</success_criteria>

<output>
После завершения создать `.planning/quick/260422-tni-fix-resize-bug-delegate-edge-resize-to-w/260422-tni-SUMMARY.md` с:
- Что изменилось в `client/ui/main_window.py` (методы удалены/переписаны, атрибуты удалены).
- Как проверили (UAT по 8 edges + MIN_SIZE + persist).
- Commit hash.
</output>
