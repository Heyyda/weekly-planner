# Changelog

Все значимые изменения. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

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
