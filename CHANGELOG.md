# Changelog

Все значимые изменения. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [0.5.0] — 2026-04-21

Полный визуальный рефакторинг — **Forest theme**. 11 фаз (A → K).

### Тема Forest
- **Палитра**: льняной cream (`#EEE9DC`) + бутылочный зелёный (`#1E5239`) + терракотовый clay (`#9E6A5A`) для деструктивных действий
- Dark-вариант с зелёно-оливковым подтоном (`#161E1A`), не нейтральный серый — характер «настольная лампа с зелёным абажуром»
- Темы `forest_light` и `forest_dark` доступны в tray-меню наряду со старыми (light/dark/beige)

### Окно
- **Frameless**: убрана Windows title bar, свой 28px header с forest-стрипом, названием и ✕
- **Скруглённые углы 12px** через GDI SetWindowRgn (Win10 совместимость)
- **Нативная тень DWM** под frameless окном (Win10/11)
- **Fade-in 180ms** на открытии — окно плавно проявляется, больше нет «сборки из частей»
- **Fade-out 120ms** на закрытии
- **Плавный переход недель**: alpha 1.0→0.55→rebuild→1.0 (230ms) при ◀/▶/«Сегодня»

### Виджеты
- **Today-секция** — фон `bg_tertiary` (forest-tint) + 3px forest-стрип слева
- Обычные дни — прозрачный фон, 1px разделители между ними
- **Inline-edit** (новый `TaskEditCard`) — редактирование задачи прямо в списке вместо модалки
  - Pills для выбора дня («Сегодня/Завтра» + 7 дней недели)
  - Компактный HH:MM + ✕ сброс
  - Три кнопки: 🗑 Удалить (clay) / Отмена / Сохранить (forest)
  - Esc = отмена, Ctrl+Enter = сохранить
- **Overlay** — flat cream плашка 56×56, forest-галочка, forest-бейдж (clay при просрочках)
- Все кнопки, полосы, диалоги перекрашены (убраны старые синий/зелёный/красный)
- **Overstrike** на выполненных задачах (зачёркивание текста)
- **Archive-режим** визуально dim'ит палитру

### Анимации
- **ColorTween** helper (~60fps, ease-out) для плавных hover-переходов на иконках, стрелках, кнопках, +
- Все hover-переходы 150ms ease-out вместо мгновенного «снапа»

### Типографика
- `init_fonts(root)` резолвит Segoe UI Variable → Segoe UI → Arial (универсальный fallback)
- Mono для времени: Cascadia Mono → Cascadia Code → Consolas → Courier New
- На Win10 всё корректно падает на Consolas вместо uglify default

### Тесты
- +150 новых тестов
- 579/579 passed в scope Forest
- WCAG AA contrast verified для всех критических пар в dark mode

---

## [0.4.0] — 2026-04-19

### Фиксы
- **DnD между днями** работает мышкой (CTkLabel блокировал события → recursive bind на children)
- **Overdue alerts** срабатывают для сегодняшних задач с истёкшим временем (раньше только для прошлых дней)
- **EditDialog** открывается поверх главного окна (transient + topmost-flash), больше не "в новой вкладке за основным меню"
- **Notifications** парсер времени понимает и `HH:MM`, и ISO datetime
- **Sync `time_deadline` → HTTP 422** — `to_wire()` конвертирует `"14:00"` в ISO datetime с server-совместимым форматом

### UX
- **Шрифты**: Segoe UI Variable + Cascadia Mono, свежая h1/h2/body/caption шкала
- **Скругления** r=10 везде (было 6-8)
- **DaySection compact**: пустой день ~34px (было 60+), плюс в правом-верхнем углу header
- **TaskWidget**: checkbox 22×22 со smooth-галочкой, иконки ✎/🗑 всегда видны (dim до hover)
- **EditDialog**: компактный 420×320, time picker через два dropdown'а (HH / MM), больше не ручной ввод с двоеточием
- **Overlay**: 3× supersampling для плавных краёв (больше не пикселизовано)
- **Tray icon**: 64×64 — корректный размер на HiDPI ноутбуках (v0.3.x был 32, уменьшался до 1/4)

---

## [0.3.1] — 2026-04-19

- **UpdateBanner** — всплывающий баннер в правом-верхнем углу при доступной новой версии
- **Auto-install**: скачивание → SHA256 verify → bat-trick замены → авторестарт
- `/api/version` на сервере читает манифест `/opt/planner/releases/latest.json` — обновление без рестарта API

---

## [0.3.0] — 2026-04-19

Первая end-to-end версия.

- **LoginDialog** встроенный (до 0.3.0 нужен был `python login.py` через CLI)
- **Phase 4** code-complete: недельный вид, quick-capture, DnD, edit, undo, 3 стиля, архив
- **Phase 5** code-complete: Telegram-бот `/add`, `/today`, `/week` + inline-кнопки
- **Phase 6** code-complete: PyInstaller .exe, GitHub release pipeline
- Publishing: репозиторий публичный, asset через GitHub Releases
- `/api/version` для проверки обновлений

---

Deploy endpoints:
- **API**: https://planner.heyda.ru
- **Bot**: [@Jazzways_bot](https://t.me/Jazzways_bot)
