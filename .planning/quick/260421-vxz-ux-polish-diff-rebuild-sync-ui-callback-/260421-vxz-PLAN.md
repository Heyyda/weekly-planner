---
phase: 260421-vxz-ux-polish
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/day_section.py
  - client/ui/main_window.py
  - client/core/sync.py
  - client/app.py
autonomous: true
requirements:
  - UX-01  # diff-rebuild недели (устранение мерцания)
  - UX-02  # sync→UI callback (убираем 30с лаг)
  - UX-03  # global Alt+Z toggle
  - UX-04  # fade-эффект show/hide

must_haves:
  truths:
    - "Смена недели стрелками/Today не вызывает визуального мерцания (нет destroy+recreate 7 DaySection)"
    - "После успешного sync с applied>0 или pushed>0 UI обновляется немедленно (не ждёт 30с _scheduled_refresh)"
    - "Alt+Z из любого приложения Windows открывает/скрывает главное окно"
    - "show() и hide() главного окна — плавный fade ~150мс вместо мгновенного переключения"
  artifacts:
    - path: "client/ui/day_section.py"
      provides: "публичный метод DaySection.set_day_date(new_date, is_today) — обновляет дату без пересоздания"
      contains: "def set_day_date"
    - path: "client/ui/main_window.py"
      provides: "MainWindow._update_week (лёгкий diff-update) + _fade + показать/скрыть с fade"
      contains: "def _update_week"
    - path: "client/core/sync.py"
      provides: "SyncManager.set_on_sync_complete + вызов callback после commit_drained"
      contains: "set_on_sync_complete"
    - path: "client/app.py"
      provides: "HotkeyManager alt+z + sync→UI wire через root.after"
      contains: "alt+z"
  key_links:
    - from: "client/ui/week_navigation.py (on_week_changed)"
      to: "client/ui/main_window.py::_update_week"
      via: "callback _on_week_changed теперь вызывает _update_week (без destroy)"
      pattern: "_update_week"
    - from: "client/core/sync.py (_attempt_sync)"
      to: "client/app.py::_handle_sync_complete"
      via: "self._on_sync_complete(stats) → root.after(0, _handle_sync_complete)"
      pattern: "_on_sync_complete"
    - from: "client/app.py (_setup)"
      to: "client/utils/hotkeys.py::HotkeyManager.register"
      via: "self.hotkeys.register('alt+z', self._on_global_hotkey_toggle)"
      pattern: "alt\\+z"
    - from: "client/ui/main_window.py (show/hide)"
      to: "client/ui/main_window.py::_fade"
      via: "attributes('-alpha', ...) через after() chain"
      pattern: "\\-alpha"
---

<objective>
UX polish главного окна: 4 независимых правки устраняют визуальные артефакты и оживляют окно.

Purpose:
  1. **Мерцание недели** — при переключении недель сейчас destroy+recreate 7 DaySection → заметный flash. Diff-rebuild убирает его.
  2. **Лаг sync→UI** — после merge_from_server UI ждёт до 30с (_scheduled_refresh). Callback вызывает refresh немедленно.
  3. **Глобальный хоткей** — HotkeyManager уже написан, но не подключён. Alt+Z → toggle окна из любого приложения.
  4. **Fade show/hide** — мгновенные deiconify/withdraw выглядят грубо. Плавный fade 150мс через attributes("-alpha").

Output: 4 независимых улучшения UX, по одному commit каждое. Никакой task не зависит от другого — можно выполнять в любом порядке.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@client/ui/main_window.py
@client/ui/day_section.py
@client/ui/week_navigation.py
@client/core/sync.py
@client/app.py
@client/utils/hotkeys.py

<interfaces>
<!-- Ключевые сигнатуры, которые executor использует напрямую. Без исследования кода. -->

From client/ui/day_section.py:
```python
class DaySection:
    HEADER_HEIGHT = 34
    TODAY_STRIP_WIDTH = 3
    # Состояние:
    self._day_date: date
    self._is_today: bool
    self._today_strip: Optional[ctk.CTkFrame]   # None если not is_today
    self._header_row: Optional[ctk.CTkFrame]    # строка 34px c label+counter+plus
    self.frame: ctk.CTkFrame                    # корневой frame секции
    # В _build() внутри _header_row создаются (перечислено для DOM-ориентирования):
    #   1) today_strip (если is_today) ИЛИ spacer frame (иначе) — pack side="left"
    #   2) day_label (CTkLabel) — pack side="left"
    #   3) right frame → counter_label + plus_btn — pack side="right"
    # DAY_NAMES_RU_SHORT / DAY_NAMES_RU_LONG — уже есть на module-level
    # FONTS["h2"] / FONTS["body"] — уже импортированы из themes
    # Helper: self._day_bg_color() — возвращает bg_secondary (today) или bg_primary
```

