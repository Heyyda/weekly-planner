---
phase: 03-overlay-system
plan: 05
subsystem: ui
tags: [customtkinter, animation, pulse, tkinter, after-loop, 60fps]

# Dependency graph
requires:
  - phase: 03-overlay-system/03-03
    provides: render_overlay_image(pulse_t) — icon_compose.py с pulse_t параметром
provides:
  - "PulseAnimator class (client/ui/pulse.py) — 60fps after-loop driver для overdue-анимации"
  - "PULSE_INTERVAL_MS=16 (60fps), PULSE_CYCLE_MS=2500 (2.5s per UI-SPEC)"
  - "start()/stop() idempotent lifecycle management"
  - "on_frame(pulse_t: float) callback interface для OverlayManager (Plan 03-10)"
affects: [03-overlay-system/03-10, client/ui/overlay.py]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "root.after() self-scheduling loop для 60fps анимации (D-28 / PITFALL 2 compliant)"
    - "Monotonic time через time.monotonic() для точного elapsed-ms tracking"
    - "Triangle-wave pulse_t: 0.0=blue → 0.5=red → 1.0=blue (wrap через % PULSE_CYCLE_MS)"
    - "Idempotent start/stop с after_cancel guard"

key-files:
  created:
    - client/ui/pulse.py
    - client/tests/ui/test_pulse.py
  modified:
    - client/tests/conftest.py

key-decisions:
  - "headless_tk fixture scope=session (fix: Tcl нельзя пересоздать в одной pytest-сессии)"
  - "PulseAnimator отдельный модуль от OverlayManager (SRP — единственная ответственность = анимация)"
  - "Module docstring упоминает 'threading.Timer запрещён' а не в теле класса — чтобы inspect.getsource(PulseAnimator) не ломал тест"

patterns-established:
  - "Pattern: PulseAnimator(root, on_frame=cb) → cb(pulse_t) каждые 16ms при active"
  - "Pattern: stop() всегда вызывает on_frame(0.0) для reset без flicker"

requirements-completed: [OVR-05]

# Metrics
duration: 5min
completed: 2026-04-16
---

# Phase 3 Plan 05: PulseAnimator Summary

**60fps overlay pulse-driver через root.after(16) self-scheduling loop — 2.5s blue→red→blue цикл для overdue-сигнала (OVR-05)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-16T07:00:02Z
- **Completed:** 2026-04-16T07:04:36Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- `PulseAnimator` класс с PULSE_INTERVAL_MS=16 и PULSE_CYCLE_MS=2500 — покрывает OVR-05
- root.after() self-scheduling loop — D-28 / PITFALL 2 соблюдён (threading.Timer absent)
- start()/stop() idempotent: guard против двойного after-цикла и flicker-free stop через on_frame(0.0)
- 14/14 unit-тестов зелёных включая PITFALL 2 guard-test (inspect.getsource проверяет threading.Timer absent)
- Исправлен баг в headless_tk fixture (scope=session) — Tcl нельзя пересоздать после destroy()

## Task Commits

1. **Task 1 RED: failing tests** — `120d71d` (test)
2. **Task 1 GREEN: PulseAnimator + conftest fix** — `c5fa0f3` (feat)

## Files Created/Modified

- `client/ui/pulse.py` — PulseAnimator: 60fps after-loop driver, ~125 строк
- `client/tests/ui/test_pulse.py` — 14 unit-тестов, covers OVR-05
- `client/tests/conftest.py` — headless_tk scope=function → scope=session (bugfix)

## Decisions Made

- `headless_tk` изменён на `scope="session"` — Tcl/Tk interpreter не может быть пересоздан внутри одной pytest-сессии после `root.destroy()`. Session scope означает один CTk root на всю сессию, что является стандартным паттерном для Tkinter unit-тестов.
- Комментарий `threading.Timer запрещён` оставлен в module docstring (вне тела класса) — `inspect.getsource(PulseAnimator)` не включает module docstring, поэтому тест-guard работает корректно.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] headless_tk fixture scope=function вызывает TclError при повторной инициализации**

- **Found during:** Task 1 GREEN (запуск тестов)
- **Issue:** `headless_tk` с function scope создаёт новый CTk() для каждого теста. После destroy() Tcl интерпретатор частично деинициализируется, и следующий CTk() падает с `TclError: Can't find a usable tk.tcl`. При работе совместно с asyncio плагином pytest поведение стало нестабильным.
- **Fix:** `@pytest.fixture(scope="session")` — один CTk root на всю pytest-сессию. Teardown происходит один раз в конце.
- **Files modified:** client/tests/conftest.py
- **Verification:** `pytest client/tests/ui/test_pulse.py` — 14 passed. `pytest client/tests/ui/` — 67 passed (нет регрессий в overlay, settings, themes тестах).
- **Committed in:** c5fa0f3 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug)
**Impact on plan:** Исправление инфраструктуры тестов. Нет изменений в бизнес-логике. Все 67 UI тестов проходят после изменения.

## Issues Encountered

- Первоначальная версия pulse.py имела `threading.Timer запрещён` в теле docstring класса — тест `test_uses_root_after_not_threading_timer` падал потому что `inspect.getsource(PulseAnimator)` включает class docstring. Исправлено переносом фразы в module-level docstring.

## Next Phase Readiness

- PulseAnimator готов к интеграции в Plan 03-10 (OverlayManager wiring):
  ```python
  pulse = PulseAnimator(root, on_frame=lambda t: overlay.refresh_image(
      state="overdue", task_count=n, overdue_count=k, pulse_t=t))
  # overdue → pulse.start(), cleared → pulse.stop()
  ```
- conftest.py headless_tk теперь session-scoped — это корректная база для всех будущих UI тестов Phase 3

---
*Phase: 03-overlay-system*
*Completed: 2026-04-16*
