---
phase: quick-260421-vxz
plan: 01
subsystem: client/ui + client/core
tags: [ux, polish, diff-rebuild, sync, hotkey, fade, animation]
requirements:
  - UX-01
  - UX-02
  - UX-03
  - UX-04
dependency_graph:
  requires:
    - client/ui/day_section.py:DaySection
    - client/ui/main_window.py:MainWindow
    - client/core/sync.py:SyncManager
    - client/utils/hotkeys.py:HotkeyManager
  provides:
    - "DaySection.set_day_date(new_date, is_today) — diff-update без пересоздания"
    - "MainWindow._update_week() — lightweight обновление недели"
    - "SyncManager.set_on_sync_complete(callback) — UI hook после успешного sync"
    - "MainWindow._fade / _safe_withdraw — fade show/hide"
    - "WeeklyPlannerApp.hotkeys: Optional[HotkeyManager] — global Alt+Z"
  affects:
    - "_on_week_changed теперь вызывает _update_week (было _rebuild_day_sections)"
    - "Sync thread вызывает UI callback после merge_from_server + commit_drained"
    - "show/hide главного окна анимированы (150мс fade)"
tech_stack:
  added: []
  patterns:
    - "Diff-rebuild: переиспользование виджетов с мутацией состояния вместо destroy+recreate"
    - "Thread-safe UI callback: sync thread → root.after(0, handler) → main thread"
    - "Graceful degradation: keyboard library может падать (admin rights / frozen exe) → логируем и продолжаем"
    - "Fade animation через attributes('-alpha') + after() chain с ease-out quadratic"
key_files:
  created: []
  modified:
    - client/ui/day_section.py
    - client/ui/main_window.py
    - client/core/sync.py
    - client/app.py
    - client/tests/ui/test_day_section.py
    - client/tests/ui/test_main_window.py
    - client/tests/test_sync.py
decisions:
  - "UX-01: set_day_date использует pack(before=...) для сохранения порядка strip/spacer → label → right — pack(side='left') без before добавил бы strip в конец"
  - "UX-01: handle_task_style_changed сохраняет heavy _rebuild_day_sections — при смене стиля карточек нужно пересоздание TaskWidget внутри DaySection"
  - "UX-02: stats dict обогащён ключом 'pushed' (не приходит из merge_from_server) — позволяет _handle_sync_complete skip refresh при noop (applied=0 pushed=0)"
  - "UX-02: callback обёрнут в try/except в sync thread — исключение в UI bridge не должно ломать sync loop"
  - "UX-03: HotkeyManager регистрируется после main_window (секция 8.5) — до этого не на что переключаться; unregister первым в _handle_quit до sync.stop/pulse.stop"
  - "UX-03: failure keyboard.add_hotkey() → warning + hotkeys=None — приложение работает без хоткея, не крашится"
  - "UX-04: FADE_STEPS=8 при FADE_DURATION_MS=150 → ~19мс на шаг — гладко для человеческого глаза, не нагружает CPU"
  - "UX-04: alpha=0 устанавливается ДО deiconify — иначе первый кадр виден непрозрачным (мерцание обратное)"
  - "UX-04: _safe_withdraw восстанавливает alpha=1.0 — следующий show начинает чисто"
metrics:
  duration: ~35min
  tasks_completed: 4
  files_changed: 7
  commits: 4
completed_date: 2026-04-21
---

# Quick Task 260421-vxz: UX Polish — Diff-Rebuild / Sync→UI Callback / Alt+Z / Fade Summary

**One-liner:** 4 независимые UX-правки устраняют мерцание недели (diff-rebuild DaySection), 30-секундный лаг sync→UI (callback), отсутствие глобального хоткея (Alt+Z) и грубое мгновенное show/hide (150мс fade).

## Задачи (4, выполнены последовательно)

### Task 1 — Diff-rebuild недели (UX-01)

**Проблема:** Переключение недели стрелками вызывало destroy+recreate всех 7 DaySection → заметное визуальное мерцание (flash).

**Решение:**
- Добавлен публичный метод `DaySection.set_day_date(new_date, is_today)` — обновляет дату/фон/strip/label без пересоздания виджета.
- Добавлены helpers: `_find_day_label`, `_swap_to_today_strip`, `_swap_to_spacer` — корректно обрабатывают transition `is_today` True↔False через `pack(before=...)` для сохранения порядка children в header_row.
- В `MainWindow._update_week()` — lightweight обновление 7 существующих DaySection через `set_day_date`. Drop zones перерегистрируются на новые даты.
- `_on_week_changed` теперь вызывает `_update_week` вместо `_rebuild_day_sections`.
- `handle_task_style_changed` сохраняет heavy rebuild — при смене стиля нужен пересоздаваемый TaskWidget.