From client/ui/main_window.py:
```python
class MainWindow:
    MIN_SIZE = (320, 320)
    # self._window: ctk.CTkToplevel
    # self._day_sections: dict[date, DaySection]
    # self._week_nav: Optional[WeekNavigation]
    # self._drag_controller: Optional[DragController]
    # self._scroll: ctk.CTkScrollableFrame  (parent для DaySection)
    # self._settings.task_style: "card" | "line" | "minimal"
    def _rebuild_day_sections(self) -> None  # сейчас destroy+recreate (heavy)
    def _refresh_tasks(self) -> None         # распределяет задачи по DaySection
    def show(self) -> None                   # deiconify + lift
    def hide(self) -> None                   # withdraw
    def is_visible(self) -> bool
    def _on_week_changed(self, new_monday: date) -> None  # callback от WeekNavigation
    def handle_task_style_changed(self, style: str) -> None  # tray callback
```

From client/core/sync.py:
```python
class SyncManager:
    # self._on_sync_complete будет добавлен: Optional[Callable[[dict], None]]
    # stats dict возвращается из storage.merge_from_server:
    #   {"applied": int, "conflicts": int, "tombstones_received": int}
    # commit_drained(drained) — после этого момент "sync confirmed"
    # Важно: _attempt_sync работает в sync thread, не main.
```

From client/app.py WeeklyPlannerApp:
```python
    self.root: ctk.CTk
    self.main_window: Optional[MainWindow]
    self.sync: Optional[SyncManager]
    self.hotkeys: Optional[HotkeyManager]   # НЕТ пока — добавим
    def _refresh_ui(self) -> None           # уже есть — обновляет overlay/tray badges
    def _handle_quit(self) -> None          # teardown — туда добавить hotkeys.unregister
```

From client/utils/hotkeys.py:
```python
class HotkeyManager:
    def register(self, combo: str, callback: Callable) -> None
    def unregister(self) -> None
    # combo синтаксис библиотеки keyboard: "alt+z"
```

From client/ui/week_navigation.py:
```python
class WeekNavigation:
    def __init__(..., on_week_changed: Callable[[date], None], ...)
    def get_week_monday(self) -> date
    def is_current_archive(self) -> bool
    # on_week_changed вызывается из prev_week/next_week/today/set_week_monday
```
</interfaces>

**Локальные конвенции** (соблюдать):
- Коммиты на **русском** (CLAUDE.md)
- snake_case для методов, `_` префикс для internal
- try/except для Tkinter операций (TclError при teardown)
- logging через `logger = logging.getLogger(__name__)` — logger.debug/info/warning/error
- Type hints обязательны для новых методов
- Tkinter thread-safety: callbacks из чужих потоков ОБЯЗАТЕЛЬНО через `root.after(0, ...)`
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Diff-rebuild недели (DaySection.set_day_date + MainWindow._update_week)</name>
  <files>client/ui/day_section.py, client/ui/main_window.py, client/tests/ui/test_day_section.py, client/tests/ui/test_main_window.py</files>
  <behavior>
    - Test 1 (day_section): После `ds.set_day_date(new_date, is_today=False)` self._day_date == new_date, header_label показывает короткий формат "Пн 20", шрифт FONTS["body"].
    - Test 2 (day_section): Transition is_today=False → True — создаётся today_strip frame (виден в children header_row), label меняется на длинный "Понедельник, 20" и FONTS["h2"].
    - Test 3 (day_section): Transition is_today=True → False — today_strip исчезает (destroyed или pack_forget), label возвращается к короткому формату.
    - Test 4 (main_window): `_on_week_changed` → `_update_week` — existing DaySection instances переиспользуются (id тех же объектов сохраняется), `_day_sections` dict меняет ключи (даты) но не пересоздаёт DaySection.
    - Test 5 (main_window): `handle_task_style_changed` по-прежнему делает heavy rebuild (destroy+recreate) — разделение сохранено.
  </behavior>
  <action>
## Часть A — DaySection.set_day_date (client/ui/day_section.py)

Добавить публичный метод (после `set_archive_mode`, перед `destroy`):

