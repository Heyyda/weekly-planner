---
phase: quick-260421-vk4
plan: 01
subsystem: client/ui
tags: [dnd, drag-drop, bugfix, ui]
requirements:
  - DND-FIX-01
dependency_graph:
  requires:
    - client/ui/day_section.py:DaySection (self.frame)
    - client/ui/drag_controller.py:DropZone
  provides:
    - "DaySection.get_drop_frame() → self.frame (вся карточка дня)"
  affects:
    - "DropZone bbox для пустых дней становится ненулевым"
    - "Подсветка hover-зоны теперь покрывает весь день (включая header)"
tech_stack:
  added: []
  patterns:
    - "Frame selection pattern: разделить 'контейнер для контента' (body_frame) и 'зона hit-тестирования' (drop_frame)"
key_files:
  created: []
  modified:
    - client/ui/day_section.py
    - client/ui/main_window.py
decisions:
  - "DropZone регистрируется на self.frame (корень секции), не на _body_frame — гарантирует ненулевой bbox всегда"
metrics:
  duration: ~2min
  tasks_completed: 1
  files_changed: 2
  lines_changed: 11
completed_date: 2026-04-21
---

# Quick Fix 260421-vk4: DnD на пустой день — DropZone на self.frame Summary

One-liner: Перенёс регистрацию DropZone с `_body_frame` (который `pack_forget()`-ится при пустом дне) на корневой `self.frame` — DnD теперь работает на все 7 дней, включая пустые.

## Что изменено

**2 файла, 3 правки, 11 строк:**

1. `client/ui/day_section.py` — добавлен публичный метод `get_drop_frame() -> ctk.CTkFrame` (возвращает `self.frame`). Документирует причину: `_body_frame` может быть скрыт при пустом дне.
2. `client/ui/main_window.py` — в `_rebuild_day_sections()` регистрация `DropZone(day_date=d, frame=ds.get_drop_frame())` вместо `ds.get_body_frame()`. Строка 279.
3. `client/ui/main_window.py` — строка `widget.get_body_frame()` (TaskWidget для привязки draggable) НЕ тронута — она не относится к регистрации зоны.

## Root Cause

`DaySection._update_body_visibility` вызывает `pack_forget()` на `_body_frame`, когда день пустой и нет inline-add. В распакованном состоянии Tkinter-фрейм не размещён в geometry manager:
- `winfo_x/y` возвращают 0
- `winfo_width/height` возвращают 1 (default размер до `pack`)

`DropZone.get_bbox()` возвращал почти нулевой прямоугольник. В `drag_controller.py:43`:
```python
if x2 <= x1 or y2 <= y1:
    return False
```
→ `contains()` всегда False → drop на пустой день не регистрировался.

**Фикс:** Использовать `self.frame` (корень секции, который упаковывается через `ds.pack(fill="x", pady=4)` в `main_window._rebuild_day_sections`). Этот фрейм упакован ВСЕГДА (пока DaySection жив), содержит `_header_row` высотой 34px → bbox всегда ненулевой.

## Verification

Автоматические проверки (все пройдены):
1. `ast.parse` + поиск `get_drop_frame` в методах класса `DaySection` → OK
2. `ds.get_drop_frame()` присутствует в `main_window.py`, старое `frame=ds.get_body_frame()` отсутствует в регистрации DropZone → OK
3. `import client.ui.day_section, client.ui.main_window` → OK (нет синтаксических ошибок)
4. `widget.get_body_frame()` (TaskWidget) сохранён → OK

Ручная UAT не выполнена (требует GUI на Windows). Код-ревью подтверждает контракт: `self.frame` упаковывается родителем в `_rebuild_day_sections:275` через `ds.pack(fill="x", pady=4)`.

## Known Issues / Follow-up

**Регрессия подсветки "сегодня" после drag (косметика, не функциональность):**

`drag_controller._set_zone_highlight(zone, "normal")` (строка ~341) делает:
```python
zone.frame.configure(fg_color=bg_primary)
```

Теперь `zone.frame = ds.frame`. У секции `is_today=True` метод `_day_bg_color()` возвращает `bg_secondary` — после завершения drag сегодняшняя секция потеряет свой акцентный фон до следующего re-theme (например, при переключении недели или темы).

**Предлагаемый фикс (отдельная задача):**
- Хранить исходный `fg_color` в `DropZone.original_bg` при `register_drop_zone()` через `zone.frame.cget("fg_color")`
- В `_set_zone_highlight(zone, "normal")` восстанавливать `zone.original_bg` вместо жёсткого `bg_primary`

Это затрагивает только визуал секции "сегодня" после drag — функциональность DnD не страдает. Приоритет: низкий, исправляется при ближайшей правке `drag_controller`.

## Deviations from Plan

None — план выполнен точно как написан. 2 файла, 3 правки, 1 новый метод + 1 строка замены.

## Commits

- `076cc69` — fix(dnd): перенос задачи на пустой день — DropZone на self.frame

## Self-Check: PASSED

- FOUND: `client/ui/day_section.py` содержит метод `get_drop_frame` (line 113, возвращает `self.frame`)
- FOUND: `client/ui/main_window.py` строка 279: `zone = DropZone(day_date=d, frame=ds.get_drop_frame())`
- FOUND: `widget.get_body_frame()` (TaskWidget) сохранён на строке 314
- FOUND: commit `076cc69` в `git log`
- Automated verifications (3/3) passed
