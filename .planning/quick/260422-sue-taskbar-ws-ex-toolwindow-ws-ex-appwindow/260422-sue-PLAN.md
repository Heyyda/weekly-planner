---
phase: quick-260422-sue
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/main_window.py
autonomous: false
requirements:
  - QUICK-260422-SUE-01
must_haves:
  truths:
    - "После запуска приложения главное окно не отображается в Windows taskbar"
    - "Alt+Tab не показывает главное окно в переключателе окон"
    - "Overlay (круглый drag-квадрат) продолжает быть видимым на рабочем столе"
    - "Tray-иконка (pystray) продолжает отображаться в системном трее"
    - "pytest client/tests/ui/test_main_window.py остаётся зелёным"
  artifacts:
    - path: "client/ui/main_window.py"
      provides: "_apply_borderless применяет WS_EX_TOOLWINDOW (скрывает из taskbar/Alt+Tab)"
      contains: "WS_EX_TOOLWINDOW"
  key_links:
    - from: "client/ui/main_window.py::_apply_borderless"
      to: "ctypes.windll.user32.SetWindowLongW"
      via: "bitmask: (current & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW"
      pattern: "~WS_EX_APPWINDOW.*\\|.*WS_EX_TOOLWINDOW"
---

<objective>
Убрать главное окно планировщика из Windows taskbar и Alt+Tab-переключателя.

Purpose: Приложение — overlay-first (круглый draggable оверлей + tray). Главное окно показывается при клике на оверлей и должно ощущаться как floating-панель, а не как полноценное taskbar-окно. Сейчас `_apply_borderless` ошибочно маскирует WS_EX_TOOLWINDOW и выставляет WS_EX_APPWINDOW — результат: окно видно в taskbar и Alt+Tab, что визуально дублирует оверлей и tray.

Output: Одна строка кода в `_apply_borderless` инвертирует маску + обновлённый docstring/комментарий. Overlay и tray не трогаются (они уже невидимы для taskbar через overrideredirect/pystray).
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@client/ui/main_window.py

<interfaces>
<!-- Текущий код строки 327-356 в client/ui/main_window.py -->

```python
def _apply_borderless(self) -> None:
    """UX v2: убрать native title bar. Сохранить taskbar через WS_EX_APPWINDOW.

    PITFALL 1 (Win11 DWM): overrideredirect должен вызываться после after(100, ...).
    PITFALL 6: ctypes.windll.user32.GetParent может вернуть 0 — graceful try/except.
    """
    try:
        self._window.overrideredirect(True)
    except tk.TclError as exc:
        logger.debug("overrideredirect failed: %s", exc)
        return

    # WS_EX_APPWINDOW — сохранить окно в taskbar и Alt+Tab
    try:
        hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
        if not hwnd:
            return
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new = (current & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)
        # Re-apply style: withdraw/deiconify цикл — только если окно видимо
        # (на первом старте окно withdraw'нуто, значит flash не случится).
        if self._window.winfo_viewable():
            self._window.withdraw()
            self._window.deiconify()
    except Exception as exc:
        logger.debug("WS_EX_APPWINDOW failed: %s", exc)
```

Грепом подтверждено: в `client/tests/ui/test_main_window.py` нет assertion-ов на `WS_EX_APPWINDOW` / `WS_EX_TOOLWINDOW` / `_apply_borderless` — обновлять тесты не нужно, достаточно убедиться что прогон остаётся зелёным.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Инвертировать EX_STYLE mask в _apply_borderless (WS_EX_TOOLWINDOW)</name>
  <files>client/ui/main_window.py</files>
  <action>
В `client/ui/main_window.py` в методе `_apply_borderless` выполнить ровно три правки (без других изменений в файле):

1. Строка 348 — инвертировать bitmask:

   Было:
   ```python
   new = (current & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
   ```
   Стало:
   ```python
   new = (current & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
   ```

2. Строка 328 — обновить docstring первой строкой:

   Было:
   ```
   """UX v2: убрать native title bar. Сохранить taskbar через WS_EX_APPWINDOW.
   ```
   Стало:
   ```
   """UX v2: убрать native title bar и скрыть из taskbar/Alt+Tab через WS_EX_TOOLWINDOW.
   ```

3. Строка 339 — обновить комментарий над ctypes-блоком:

   Было:
   ```
   # WS_EX_APPWINDOW — сохранить окно в taskbar и Alt+Tab
   ```
   Стало:
   ```
   # WS_EX_TOOLWINDOW — скрыть окно из taskbar и Alt+Tab (overlay+tray остаются видны)
   ```