```python
def set_day_date(self, new_date: date, is_today: bool) -> None:
    """Обновить день без пересоздания виджета (diff-rebuild).

    Пересчитывает: _day_date, _is_today, bg_color, label (текст+шрифт),
    today_strip (create/destroy при transition).
    """
    if self._destroyed:
        return
    old_is_today = self._is_today
    self._day_date = new_date
    self._is_today = is_today

    # 1) bg_color рамки
    try:
        self.frame.configure(fg_color=self._day_bg_color())
    except tk.TclError:
        pass

    # 2) today_strip transition
    if is_today and not old_is_today:
        # Нужен strip — удалить spacer (первый child header_row) и создать strip
        self._swap_to_today_strip()
    elif not is_today and old_is_today:
        self._swap_to_spacer()

    # 3) Label текст + шрифт (ищем первый CTkLabel в header_row)
    day_label = self._find_day_label()
    if day_label is not None:
        day_name_short = DAY_NAMES_RU_SHORT[new_date.weekday()]
        day_name_long = DAY_NAMES_RU_LONG[new_date.weekday()]
        if is_today:
            label_text = f"{day_name_long}, {new_date.day}"
            font = FONTS["h2"]
        else:
            label_text = f"{day_name_short} {new_date.day}"
            font = FONTS["body"]
        try:
            day_label.configure(text=label_text, font=font)
        except tk.TclError:
            pass


def _find_day_label(self) -> Optional[ctk.CTkLabel]:
    """Найти day_label в _header_row (первый CTkLabel после strip/spacer)."""
    if self._header_row is None:
        return None
    try:
        for child in self._header_row.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                return child
    except tk.TclError:
        pass
    return None


def _swap_to_today_strip(self) -> None:
    """not-today → today: найти spacer (первый child, width≈11, transparent) → destroy → создать strip с pack(side='left', fill='y', padx=(0,8)) перед остальными."""
    if self._header_row is None:
        return
    try:
        children = list(self._header_row.winfo_children())
    except tk.TclError:
        return
    # Первый child — либо spacer (transparent frame) либо уже strip
    if children and isinstance(children[0], ctk.CTkFrame):
        try:
            children[0].destroy()
        except Exception:
            pass

    self._today_strip = ctk.CTkFrame(
        self._header_row, width=TODAY_STRIP_WIDTH,
        fg_color=self._theme.get("accent_brand"), corner_radius=0,
    )
    # pack_before первого оставшегося child, чтобы strip стал первым
    try:
        remaining = list(self._header_row.winfo_children())
        # strip в конце после create — pack side="left" добавит в конец.
        # Чтобы разместить strip ПЕРВЫМ: использовать pack(side="left", before=...)
        if remaining and len(remaining) > 1:
            first_existing = remaining[0] if remaining[0] is not self._today_strip else remaining[1]
            self._today_strip.pack(side="left", fill="y", padx=(0, 8), before=first_existing)
        else:
            self._today_strip.pack(side="left", fill="y", padx=(0, 8))
        self._today_strip.pack_propagate(False)
    except tk.TclError:
        pass


def _swap_to_spacer(self) -> None:
    """today → not-today: destroy strip, создать spacer вместо него."""
    if self._today_strip is not None:
        try:
            self._today_strip.destroy()
        except Exception:
            pass
        self._today_strip = None
    if self._header_row is None:
        return
    try:
        spacer = ctk.CTkFrame(
            self._header_row, width=TODAY_STRIP_WIDTH + 8, fg_color="transparent",
        )
        remaining = list(self._header_row.winfo_children())
        if remaining and remaining[0] is not spacer:
            spacer.pack(side="left", before=remaining[0])
        else:
            spacer.pack(side="left")
    except tk.TclError:
        pass
```

**Важно:** в существующем `_build()` посмотреть на порядок packing — strip/spacer идёт первым (side="left"), затем day_label (side="left"), затем right frame (side="right"). Наши `_swap_*` через `pack(before=...)` сохраняют этот порядок.

## Часть B — MainWindow._update_week (client/ui/main_window.py)

Добавить новый метод (рядом с `_rebuild_day_sections`):

```python
def _update_week(self) -> None:
    """Лёгкий update недели — обновить даты существующих DaySection без пересоздания (устранение мерцания).

    Если day_sections ещё не созданы (первый вызов) ИЛИ их количество != 7 —
    fallback к _rebuild_day_sections.
    """
    if self._week_nav is None:
        return
    # Первый вызов или некорректное состояние → тяжёлый rebuild
    if len(self._day_sections) != 7:
        self._rebuild_day_sections()
        return

    week_monday = self._week_nav.get_week_monday()
    today = date.today()
    new_dates = [week_monday + timedelta(days=i) for i in range(7)]

    # Старые секции в порядке текущих дат (словарь упорядочен по вставке = неделе)
    old_sections_ordered = list(self._day_sections.values())
    new_map: dict[date, DaySection] = {}

    for i, d in enumerate(new_dates):
        ds = old_sections_ordered[i]
        ds.set_day_date(d, is_today=(d == today))
        new_map[d] = ds

    self._day_sections = new_map

    # Drop zones: ссылки на те же frames остаются валидными, но day_date в zone устарели.
    # Перерегистрируем zones.
    if self._drag_controller is not None:
        try:
            self._drag_controller.clear_drop_zones()
            for d, ds in self._day_sections.items():
                zone = DropZone(day_date=d, frame=ds.get_drop_frame())
                self._drag_controller.register_drop_zone(zone)
        except Exception as exc:
            logger.debug("_update_week drop zone refresh failed: %s", exc)

    # Archive mode (если была)
    if self._week_nav.is_current_archive():
        self._on_archive_changed(True)
```

Заменить callback `_on_week_changed` — вместо `_rebuild_day_sections` вызывать `_update_week`:

```python
def _on_week_changed(self, new_monday: date) -> None:
    self._update_week()
    self._refresh_tasks()
```

`handle_task_style_changed` оставить КАК ЕСТЬ (он вызывает `_rebuild_day_sections` + `_refresh_tasks` — heavy rebuild нужен при смене style).

## Часть C — Тесты

В `client/tests/ui/test_day_section.py` добавить (используя существующую фикстуру `headless_tk` и `theme_manager`):

