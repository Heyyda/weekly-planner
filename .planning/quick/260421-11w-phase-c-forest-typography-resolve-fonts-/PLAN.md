---
phase: 260421-11w
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/themes.py
  - client/app.py
  - client/ui/quick_capture.py
  - client/tests/ui/test_themes.py
autonomous: true
requirements: [FOREST-C-01, FOREST-C-02, FOREST-C-03]
must_haves:
  truths:
    - "На Win10 без Cascadia Mono mono-шрифт корректно падает на Consolas → Courier New → TkFixedFont"
    - "На Win10/Win11 с Segoe UI Variable отсутствующим — используется Segoe UI"
    - "Все CTk виджеты, содержащие текст, применяют FONTS[role] из themes.py (а не CTk-дефолт Roboto)"
    - "init_fonts(root) выполняется сразу после создания Tk root в app.py — до любых виджетов"
  artifacts:
    - path: client/ui/themes.py
      provides: "init_fonts(root) + mutable _FONT_FAMILY / _FONT_MONO"
      contains: "def init_fonts"
    - path: client/app.py
      provides: "init_fonts(self.root) после ctk.CTk()"
      contains: "init_fonts"
    - path: client/ui/quick_capture.py
      provides: "font=FONTS['body'] на CTkEntry"
    - path: client/tests/ui/test_themes.py
      provides: "test_init_fonts_picks_fallback"
  key_links:
    - from: client/app.py
      to: client/ui/themes.init_fonts
      via: "вызов init_fonts(self.root) сразу после ctk.CTk()"
      pattern: "init_fonts\\(self\\.root\\)"
    - from: client/ui/themes.py FONTS dict
      to: "consumers: main_window, week_navigation, day_section, task_widget, edit_dialog, undo_toast, update_banner, login_dialog, quick_capture"
      via: "import FONTS — mutation dict in-place сохраняет ссылки"
      pattern: "FONTS\\[\"[a-z_]+\"\\]"
---

<objective>
Forest Refactor Phase C — Typography. Две задачи:
1. **Runtime font resolution**: добавить `init_fonts(root)` в themes.py, которая через `tkinter.font.families(root)` выбирает лучший доступный шрифт из fallback-цепочки (sans: Segoe UI Variable → Segoe UI → Arial → TkDefaultFont; mono: Cascadia Mono → Cascadia Code → Consolas → Courier New → TkFixedFont). Мутирует модульные `_FONT_FAMILY` / `_FONT_MONO` и ОБНОВЛЯЕТ dict FONTS in-place — ссылки у всех потребителей остаются валидными.
2. **UI audit**: grep показал одно упущение — `client/ui/quick_capture.py` CTkEntry создаётся без `font=`. Добавить `font=FONTS["body"]`. Все остальные виджеты (main_window, day_section, task_widget, edit_dialog, undo_toast, update_banner, login_dialog, week_navigation) уже используют FONTS из themes — подтверждено через Grep.

Purpose: Win10 без Segoe UI Variable / Cascadia Mono silent-fallback'ил к MS Sans Serif / дефолт. Runtime-резолв через `tkinter.font.families()` устраняет эту разницу. Плюс QuickCapturePopup — самый частый entry-point capture-flow — сейчас показывает placeholder дефолтным CTk шрифтом (Roboto-like), не Segoe UI. Несогласованность с остальным UI.

Output: themes.py + app.py + quick_capture.py + targeted тест.
</objective>

<context>
Phase A (palette), A2 (frameless), A3 (Win10 hotfix: Segoe UI Variable → Segoe UI) уже закоммичены.

CLAUDE.md стек: CustomTkinter 5.2+ поверх tkinter. `tkinter.font.families(root)` требует живой Tk root — поэтому резолв должен быть function-call'ом, не import-time.

Референс UI-SPEC (design-forest.md §2 type scale):
- h1 16 bold, h2 14 bold, body 13, body_m 13 bold, caption 11, small 10, icon 24 bold
- mono 12 для времени HH:MM

Все существующие виджеты используют FONTS через `from client.ui.themes import FONTS`. Т.к. dict мутируется in-place (FONTS["h1"] = (...)), переприсваиваний у потребителей не нужно.
</context>

<interfaces>
Current themes.py FONTS (module-level, tuple format):
```python
_FONT_FAMILY = "Segoe UI"
_FONT_MONO = "Cascadia Mono"
FONTS: dict[str, tuple] = {
    "h1": (_FONT_FAMILY, 16, "bold"),
    "h2": (_FONT_FAMILY, 14, "bold"),
    "body": (_FONT_FAMILY, 13, "normal"),
    "body_m": (_FONT_FAMILY, 13, "bold"),
    "caption": (_FONT_FAMILY, 11, "normal"),
    "small": (_FONT_FAMILY, 10, "normal"),
    "icon": (_FONT_FAMILY, 24, "bold"),
    "mono": (_FONT_MONO, 12, "normal"),
}
```