**Файлы:** `client/ui/day_section.py` (+125 строк), `client/ui/main_window.py` (+47 строк).

**Тесты (5):**
- `test_set_day_date_updates_date_and_label_short_format` — проверка базового обновления даты.
- `test_set_day_date_not_today_to_today_creates_strip` — transition not-today → today.
- `test_set_day_date_today_to_not_today_destroys_strip` — обратный transition.
- `test_on_week_changed_reuses_day_sections` — `id()` DaySection стабильны после next_week().
- `test_handle_task_style_changed_rebuilds_heavy` — при смене стиля `id()` меняются.

**Commit:** `485bee6`.

### Task 2 — Sync→UI callback (UX-02)

**Проблема:** После `merge_from_server` UI ждал до 30с (`_scheduled_refresh`) чтобы отобразить новые задачи — лаг между реальным sync и визуальным результатом.

**Решение:**
- `SyncManager.set_on_sync_complete(cb)` — публичный setter. Callback сохраняется в `self._on_sync_complete`.
- В `_attempt_sync` после `commit_drained(drained)` и до `logger.info(...)` — вызов callback со stats dict (applied/conflicts/tombstones_received/pushed).
- Exception в callback обёрнут в `try/except` с `logger.debug` — sync loop не ломается.
- Callback НЕ вызывается на auth_expired / 5xx (только в успешной ветке).
- В `client/app.py` после `self.sync.start()`:
  - `_sync_complete_bridge(stats)` — обёртка из sync thread на main через `root.after(0, ...)`.
  - `_handle_sync_complete(stats)` — skip refresh при `applied==0 and pushed==0` (noop), иначе `main_window._refresh_tasks()` + `_refresh_ui()`.

**Файлы:** `client/core/sync.py` (+28 строк), `client/app.py` (+38 строк).

**Тесты (4):**
- `test_set_on_sync_complete_invoked_after_successful_sync` — callback вызывается с правильным stats dict.
- `test_on_sync_complete_not_called_on_auth_expired` — skip при 401/refresh fail.
- `test_on_sync_complete_not_called_on_server_error` — skip при 5xx.
- `test_on_sync_complete_exception_does_not_crash_sync` — sync loop стабилен при bad callback.

**Commit:** `e98152d`.

### Task 3 — Global hotkey Alt+Z (UX-03)

**Проблема:** `HotkeyManager` уже реализован (`client/utils/hotkeys.py`), но не подключён к приложению — горячая клавиша Alt+Z не работала.

**Решение:**
- `self.hotkeys: Optional[HotkeyManager] = None` в `WeeklyPlannerApp.__init__`.
- В `_setup` (секция 8.5, после `self.pulse = PulseAnimator(...)`):
  ```python
  try:
      self.hotkeys = HotkeyManager()
      self.hotkeys.register("alt+z", self._on_global_hotkey_toggle)
  except Exception as exc:
      logger.warning("Не удалось зарегистрировать Alt+Z: %s", exc)
      self.hotkeys = None
  ```
- `_on_global_hotkey_toggle()` — переносит `main_window.toggle` на main thread через `root.after(0, ...)` (keyboard callback вызывается из своего thread → прямой Tkinter вызов = TclError crash).
- В `_handle_quit`: `hotkeys.unregister()` **первым** в try-блоке — listener должен замолчать до того, как остальные компоненты умрут. Иначе последний hotkey callback может обратиться к уничтоженному main_window.

**Файлы:** `client/app.py` (+36 строк).

**Тесты:** Не добавлены — `keyboard` library требует ОС и админ-прав, headless тестирование нецелесообразно. AST-проверка (запуск вручную) подтверждает наличие `_on_global_hotkey_toggle`, регистрацию `alt+z` и `hotkeys.unregister` в teardown.

**Commit:** `b18da5e`.

### Task 4 — Fade show/hide (UX-04)

**Проблема:** Мгновенные `deiconify()` / `withdraw()` при показе/скрытии главного окна выглядели грубо — без анимации.

**Решение:**
- Константы класса: `FADE_DURATION_MS = 150`, `FADE_STEPS = 8` (~19мс на кадр).
- `show()`: устанавливает `alpha=0.0` **до** `deiconify` (иначе первый кадр виден непрозрачным → обратное мерцание) → `deiconify()` → `lift()` → `_fade(target=1.0)`.
- `hide()`: `winfo_viewable()` guard → `_fade(target=0.0, on_complete=_safe_withdraw)`.
- `_safe_withdraw`: `withdraw()` + восстановить `alpha=1.0` для следующего show.
- `_fade(target, step, on_complete)` — рекурсивный `after()` chain с ease-out quadratic (`1 - (1-t)²`). Финальный шаг выставляет точный `target` (защита от floating-point погрешности).
- Все Tkinter операции обёрнуты в `try/except tk.TclError` — graceful на Linux без WM-support для alpha.