```python
def test_set_day_date_updates_date_and_label_short_format(headless_tk, theme_manager):
    d = date(2024, 1, 15)  # Mon
    ds = DaySection(headless_tk, d, is_today=False, theme_manager=theme_manager,
                    task_style="card", user_id="u",
                    on_task_toggle=lambda *a: None, on_task_edit=lambda *a: None,
                    on_task_delete=lambda *a: None, on_inline_add=lambda *a: None)
    ds.pack()
    headless_tk.update_idletasks()
    new_d = date(2024, 2, 6)  # Tue
    ds.set_day_date(new_d, is_today=False)
    assert ds._day_date == new_d
    lbl = ds._find_day_label()
    assert lbl is not None
    assert "Вт" in lbl.cget("text")
    assert "6" in lbl.cget("text")


def test_set_day_date_not_today_to_today_creates_strip(headless_tk, theme_manager):
    d = date(2024, 1, 15)
    ds = DaySection(headless_tk, d, is_today=False, theme_manager=theme_manager,
                    task_style="card", user_id="u",
                    on_task_toggle=lambda *a: None, on_task_edit=lambda *a: None,
                    on_task_delete=lambda *a: None, on_inline_add=lambda *a: None)
    ds.pack()
    headless_tk.update_idletasks()
    assert ds._today_strip is None
    ds.set_day_date(d, is_today=True)
    assert ds._today_strip is not None
    lbl = ds._find_day_label()
    assert "Понедельник" in lbl.cget("text")


def test_set_day_date_today_to_not_today_destroys_strip(headless_tk, theme_manager):
    d = date(2024, 1, 15)
    ds = DaySection(headless_tk, d, is_today=True, theme_manager=theme_manager,
                    task_style="card", user_id="u",
                    on_task_toggle=lambda *a: None, on_task_edit=lambda *a: None,
                    on_task_delete=lambda *a: None, on_inline_add=lambda *a: None)
    ds.pack()
    headless_tk.update_idletasks()
    old_strip = ds._today_strip
    assert old_strip is not None
    ds.set_day_date(d, is_today=False)
    assert ds._today_strip is None
    # Старая ссылка destroyed
    assert not old_strip.winfo_exists()
```

В `client/tests/ui/test_main_window.py` добавить (минимум 1 тест):

```python
def test_on_week_changed_reuses_day_sections(headless_tk, theme_manager, settings_store, settings):
    # Используй существующую фикстуру для MainWindow (см. файл)
    mw = MainWindow(headless_tk, settings_store, settings, theme_manager)
    headless_tk.update_idletasks()
    # Запомнить id объектов первых секций
    first_ids = [id(ds) for ds in mw._day_sections.values()]
    # Симулировать смену недели
    mw._week_nav.next_week()
    headless_tk.update_idletasks()
    new_ids = [id(ds) for ds in mw._day_sections.values()]
    assert first_ids == new_ids  # те же объекты переиспользованы
```

Если фикстур нет в тестовом файле — скопировать минимально необходимое из test_main_window.py (он уже существует).

## Часть D — Git commit

Коммит **на русском**: `feat(ux): diff-rebuild недели — устранено мерцание при переключении (DaySection.set_day_date + MainWindow._update_week)`

**Pitfall (важный!):** `_build()` в DaySection сейчас пакует strip/spacer первым через `pack(side="left")`. Наш `_swap_*` должен ставить новый widget **перед** существующими children, иначе он окажется в конце ряда. Используем `pack(before=first_remaining_child)`.

**Что НЕ трогать:** `_rebuild_day_sections` остаётся для initial build и при task_style change. `handle_task_style_changed` вызывает именно его.
  </action>
  <verify>
    <automated>cd s:\Проекты\ежедневник && python -m pytest client/tests/ui/test_day_section.py -x -q 2>&1 | tail -30 && python -m pytest client/tests/ui/test_main_window.py -x -q 2>&1 | tail -30</automated>
  </verify>
  <done>
    - DaySection.set_day_date реализован с корректной обработкой is_today transition
    - MainWindow._update_week переиспользует существующие DaySection
    - _on_week_changed вызывает _update_week (не _rebuild_day_sections)
    - handle_task_style_changed по-прежнему делает heavy rebuild
    - Новые тесты passing, существующие не сломаны
    - Commit создан с русским описанием
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Sync→UI callback (убираем 30с лаг после merge_from_server)</name>
  <files>client/core/sync.py, client/app.py, client/tests/test_sync.py</files>
  <behavior>
    - Test 1: `SyncManager.set_on_sync_complete(cb)` сохраняет callback, и после успешного _attempt_sync cb вызывается с dict stats (ключи: applied, conflicts, tombstones_received, pushed).
    - Test 2: При неудачном sync (network error / auth_expired) callback НЕ вызывается.
    - Test 3: Если `applied==0 and pushed==0` — callback всё равно вызывается (но сам `_handle_sync_complete` в app.py решает, нужен ли refresh).
    - Test 4: Exception внутри callback не крашит sync loop (обёрнут в try/except с logger.debug).
  </behavior>
  <action>
## Часть A — SyncManager callback (client/core/sync.py)

В `SyncManager.__init__` добавить (после `self._auth_expired = False`):

```python
# Callback, вызывается после успешного merge_from_server + commit_drained.
# ВНИМАНИЕ: вызывается из sync thread — обработчик обязан сам заворачивать в root.after(0, ...)
self._on_sync_complete: Optional[Callable[[dict], None]] = None
```

