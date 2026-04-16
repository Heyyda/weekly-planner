# Phase 3: Оверлей и системная интеграция — Context

**Gathered:** 2026-04-16
**Status:** Ready for planning
**Mode:** Conversational design discussion — all visual decisions in UI-SPEC.md

<domain>
## Phase Boundary

Визуальный каркас клиента: **квадрат-оверлей на рабочем столе** (replaces изначальный "кружок"), **главное окно с аккордеоном дней**, **system tray-иконка**, **toast-уведомления**. Phase 3 строит **UI shell** — контейнеры, темизацию, навигацию между неделями. **Содержимое задач — добавление/редактирование/удаление/drag-and-drop — Phase 4**.

Покрывает REQ-IDs: OVR-01..06, TRAY-01..04, NOTIF-01..04 (всего 14).

</domain>

<decisions>
## Implementation Decisions

### Visual design (все детали в UI-SPEC.md)
- **D-01:** Квадрат вместо кружка — отсылка к Things 3. Синий градиент `#4EA1FF → #1E73E8`, 56×56, rounded 12px, белая галочка / плюс / badge в углу.
- **D-02:** Overdue signal — **весь квадрат пульсирует** (blue→red→blue, 2.5s loop). Не точка, не change-galочку.
- **D-03:** Badge с числом задач сегодня в правом-верхнем углу квадрата.
- **D-04:** Empty state — белый "+" вместо галочки.
- **D-05:** Tray-иконка = тот же квадрат (упрощённый для 16px).
- **D-06:** Окно — **аккордеон по дням**, сегодня раскрыт по умолчанию.
- **D-07:** Today-indicator: **синяя вертикальная полоска слева + bold заголовок** (оба одновременно).
- **D-08:** Окно **ресайзабельное**, размер+позиция персистят.
- **D-09:** Три темы: светлая (кремовая), тёмная (warm dark), бежевая (sepia) — палитра Claude Code. Плюс опция "системная".
- **D-10:** Синий акцент — только для CTA/focus/квадрата. Красный — overdue/destructive. Зелёный — done checkmark. Остальное — тёплые бежевые/коричневые тона.
- **D-11:** Task-block — **3 стиля на выбор в настройках** (карточки / строки / минимализм). Переключение мгновенное.
- **D-12:** Tray-меню структура: Открыть → Добавить → Настройки(вложено 5 toggles) → Sync → Logout → Выход.
- **D-13:** Toast-режимы: звук+pulse / только pulse / тихо (не беспокоить).

### Library choices (Claude discretion based on research)
- **D-14:** CustomTkinter 5.2.2 (pinned per STACK research) — основной GUI framework.
- **D-15:** pystray (`run_detached()` + `root.after(0, ...)` callbacks — PITFALL 2).
- **D-16:** Overlay через `overrideredirect(True)` + `after(100, ...)` delay (PITFALL 1 Win11 DWM).
- **D-17:** Toast — `winotify` (active maintenance) вместо `win10toast` (stagnant).
- **D-18:** Icon composition через Pillow в памяти (квадрат+галочка+badge) → передача в pystray.Icon и overlay canvas.
- **D-19:** Multi-monitor: ctypes `EnumDisplayMonitors` + `GetSystemMetrics` для positioning.
- **D-20:** Global hotkey для вызова окна — **отложен в v2** (PROJECT.md out-of-scope UXI-01). В Phase 3 только клик по квадрату + tray-меню.
- **D-21:** Font — `Segoe UI Variable` (Windows 11 native с кириллицей) + `Cascadia Code` mono.

### Integration with Phase 2 (client core)
- **D-22:** Overlay и окно читают `LocalStorage.get_visible_tasks()` (Phase 2 API) — не дублируют state.
- **D-23:** Tray "Обновить синхронизацию" вызывает `SyncManager.force_sync()` (Phase 2 API).
- **D-24:** Overlay полагается на `SyncManager.sync_status` (running / stale / offline) для визуального индикатора (если будет добавлено — в Phase 3 пока нет).
- **D-25:** Настройки (тема, task-style, notifications mode, on-top, autostart) сохраняются в `settings.json` через Phase 2 `LocalStorage.settings` (или отдельный SettingsStore — planner решит).