**Файлы:** `client/ui/main_window.py` (+88 строк).

**Тесты (3 новых + обновлены 2 существующих):**
- `test_show_fades_in_to_alpha_1` — alpha ≥ 0.99 после прогона fade.
- `test_hide_fades_out_and_withdraws` — `is_visible()==False` после fade-out, alpha восстановлена к 1.0.
- `test_fade_constants_present` — FADE_DURATION_MS и FADE_STEPS определены.
- `_drain_fade(root, duration_ms)` — хелпер прогона after-колбэков (250мс default).
- `test_show_makes_visible` и `test_toggle_alternates` — обновлены на `_drain_fade` вместо одиночного `update()` (fade async, одного update не хватает).

**Commit:** `444d70e`.

## Verification

**Тесты (все зелёные):**
- `client/tests/ui/test_day_section.py` — 31 тест (3 новых)
- `client/tests/ui/test_main_window.py` — 28 тестов (5 новых)
- `client/tests/test_sync.py` — 24 теста (4 новых)
- Полная регрессия (`client/tests/` без `test_e2e_phase3.py`/`test_e2e_phase4.py`) — **473 passed**.

**Импорты:**
```bash
python -c "from client.app import WeeklyPlannerApp; from client.ui.main_window import MainWindow; from client.core.sync import SyncManager; print('Imports OK')"
# → Imports OK
```

**AST-проверка app.py:**
- `_on_global_hotkey_toggle` существует
- `_handle_sync_complete` существует
- `alt+z` зарегистрирован в source
- `hotkeys.unregister` в teardown

## Known Issues (не блокеры, pre-existing)

**`client/tests/ui/test_e2e_phase3.py` / `test_e2e_phase4.py`:**
- `test_overlay_click_toggles_main_window` — FAIL (shared Tk state + real OS window manager).
- `test_overdue_task_triggers_pulse` — ERROR (зависит от предыдущего).
- **Проверено:** эти тесты падали ДО наших изменений (`git stash` + запуск = та же картина).
- STATE.md уже документирует эти e2e issues как не-блокеры. Наши правки их не затронули.

**Ручная UAT (TODO):**
- Переключить неделю стрелками — визуально нет мерцания (UX-01).
- Изменить задачу на другом устройстве → дождаться sync → UI обновится без 30с лага (UX-02).
- Свернуть окно, нажать Alt+Z из другого приложения — окно появляется (UX-03).
- Открыть/закрыть окно — плавный fade ~150мс (UX-04).

## Deviations from Plan

None — все 4 задачи выполнены по плану. Добавлен только `_drain_fade()` хелпер в тест-файл — необходимость стала очевидна после первого прогона (существующие `test_show_makes_visible` / `test_toggle_alternates` ломались из-за async fade через `after()`). Это естественное продолжение задачи, не отклонение.

## Commits (4, на русском)

1. `485bee6` — feat(ux): diff-rebuild недели — устранено мерцание при переключении
2. `e98152d` — feat(sync): callback on_sync_complete — UI обновляется сразу после merge
3. `b18da5e` — feat(hotkey): global Alt+Z — toggle главного окна из любого приложения
4. `444d70e` — feat(ux): fade-эффект 150мс при show/hide главного окна

## Self-Check: PASSED

- FOUND: `client/ui/day_section.py` — метод `set_day_date` (line ~130)
- FOUND: `client/ui/main_window.py` — метод `_update_week` + константы FADE_DURATION_MS/FADE_STEPS
- FOUND: `client/core/sync.py` — метод `set_on_sync_complete` + вызов callback после commit_drained
- FOUND: `client/app.py` — `self.hotkeys`, `_on_global_hotkey_toggle`, `_handle_sync_complete`, `hotkeys.unregister` в _handle_quit
- FOUND: commit `485bee6` в `git log --oneline`
- FOUND: commit `e98152d` в `git log --oneline`
- FOUND: commit `b18da5e` в `git log --oneline`
- FOUND: commit `444d70e` в `git log --oneline`
- VERIFIED: 473 тестов прошли (без e2e)
- VERIFIED: Импорты `WeeklyPlannerApp`, `MainWindow`, `SyncManager` работают без ошибок