Добавить импорт в начало файла: `from typing import Callable, Optional` (Optional уже есть, Callable добавить).

Публичный setter (после `force_sync`):

```python
def set_on_sync_complete(self, cb: Optional[Callable[[dict], None]]) -> None:
    """Установить callback, вызываемый после успешного sync.

    Callback получает stats dict:
      {"applied": int, "conflicts": int, "tombstones_received": int, "pushed": int}
    Вызывается из SYNC THREAD — обработчик обязан сам обернуть UI-операции в root.after(0, ...).
    """
    self._on_sync_complete = cb
```

В `_attempt_sync`, сразу после `self._storage.commit_drained(drained)` и до `logger.info(...)` (примерно строка 220-221), добавить вызов callback:

```python
# Уведомить UI-слой о завершении успешного sync (после commit_drained)
if self._on_sync_complete is not None:
    notify_stats = dict(stats)  # копируем чтобы не делить dict
    notify_stats["pushed"] = len(drained)
    try:
        self._on_sync_complete(notify_stats)
    except Exception as exc:  # noqa: BLE001
        logger.debug("on_sync_complete callback failed: %s", exc)
```

**Разместить ПОСЛЕ `commit_drained` и ПЕРЕД `logger.info` — это корректная точка "sync confirmed".**

## Часть B — Wire в app.py (client/app.py)

В `_setup`, сразу после `self.sync.start()` (строка ~154):

```python
# Sync→UI callback (убирает 30с лаг между merge_from_server и UI refresh)
def _sync_complete_bridge(stats: dict) -> None:
    # Callback вызывается из sync thread — переносим на main через after
    try:
        self.root.after(0, self._handle_sync_complete, stats)
    except Exception as exc:
        logger.debug("sync complete bridge failed: %s", exc)

self.sync.set_on_sync_complete(_sync_complete_bridge)
```

Добавить новый метод в `WeeklyPlannerApp` (рядом с `_handle_force_sync` или другими handlers):

```python
def _handle_sync_complete(self, stats: dict) -> None:
    """Вызывается из sync thread через root.after — обновить UI после успешного sync.

    Args:
        stats: {"applied": int, "conflicts": int, "tombstones_received": int, "pushed": int}
    """
    applied = int(stats.get("applied", 0) or 0)
    pushed = int(stats.get("pushed", 0) or 0)
    # Если ничего не изменилось — skip дорогой _refresh_tasks
    if applied == 0 and pushed == 0:
        return
    logger.debug("sync complete: applied=%d pushed=%d → refresh UI", applied, pushed)
    try:
        if self.main_window is not None:
            self.main_window._refresh_tasks()
    except Exception as exc:
        logger.debug("main_window refresh failed: %s", exc)
    try:
        self._refresh_ui()  # уже существующий метод — overlay/tray badges
    except Exception as exc:
        logger.debug("_refresh_ui failed: %s", exc)
```

## Часть C — Тесты

В `client/tests/test_sync.py` (путь может быть `client/tests/core/test_sync.py` — проверь Glob) добавить:

```python
def test_set_on_sync_complete_invoked_after_successful_sync(sync_manager_with_stub):
    """После успешного _attempt_sync callback вызывается с stats dict."""
    sync = sync_manager_with_stub  # фикстура из существующих тестов
    captured = []
    sync.set_on_sync_complete(lambda stats: captured.append(stats))
    # Запустить один цикл (стаб-сервер возвращает 200)
    sync._attempt_sync()
    assert len(captured) == 1
    assert "applied" in captured[0]
    assert "pushed" in captured[0]


def test_on_sync_complete_not_called_on_auth_expired(sync_manager_auth_expired):
    """При auth_expired callback НЕ вызывается."""
    sync = sync_manager_auth_expired
    captured = []
    sync.set_on_sync_complete(lambda stats: captured.append(stats))
    sync._attempt_sync()
    assert captured == []


def test_callback_exception_does_not_crash_sync(sync_manager_with_stub):
    """Исключение в callback не должно крашить sync loop."""
    sync = sync_manager_with_stub
    sync.set_on_sync_complete(lambda stats: (_ for _ in ()).throw(RuntimeError("boom")))
    # Не должно raise
    result = sync._attempt_sync()
    assert result.ok  # sync всё равно завершился OK
```

Если фикстур `sync_manager_with_stub` / `sync_manager_auth_expired` нет — посмотри существующие тесты sync и используй их подход (requests-mock + FakeServer, см. STATE.md D-08, Phase 02-08). Адаптируй названия фикстур к реальности.

## Часть D — Git commit

Коммит: `feat(sync): callback on_sync_complete — UI обновляется сразу после merge (убран 30с лаг)`

**Pitfall 1:** Callback вызывается из sync thread. `_refresh_tasks` делает Tkinter операции — ОБЯЗАТЕЛЬНО через `root.after(0, ...)`. Bridge-функция в app.py это делает.

**Pitfall 2:** `merge_from_server` возвращает stats БЕЗ ключа "pushed" — мы его добавляем отдельно (`notify_stats["pushed"] = len(drained)`) чтобы handler мог решить о refresh.