НЕ трогать:
- `if self._window.winfo_viewable(): withdraw/deiconify` (строки 352-354) — этот цикл нужен чтобы Windows применил новый EX_STYLE. На первом старте окно withdrawn'нуто в `__init__`, поэтому flash не возникнет.
- Константы `GWL_EXSTYLE`, `WS_EX_APPWINDOW`, `WS_EX_TOOLWINDOW` — оставить обе, чтобы не ломать семантику маски.
- Логгирование в `except Exception as exc: logger.debug("WS_EX_APPWINDOW failed: %s", exc)` (строка 356) — сообщение относится к общему try-блоку, его можно оставить как есть (не критично для фикса).
- Overlay (`client/ui/overlay/overlay_manager.py`) и tray (`client/utils/tray.py`) — не трогать, они уже невидимы в taskbar.

Этот фикс соответствует правильному поведению `WS_EX_TOOLWINDOW`: окно остаётся topmost и draggable, но исключается из taskbar и Alt+Tab переключателя.
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник" &amp;&amp; python -m pytest client/tests/ui/test_main_window.py -x -q</automated>
    Дополнительно (grep-sanity, без запуска):
    - `grep -n "~WS_EX_APPWINDOW.*|.*WS_EX_TOOLWINDOW" client/ui/main_window.py` должен найти строку 348
    - `grep -n "WS_EX_APPWINDOW — сохранить" client/ui/main_window.py` должен НЕ найти ничего (старый комментарий удалён)
  </verify>
  <done>
    - Строка 348 `client/ui/main_window.py` содержит `new = (current & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW`
    - Docstring `_apply_borderless` упоминает "скрыть из taskbar/Alt+Tab через WS_EX_TOOLWINDOW"
    - Комментарий над ctypes-блоком упоминает "WS_EX_TOOLWINDOW — скрыть окно из taskbar и Alt+Tab (overlay+tray остаются видны)"
    - `python -m pytest client/tests/ui/test_main_window.py -x -q` — зелёный (или ни одного нового падения относительно базы)
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: UAT — проверить исчезновение окна из taskbar и Alt+Tab</name>
  <what-built>
    В `_apply_borderless` инвертирована EX_STYLE-маска: теперь применяется `WS_EX_TOOLWINDOW` вместо `WS_EX_APPWINDOW`. Главное окно должно пропасть из Windows taskbar и Alt+Tab-переключателя, оставаясь полноценно функциональным при клике на overlay.
  </what-built>
  <how-to-verify>
    1. Запусти приложение: `python main.py` (или собранный `.exe`, если есть).
    2. Убедись что:
       - Overlay (круглый draggable-квадрат на рабочем столе) — **виден**.
       - Tray-иконка "Личный Еженедельник" — **видна** в системном трее (возле часов).
    3. Проверь **taskbar** (панель задач внизу экрана):
       - Иконки "Личный Еженедельник" **не должно быть** среди активных окон.
    4. Кликни на overlay — откроется главное окно планировщика.
    5. С открытым главным окном:
       - Нажми **Alt+Tab** — окно "Личный Еженедельник" **не должно** появиться в переключателе окон.
       - В taskbar окно **тоже не должно** появиться.
    6. Взаимодействуй с окном: drag за title bar, resize за нижний правый угол, кнопка закрытия — всё должно работать как раньше.
    7. Закрой окно через крестик, затем открой снова кликом на overlay — должно работать штатно.

    Ожидаемый результат: окно ведёт себя как floating tool-window — видимо и функционально, но невидимо в системных списках окон.

    Если что-то не работает (окно появилось в taskbar / Alt+Tab показывает его / overlay сломался) — опиши что именно.
  </how-to-verify>
  <resume-signal>Напиши "approved" если всё работает, либо опиши наблюдаемое поведение</resume-signal>
</task>

</tasks>

<verification>
- `client/ui/main_window.py:348` применяет WS_EX_TOOLWINDOW (не WS_EX_APPWINDOW)
- Docstring и комментарий в `_apply_borderless` консистентны с новым поведением
- `pytest client/tests/ui/test_main_window.py` — зелёный
- UAT: окно отсутствует в taskbar и Alt+Tab при живой работе overlay+tray
</verification>

<success_criteria>
- После запуска приложения: главное окно отсутствует в Windows taskbar
- Alt+Tab не включает главное окно в переключатель
- Overlay и tray-иконка работают без регрессий
- Drag, resize, close главного окна через кастомный title bar — функциональны
- Прогон `pytest client/tests/ui/test_main_window.py` — зелёный
</success_criteria>

<output>
После выполнения обоих task'ов создать `.planning/quick/260422-sue-taskbar-ws-ex-toolwindow-ws-ex-appwindow/260422-sue-SUMMARY.md` с краткой записью: что изменено (1 строка кода + 2 текстовых), результат pytest, результат UAT, коммит hash.
</output>