### Thread safety (critical per PITFALLS)
- **D-26:** `pystray.Icon.run_detached()` — НЕ `run()`. Иначе Tk-apartment race crash.
- **D-27:** Все tray-callbacks проходят через `root.after(0, fn)` — никогда не трогать Tk виджеты из pystray-потока напрямую.
- **D-28:** Overdue pulse animation — через `root.after()` цикл, не `threading.Timer`.
- **D-29:** Авто-обновление (через SyncManager в фоне) — когда приходят изменения, UI обновляется через `root.after(0, refresh_overlay)` чтобы избежать cross-thread Tk calls.

### Autostart (TRAY-toggle)
- **D-30:** Автозапуск Windows — через реестр `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Запись/удаление — через `winreg`, значение — путь к `.exe` (в Phase 6 — это будет frozen PyInstaller executable; в dev — `python.exe main.py`).

### Claude's Discretion
- Конкретная структура файлов `client/ui/` (`overlay.py`, `main_window.py`, `day_section.py`, `task_widget.py`, `tray_icon.py`, `notifications.py`, `themes.py`)
- Точные значения anim-timings (UI-SPEC даёт общие величины, planner уточняет фреймы)
- Способ реализации pulse: `after()` loop vs canvas blending vs frame sequence (Pillow pre-rendered)
- Реализация "empty state dim opacity" для "не беспокоить" режима
- Структура unit/integration тестов (mock-Tk vs headless display)
- Конкретная pydantic/dataclass схема для `settings.json` (theme, task_style, notifications_mode, on_top, autostart, overlay_position, window_size)

### Folded Todos
(cross_reference_todos вернул 0)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Visual design contract (MANDATORY)
- `.planning/phases/03-overlay-system/03-UI-SPEC.md` — полный дизайн-контракт (overlay, окно, tray, палитра, anim, success criteria)

### Project vision & constraints
- `.planning/PROJECT.md` — Core Value, Design-risk mitigation (UI-phase через `/gsd:ui-phase`)
- `.planning/REQUIREMENTS.md` §OVR §TRAY §NOTIF — 14 требований
- `.planning/ROADMAP.md` §Phase 3 — goal, research flags (overrideredirect Win11 delay, pystray threading)
- `CLAUDE.md` — Russian comments/commits, minimal/elegant UI

### Research — architectural patterns + pitfalls
- `.planning/research/STACK.md` §CustomTkinter (pin 5.2.2), §winotify vs win10toast
- `.planning/research/PITFALLS.md` — **ALL applicable pitfalls in this phase:**
  - Pitfall 1: `overrideredirect(True)` + Win11 DWM delay
  - Pitfall 2: pystray + Tk requires `run_detached()` + `after(0, ...)`
  - Pitfall 3: CustomTkinter `--onefile` bundling (Phase 6 concern, awareness here)
  - Pitfall 5: Global hotkey silently fails without elevation (out of scope v1, but awareness)

### Phase 2 integration (API surfaces to import from)
- `client/core/__init__.py` — exported classes (LocalStorage, SyncManager, AuthManager, Task, TaskChange)
- `client/core/storage.py` §get_visible_tasks(), §update_task(), §settings accessor
- `client/core/sync.py` §force_sync(), §status property (if exists, else add)
- `client/core/models.py` §Task schema (id, text, day, time_deadline, done, position)
- `client/core/logging_setup.py` — переиспользовать для UI-логов

### Codebase existing skeleton (REWRITE or extend)
- `client/ui/sidebar.py` — old skeleton (replaced by new `overlay.py`)
- `client/ui/week_view.py`, `day_panel.py`, `task_widget.py`, `notes_panel.py`, `stats_panel.py`, `settings_panel.py`, `themes.py` — skeletons, будут переписаны под новый UI-SPEC
- `client/utils/tray.py`, `hotkeys.py`, `notifications.py`, `autostart.py` — skeletons для рефа
- `client/app.py` — главный класс `WeeklyPlannerApp`, точка интеграции

### Reference products (inspiration)
- Things 3 (iOS/Mac) — квадрат-иконка + минималистичные карточки. Скриншоты в гугле достаточны как визуальный референс.
- Claude Code — тёплая кремовая палитра, которую повторяем для тем.
- Linear — "воздушный" минималистичный task-block (Style C).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (из Phase 2)
- `client.core.LocalStorage` — источник задач, settings accessor (через `settings.json`)
- `client.core.SyncManager.force_sync()` — триггер ручного sync
- `client.core.AuthManager.logout()` — для tray "Разлогиниться"
- `client.core.models.Task` — полная схема для отображения

### Skeleton to rewrite (из оригинального `client/ui/` и `client/utils/`)
Публичные сигнатуры в скелетах — ориентир. Тела заменить. Пример:
- `ThemeManager` (was `themes.py`) → расширить 3-мя темами + бежевой
- `SidebarManager` → переименовать в `OverlayManager` (квадрат вместо sidebar-а)

### Integration Points
- `main.py` → `WeeklyPlannerApp(version).run()` — последовательность:
  1. AuthManager `load_saved_token()` → если нет refresh → показать login dialog (Phase 3 out of scope, показать placeholder "Нужна авторизация")
  2. Создать LocalStorage + SyncManager + запустить sync thread
  3. Создать MainWindow (hidden) + OverlayManager (visible) + TrayIcon
  4. Настроить обработчики сигналов между компонентами (click overlay → show window)
  5. Запустить Tk mainloop

### Platform constraints
- Windows 10/11 only — win32gui / ctypes DWM APIs требуются
- HiDPI — CustomTkinter сам не скейлит overlay через `overrideredirect`; нужно ctypes `SetProcessDpiAwareness` + ручной scale в Pillow composition
- Multi-monitor — обязательно тестировать (Никита имеет 2 экрана на работе)

</code_context>

<specifics>
## Specific Ideas

- **Things 3 visual language** — закруглённые квадраты, синий accent, chunky checkmarks. Но цвета окон — Claude Code warm cream.
- **Claude Code warmth** — бежево-коричневая палитра вдохновлена именно Anthropic CLI tool. "Бумажное" ощущение.
- **"Не раздражающее"** — главный критерий. Минимализм не самоцель, но перегруз = провал. Задача не "показать все функции", а "не мешать работе".
- **Three task styles** — необычное решение, но user value: разные люди предпочитают разную плотность. Implementation cost невысокий (CSS-like токены, 3 renderer функции).
- **Quarter-second animations** — не slow (200-250ms), чувствуется отзывчиво, но не резко.

</specifics>

<deferred>
## Deferred Ideas

- **Drag-and-drop задач** — Phase 4 (требует tasks CRUD сначала)
- **Inline add-task input** — Phase 4 (design есть в UI-SPEC, но код в Phase 4)
- **Редактирование текста задачи** — Phase 4
- **Global hotkey (Win+Q)** — v2 (elevation issues, PROJECT.md out-of-scope UXI-01)
- **Sync status visual indicator** (спиннер/tick в overlay когда syncs) — добавить в v2 если нужно
- **Mini-preview в overlay при hover** (список задач на сегодня) — idea for v2
- **Keyboard shortcuts внутри окна** (J/K navigation, space=done) — v2, Phase 4 если время будет
- **Window transparency settings** — v2
- **Multi-workspace/virtual-desktops Windows** — потенциальный PITFALL для always-on-top, изучим на практике

### Reviewed Todos (not folded)
(cross_reference_todos вернул 0)

</deferred>

---

*Phase: 03-overlay-system*
*Context gathered: 2026-04-16 — conversational, UI-SPEC пишется параллельно*
*Approved by owner for planning.*