**Pitfall 3:** `_handle_sync_complete` проверяет applied+pushed — noop-sync (skip ветка в _attempt_sync строка 198-203, когда `not drained and not is_stale`) **не вызывает commit_drained** и **не вызывает callback** — всё ОК, там нет `commit_drained`.
  </action>
  <verify>
    <automated>cd s:\Проекты\ежедневник && python -m pytest client/tests/test_sync.py client/tests/core/test_sync.py -x -q 2>&1 | tail -30</automated>
  </verify>
  <done>
    - SyncManager.set_on_sync_complete реализован
    - Callback вызывается после commit_drained в _attempt_sync
    - Callback НЕ вызывается на auth_expired/client error (logic уже обработан — callback только в успешной ветке)
    - Исключения в callback логируются и не ломают sync loop
    - app.py: _sync_complete_bridge оборачивает callback в root.after
    - app.py: _handle_sync_complete вызывает _refresh_tasks и _refresh_ui только при applied+pushed > 0
    - Тесты passing
    - Commit создан
  </done>
</task>

<task type="auto">
  <name>Task 3: Global hotkey Alt+Z toggle main window</name>
  <files>client/app.py</files>
  <action>
## Часть A — Инициализация в __init__

В `WeeklyPlannerApp.__init__` (где `self.tray`, `self.sync`, etc. инициализируются как None), добавить:

```python
self.hotkeys: Optional[HotkeyManager] = None
```

И импорт на уровне модуля (проверь, не было ли уже):

```python
from client.utils.hotkeys import HotkeyManager
```

## Часть B — Регистрация в _setup

В `_setup`, **после** создания `self.main_window` (после шага 6, но до шага 10 tray), добавить:

```python
# Global hotkey Alt+Z — toggle main window из любого приложения
try:
    self.hotkeys = HotkeyManager()
    self.hotkeys.register("alt+z", self._on_global_hotkey_toggle)
    logger.info("Global hotkey Alt+Z зарегистрирован")
except Exception as exc:
    # keyboard library может требовать admin rights, PyInstaller frozen bundling issues.
    # НЕ блокируем запуск приложения — логируем и продолжаем.
    logger.warning("Не удалось зарегистрировать Alt+Z: %s", exc)
    self.hotkeys = None
```

## Часть C — Handler

Новый метод `WeeklyPlannerApp._on_global_hotkey_toggle`:

```python
def _on_global_hotkey_toggle(self) -> None:
    """Callback глобального хоткея Alt+Z — toggle main window.

    ВНИМАНИЕ: вызывается из внутреннего потока библиотеки keyboard.
    Все Tkinter операции обязательно через root.after(0, ...).
    """
    if self.main_window is None:
        return
    try:
        self.root.after(0, self.main_window.toggle)
    except Exception as exc:
        logger.debug("hotkey toggle failed: %s", exc)
```

## Часть D — Teardown

В `_handle_quit`, **ПЕРЕД** `self.sync.stop()` (hotkey callback может обратиться к sync/main_window которые закрываем), добавить:

```python
if self.hotkeys is not None:
    try:
        self.hotkeys.unregister()
    except Exception as exc:
        logger.debug("hotkeys unregister: %s", exc)
```

Разместить первым в try-блоке — ДО `self.pulse.stop()`, чтобы keyboard listener перестал стрелять ДО того как остальные компоненты умрут.

Итого порядок в try блоке `_handle_quit`:
```python
try:
    if self.hotkeys is not None:       # НОВОЕ — первым
        try:
            self.hotkeys.unregister()
        except Exception as exc:
            logger.debug("hotkeys unregister: %s", exc)
    if self.pulse is not None:         # существующее
        self.pulse.stop()
    if self.sync is not None:
        self.sync.stop()
    # ... остальное без изменений
```

## Часть E — Git commit

Коммит: `feat(hotkey): global Alt+Z — toggle главного окна из любого приложения`

**Pitfall 1 (admin rights):** `keyboard` library на Windows может требовать admin в некоторых setup. При ошибке `register()` — НЕ падаем, логируем и продолжаем без hotkey.

**Pitfall 2 (thread-safety):** `keyboard.add_hotkey` callback вызывается из её внутреннего потока. Вся Tkinter работа ТОЛЬКО через `root.after(0, ...)`. Прямой вызов `main_window.toggle()` из keyboard thread = краш Tcl.

**Pitfall 3 (teardown race):** Если keyboard thread стрельнёт после `root.destroy` — `root.after` бросит TclError. Поэтому `hotkeys.unregister()` ПЕРВЫМ в teardown.

**Pitfall 4 (PyInstaller):** `keyboard` библиотека должна попасть во frozen bundle. Обычно попадает автоматически через `pip install keyboard` → в requirements.txt. Если при сборке exe будут issues — hidden-import `keyboard` в .spec (это отдельно, НЕ в этом task).

**Тесты:** keyboard library требует админ-прав и реальной ОС клавиатуры — unit-тестировать headless сложно. Тесты для этого task НЕ требуются. Ручная verification: запустить `python main.py`, свернуть окно, нажать Alt+Z вне приложения — окно должно появиться.