API после Task 1:
```python
def init_fonts(root) -> None:
    """Резолв Segoe UI / Cascadia Mono через tkinter.font.families(root).
    Мутирует _FONT_FAMILY, _FONT_MONO и FONTS dict in-place."""
```

Fallback chains:
- SANS = ["Segoe UI Variable", "Segoe UI", "Arial", "TkDefaultFont"]
- MONO = ["Cascadia Mono", "Cascadia Code", "Consolas", "Courier New", "TkFixedFont"]
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: init_fonts(root) в themes.py + тест fallback</name>
  <files>client/ui/themes.py, client/tests/ui/test_themes.py</files>
  <action>
В `client/ui/themes.py`:
1. Импорт `tkinter.font as tkfont` вверху
2. Оставить текущие дефолты `_FONT_FAMILY = "Segoe UI"` и `_FONT_MONO = "Cascadia Mono"` (pre-init значения — для legacy тестов и предотвращения крашей при раннем доступе)
3. Объявить константы:
```python
_SANS_FALLBACK = ("Segoe UI Variable", "Segoe UI", "Arial", "TkDefaultFont")
_MONO_FALLBACK = ("Cascadia Mono", "Cascadia Code", "Consolas", "Courier New", "TkFixedFont")
```
4. Добавить функцию:
```python
def init_fonts(root) -> None:
    """Резолв sans/mono семейств через tkinter.font.families(root).
    Мутирует _FONT_FAMILY / _FONT_MONO и перестраивает FONTS dict in-place.
    Вызывать СРАЗУ после создания Tk root, до любых виджетов."""
    global _FONT_FAMILY, _FONT_MONO
    try:
        available = set(tkfont.families(root))
    except Exception as exc:
        logger.warning("tkfont.families() failed: %s — используем дефолты", exc)
        return
    sans = _pick_family(_SANS_FALLBACK, available, "TkDefaultFont")
    mono = _pick_family(_MONO_FALLBACK, available, "TkFixedFont")
    _FONT_FAMILY = sans
    _FONT_MONO = mono
    # Пересобрать FONTS in-place — сохраняет dict ref у всех импортёров
    FONTS["h1"]      = (sans, 16, "bold")
    FONTS["h2"]      = (sans, 14, "bold")
    FONTS["body"]    = (sans, 13, "normal")
    FONTS["body_m"]  = (sans, 13, "bold")
    FONTS["caption"] = (sans, 11, "normal")
    FONTS["small"]   = (sans, 10, "normal")
    FONTS["icon"]    = (sans, 24, "bold")
    FONTS["mono"]    = (mono, 12, "normal")
    logger.info("Fonts resolved: sans=%r mono=%r", sans, mono)


def _pick_family(candidates: tuple, available: set, final_fallback: str) -> str:
    """Первый из candidates присутствующий в available. Иначе final_fallback."""
    for fam in candidates:
        if fam in available:
            return fam
    return final_fallback
```

Важно: НЕ менять `logger = logging.getLogger(__name__)` объявление. Не трогать PALETTES. Не трогать размеры/веса в FONTS — только family-строки.

В `client/tests/ui/test_themes.py`:
1. Убрать/смягчить хрупкий тест `test_fonts_has_segoe_and_cascadia` (строки 70-73) — на CI без шрифтов он всё равно работает, т.к. init не вызывается; но чтобы было явно, переименовать assertion в "до init_fonts всё ещё дефолтные имена":
```python
def test_fonts_default_names_before_init():
    # До init_fonts — модульные дефолты (Segoe UI + Cascadia Mono)
    # Реальный резолв проверяется в test_init_fonts_picks_fallback.
    assert FONTS["body"][0] == "Segoe UI"
    assert FONTS["mono"][0] in ("Cascadia Code", "Cascadia Mono")
```
2. Добавить новый тест:
```python
def test_init_fonts_picks_fallback_when_families_empty(monkeypatch):
    """init_fonts: если tkfont.families() пустой → sans→TkDefaultFont, mono→TkFixedFont."""
    from client.ui import themes as themes_mod
    monkeypatch.setattr(
        "tkinter.font.families",
        lambda root=None: (),
        raising=False,
    )
    # root не нужен реально — mock перехватывает вызов
    themes_mod.init_fonts(root=None)
    assert themes_mod.FONTS["body"][0] == "TkDefaultFont"
    assert themes_mod.FONTS["mono"][0] == "TkFixedFont"
    # Восстановить дефолты для последующих тестов — повторный init с полным набором
    monkeypatch.setattr(
        "tkinter.font.families",
        lambda root=None: ("Segoe UI", "Cascadia Mono", "Arial", "Consolas"),
        raising=False,
    )
    themes_mod.init_fonts(root=None)
    assert themes_mod.FONTS["body"][0] == "Segoe UI"
    assert themes_mod.FONTS["mono"][0] == "Cascadia Mono"


def test_init_fonts_prefers_segoe_variable_when_available(monkeypatch):
    from client.ui import themes as themes_mod
    monkeypatch.setattr(
        "tkinter.font.families",
        lambda root=None: ("Segoe UI Variable", "Segoe UI", "Consolas"),
        raising=False,
    )
    themes_mod.init_fonts(root=None)
    assert themes_mod.FONTS["body"][0] == "Segoe UI Variable"
    assert themes_mod.FONTS["mono"][0] == "Consolas"
    # Восстановить для остальных тестов
    monkeypatch.setattr(
        "tkinter.font.families",
        lambda root=None: ("Segoe UI", "Cascadia Mono"),
        raising=False,
    )
    themes_mod.init_fonts(root=None)
```
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && python -m pytest client/tests/ui/test_themes.py -x -q</automated>
  </verify>
  <done>init_fonts резолвит fallback; оба новых теста проходят; legacy Segoe UI / Cascadia Mono assertion адаптирован.</done>
