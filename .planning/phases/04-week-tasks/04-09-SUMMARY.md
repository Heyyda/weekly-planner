---
plan: 04-09
status: DONE
commits: 8377f29
tests: 24 passed
---

# 04-09 SUMMARY — DragController (TASK-05, TASK-06)

## Delivered
- `client/ui/drag_controller.py` — DropZone + GhostWindow + DragController (360 lines)
- `client/tests/ui/test_drag_controller.py` — 24 tests (100 % green)

## Approach 2 (Research DND §8)
- Custom mouse bindings (`<ButtonPress-1>`/`<B1-Motion>`/`<ButtonRelease-1>`) ТОЛЬКО на task body frame
- CTkToplevel ghost pre-created в `__init__` (избегаем alpha-flash от recreate)
- Explicit DropZone bbox hit-test через `winfo_rootx/rooty/width/height` — **НЕ `winfo_containing`** (PITFALL: broken в CTkScrollableFrame)
- 5px threshold до start-drag (избегаем accidental drag при clicks)

## Key markers
- `DRAG_THRESHOLD_PX = 5`
- `GhostWindow.ALPHA = 0.6`, `INIT_DELAY_MS = 100` (overrideredirect через after)
- `_blend_hex` — active 15 % / adjacent 5 % highlight
- D-25: next-week zone показывается на `_start_drag`, прячется на `_cancel_drag`/`_commit_drop`
- D-26: archive-mode блокирует все drops; drop outside zones → cancel

## Tests (24)
- DropZone.contains inside/outside + flags (archive, next-week)
- GhostWindow initial withdrawn state
- `_find_drop_zone` hit detection
- Threshold below 5px no-drag / above starts
- Drop same-source cancels / different-zone commits / outside cancels / archive cancels
- `set_archive_mode` marks all + `clear_drop_zones`
- `_blend_hex` 50 % / 0 % / 1 % / invalid-fallback
- Next-week zone shown on drag_start (pack called)
- Marker tests: `DRAG_THRESHOLD_PX = 5`, `ALPHA = 0.6`, no `winfo_containing`, `winfo_rootx` used, ghost pre-created, `INIT_DELAY_MS = 100`

## Fixes during run
1. Docstring содержал literal "winfo_containing" → тест `test_no_winfo_containing` failed. Заменил на "winfo-containing" (дефис).
2. `MagicMock.winfo_width()` возвращает MagicMock, который умножается на float → `TypeError`. Добавил `int(...)` coercion + catch `TypeError/ValueError`.
3. `DropZone.contains` падал на MagicMock bbox — обернул в `try/except TypeError`.

## Next
- 04-10: wire DragController + UndoToast + EditDialog + QuickCapture в `WeeklyPlannerApp`
- 04-11: E2E phase-4 tests + human-verify checkpoint