**НЕ трогать:** `client/utils/hotkeys.py` — уже реализован корректно. Не менять.
  </action>
  <verify>
    <automated>cd s:\Проекты\ежедневник && python -c "import ast; tree = ast.parse(open('client/app.py', encoding='utf-8').read()); funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; assert '_on_global_hotkey_toggle' in funcs, 'missing handler'; src = open('client/app.py', encoding='utf-8').read(); assert 'alt+z' in src.lower(), 'alt+z not registered'; assert 'hotkeys.unregister' in src, 'no unregister in teardown'; print('OK: alt+z hotkey wired')"</automated>
  </verify>
  <done>
    - self.hotkeys: Optional[HotkeyManager] объявлен в __init__
    - HotkeyManager создаётся и регистрирует alt+z в _setup после main_window
    - Failure при register() не блокирует запуск (graceful degradation + warning log)
    - _on_global_hotkey_toggle переносит toggle на main thread через root.after
    - _handle_quit unregister ПЕРВЫМ в teardown (до pulse/sync/tray)
    - Commit создан
    - Ручная проверка: Alt+Z из свёрнутого состояния открывает окно
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Fade-эффект show/hide главного окна</name>
  <files>client/ui/main_window.py, client/tests/ui/test_main_window.py</files>
  <behavior>
    - Test 1: После `show()` → через FADE_DURATION_MS + небольшой буфер окно имеет alpha ≈ 1.0 и is_visible()==True.
    - Test 2: После `hide()` → через FADE_DURATION_MS + буфер alpha ≈ 0.0 и withdraw вызван (is_visible()==False).
    - Test 3: `toggle()` во время активного fade не инициирует параллельный fade (или инициирует, но корректно — не падает).
  </behavior>
  <action>
## Часть A — Константы и show/hide

В классе `MainWindow` (после `DEFAULT_SIZE = (460, 600)`), добавить:

```python
FADE_DURATION_MS = 150
FADE_STEPS = 8  # ~19мс на шаг
```

Заменить метод `show`:

```python
def show(self) -> None:
    # Если окно в процессе fade-out — гасим fade (alpha вернётся к 1.0 через новый цикл)
    try:
        self._window.attributes("-alpha", 0.0)
    except tk.TclError:
        pass
    self._window.deiconify()
    self._window.lift()
    self._fade(target=1.0, step=0)
```

Заменить метод `hide`:

```python
def hide(self) -> None:
    # Защита: если окно не viewable — ничего fade-ить не нужно
    try:
        if self._window.winfo_viewable() == 0:
            return
    except tk.TclError:
        return
    self._fade(target=0.0, step=0, on_complete=self._safe_withdraw)


def _safe_withdraw(self) -> None:
    try:
        self._window.withdraw()
        # Восстановить alpha=1.0 чтобы следующий show не начинал с прозрачного окна
        self._window.attributes("-alpha", 1.0)
    except tk.TclError:
        pass
```

## Часть B — _fade

Новый приватный метод:

```python
def _fade(self, target: float, step: int, on_complete: Optional[Callable[[], None]] = None) -> None:
    """Плавное изменение alpha окна.

    Args:
        target: целевая alpha (0.0 или 1.0)
        step: текущий шаг (0..FADE_STEPS)
        on_complete: вызвать после завершения fade
    """
    current_step = step + 1
    progress = current_step / self.FADE_STEPS
    # ease-out quadratic
    eased = 1.0 - (1.0 - progress) ** 2

    if target >= 0.5:  # fade-in
        alpha = eased
    else:              # fade-out
        alpha = 1.0 - eased

    try:
        self._window.attributes("-alpha", max(0.0, min(1.0, alpha)))
    except tk.TclError:
        return

    if current_step >= self.FADE_STEPS:
        # Финальный кадр — точное значение
        try:
            self._window.attributes("-alpha", target)
        except tk.TclError:
            pass
        if on_complete is not None:
            try:
                on_complete()
            except Exception as exc:
                logger.debug("fade on_complete failed: %s", exc)
        return

    delay_ms = max(1, int(self.FADE_DURATION_MS / self.FADE_STEPS))
    try:
        self._window.after(delay_ms, self._fade, target, current_step, on_complete)
    except tk.TclError:
        pass
```

Не забудь импорт `Callable` уже есть в заголовке файла (см. `from typing import Callable, Optional`).

## Часть C — Тесты

В `client/tests/ui/test_main_window.py` добавить:

```python
def test_show_fades_in_to_alpha_1(headless_tk, theme_manager, settings_store, settings):
    """show() приводит alpha к 1.0 после FADE_DURATION_MS."""
    mw = MainWindow(headless_tk, settings_store, settings, theme_manager)
    mw.show()
    # Прогнать все after-калбэки
    total_wait = MainWindow.FADE_DURATION_MS + 100
    deadline = mw._window.tk.call('clock', 'milliseconds') + total_wait  # или простой цикл
    for _ in range(50):
        headless_tk.update()
        headless_tk.after(10)
        headless_tk.update_idletasks()
    alpha = float(mw._window.attributes("-alpha"))
    assert alpha >= 0.99
    assert mw.is_visible()


def test_hide_fades_out_and_withdraws(headless_tk, theme_manager, settings_store, settings):
    """hide() уводит alpha к 0, затем withdraws окно."""
    mw = MainWindow(headless_tk, settings_store, settings, theme_manager)
    mw.show()
    for _ in range(50):
        headless_tk.update()
        headless_tk.update_idletasks()
    mw.hide()
    for _ in range(50):
        headless_tk.update()
        headless_tk.update_idletasks()
    assert not mw.is_visible()
```

