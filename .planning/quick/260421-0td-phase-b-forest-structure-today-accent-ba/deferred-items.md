# Deferred Items — Phase B Forest (260421-0td)

Issues discovered during execution, out of scope for this plan (boundary:
 only `day_section.py`, `task_widget.py` + their test files).

## Pre-existing failures (NOT caused by Phase B changes)

Подтверждено: стащил рабочие изменения (`git stash`) и перезапустил те же тесты —
они падали до Phase B в той же конфигурации. Не в scope.

### 1. `client/tests/ui/test_notifications.py::test_check_deadlines_approaching_zero_delta`

- **Симптом:** `AssertionError: assert 'overdue' == 'approaching'` — тест ожидает
  что задача с дедлайном ровно сейчас будет классифицирована как `approaching`,
  но классификатор возвращает `overdue`.
- **Причина (предположительно):** граница approaching/overdue в классификаторе
  исключает `delta == 0` (задача «ровно сейчас» считается уже просроченной).
- **Defer-reason:** не пересекается с day_section/task_widget scope, отдельный
  тикет на semantics notifications.

### 2. `client/tests/ui/test_e2e_phase3.py::*` (10 errors, не failures)

- **Симптом:** все тесты собираются в ERROR, не в FAILURE — проблема до запуска
  теста (setup). Сообщение из tail: `_tk...` (отрезано), предположительно
  `_tkinter.TclError` из-за проблем с session-scoped `headless_tk` после того
  как предыдущие тесты destroy его children.
- **Причина (предположительно):** headless_tk scope=session + e2e tests пересоздают
  корневые виджеты — interaction issue, не регрессия.
- **Defer-reason:** не пересекается с Phase B scope. Отдельная задача на изоляцию
  e2e fixture.

## Status

- Phase B scope тесты: **52/52 green** (`test_day_section.py` + `test_task_widget.py`).
- Phase 4 e2e scope тесты: **16/16 green** (`test_e2e_phase4.py`).
- Никакие из вышеперечисленных deferred items НЕ связаны с изменениями Phase B
  (verified via git stash).