</task>

<task type="auto">
  <name>Task 2: Wire init_fonts в app.py + font= на quick_capture CTkEntry</name>
  <files>client/app.py, client/ui/quick_capture.py</files>
  <action>
В `client/app.py`:
1. Импорт: `from client.ui.themes import ThemeManager, init_fonts` (дополнить существующий импорт `ThemeManager`).
2. В `WeeklyPlannerApp.__init__`, СРАЗУ после `self.root = ctk.CTk()` и `self.root.withdraw()` (строки 80-81) добавить:
```python
        # Phase C: runtime font resolution (Segoe UI / Cascadia Mono fallback chain).
        # Должно быть ДО создания любых виджетов — FONTS dict мутируется in-place.
        try:
            init_fonts(self.root)
        except Exception as exc:
            logger.warning("init_fonts failed: %s — используем дефолты", exc)
```

В `client/ui/quick_capture.py`:
1. Импорт: заменить `from client.ui.themes import ThemeManager` на `from client.ui.themes import FONTS, ThemeManager`.
2. В `_init_popup_style()` при создании `self._entry = ctk.CTkEntry(...)` (строка 124) добавить параметр `font=FONTS["body"]`:
```python
        self._entry = ctk.CTkEntry(
            frame,
            placeholder_text="Новая задача на сегодня...",
            border_width=0,
            fg_color=self._theme.get("bg_secondary"),
            font=FONTS["body"],
        )
```
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && python -m pytest client/tests/ui/test_themes.py client/tests/ui/test_quick_capture.py -x -q</automated>
  </verify>
  <done>init_fonts вызван в app.__init__; quick_capture._entry получил font=FONTS["body"]; тесты проходят.</done>
</task>

<task type="auto">
  <name>Task 3: SUMMARY.md + atomic commit</name>
  <files>.planning/quick/260421-11w-phase-c-forest-typography-resolve-fonts-/SUMMARY.md</files>
  <action>
Написать краткий SUMMARY.md с списком touched files, testing evidence и проверкой что остальные UI-файлы уже были корректны (grep audit result).

Затем atomic commit:
```
feat(ui): Forest Phase C — typography fallback + consistent FONTS

- themes.py: init_fonts(root) резолвит Segoe UI / Cascadia Mono через tkinter.font.families()
  fallback chain: Segoe UI Variable → Segoe UI → Arial; Cascadia Mono → Consolas → Courier New
- app.py: init_fonts(self.root) вызван сразу после ctk.CTk()
- Audit: проставлен font=FONTS["body"] на quick_capture CTkEntry (был единственный пропуск)
- Тесты: добавлены test_init_fonts_picks_fallback_when_families_empty +
  test_init_fonts_prefers_segoe_variable_when_available

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && git log -1 --oneline && git status</automated>
  </verify>
  <done>SUMMARY.md существует; коммит создан; git status чистый.</done>
</task>

</tasks>

<verification>
- pytest client/tests/ui/test_themes.py — 2 новых теста проходят + legacy assertions работают
- pytest client/tests/ui/test_quick_capture.py — не сломан (font= не влияет на focus/visibility-логику)
- git status чистый, один commit добавлен
</verification>

<success_criteria>
1. `init_fonts(root)` существует в themes.py и вызывается в app.__init__ сразу после ctk.CTk()
2. QuickCapturePopup CTkEntry теперь использует FONTS["body"]
3. Тесты test_init_fonts_picks_fallback_* проходят
4. Atomic git commit создан
</success_criteria>

<output>
SUMMARY.md в .planning/quick/260421-11w-phase-c-forest-typography-resolve-fonts-/
</output>