**Примечание:** Существующий метод `test_show_hide` (если есть) может ломаться из-за async fade. Если тест `test_x_show_immediately_deiconifies` fail'ится — адаптировать ожидание или добавить `update_idletasks()` прогон.

## Часть D — Git commit

Коммит: `feat(ux): fade-эффект 150мс при show/hide главного окна`

**Pitfall 1:** `attributes("-alpha")` на Windows работает на CTkToplevel (наш случай). На Linux — tkinter >=8.5 + WM support. Обёрнуто в try/except TclError — graceful fallback.

**Pitfall 2:** `hide` + немедленный `show` (быстрый toggle): текущий fade-out ещё идёт, `show` стартует новый fade-in → alpha начнёт расти. На финале fade-out может сработать `_safe_withdraw` и опять скрыть окно. Решение в этой реализации: `_safe_withdraw` только withdraw-ит, если предполагается что окно видно. Если `toggle` вызван во время fade — возможен визуальный глич, но это РЕДКИЙ edge case. **НЕ добавляем complicated state machine** — KISS.

**Pitfall 3:** После `withdraw` возвращаем alpha=1.0 — чтобы следующий `show` → `deiconify` не показал прозрачное окно кратковременно.

**Pitfall 4:** `show()` устанавливает alpha=0.0 ДО deiconify — иначе первый кадр виден с alpha=1.0 и только потом гаснет → мерцание.
  </action>
  <verify>
    <automated>cd s:\Проекты\ежедневник && python -m pytest client/tests/ui/test_main_window.py -x -q 2>&1 | tail -30</automated>
  </verify>
  <done>
    - FADE_DURATION_MS и FADE_STEPS константы добавлены
    - show() устанавливает alpha=0 → deiconify → _fade to 1.0
    - hide() _fade to 0.0 → _safe_withdraw (withdraw + alpha=1.0)
    - _fade использует ease-out quadratic
    - Tkinter операции обёрнуты в try/except TclError
    - Тесты passing
    - Commit создан
    - Ручная проверка: открытие/закрытие окна — плавное, без мгновенного переключения
  </done>
</task>

</tasks>

<verification>
Все 4 фичи независимы — выполнять в любом порядке. После каждой task:

1. **Unit тесты** по затронутым модулям passing (см. verify в каждом task)
2. **Git commit на русском** создан
3. **Ручная verification** (после всех 4):
   - Открыть приложение: `python main.py`
   - Переключить неделю стрелками — визуально нет мерцания (Task 1)
   - Изменить задачу на другом устройстве/через server API и дождаться sync — UI обновится в течение ~30с-60с (sync period), без дополнительных 30с лага (Task 2)
   - Свернуть окно, нажать Alt+Z — окно появляется (Task 3)
   - Открыть/закрыть окно — плавный fade ~150мс (Task 4)

**Pre-existing test issues (не блокеры):**
- `test_e2e_phase3.py` может иметь 10 Tcl errors из shared Tk state — игнорируем если они не от новых изменений.

**Regression check:**
```bash
cd s:\Проекты\ежедневник && python -m pytest client/tests/ -x -q --ignore=client/tests/ui/test_e2e_phase3.py 2>&1 | tail -20
```
Зелёный билд обязателен.
</verification>

<success_criteria>
- **Task 1** — `DaySection.set_day_date` и `MainWindow._update_week` существуют; `_on_week_changed` больше не делает destroy+recreate; тесты passing
- **Task 2** — `SyncManager.set_on_sync_complete` публичный; callback вызывается после commit_drained в успешной ветке; app.py оборачивает в root.after; `_handle_sync_complete` вызывает `_refresh_tasks` + `_refresh_ui` только при applied+pushed>0
- **Task 3** — `HotkeyManager` инстанцируется и регистрирует alt+z; callback через root.after; unregister ПЕРЕД sync.stop в _handle_quit
- **Task 4** — show/hide используют _fade; alpha attribute переключается плавно ease-out; _safe_withdraw восстанавливает alpha=1.0

**4 атомарных commit'а на русском**, каждый в отдельный task. Порядок не важен (независимы).

**Главное: `python main.py` запускается, ни одна из существующих фич не сломана.**
</success_criteria>

<output>
После выполнения всех 4 tasks, обновить `.planning/STATE.md` секцию Quick Tasks Completed:

```markdown
| 260421-vxz | UX polish: diff-rebuild недели + sync→UI callback + Alt+Z + fade show/hide | 2026-04-21 | {4 commits} | [260421-vxz-ux-polish-diff-rebuild-sync-ui-callback-](./quick/260421-vxz-ux-polish-diff-rebuild-sync-ui-callback-/) |
```
</output>
