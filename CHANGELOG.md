# Changelog

Все значимые изменения. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [0.7.0] — 2026-04-22

### Новое
- **Повторяющиеся задачи** — toggle «Повторять каждую неделю» в inline-edit панели. При отметке задачи как выполненной она автоматически клонируется на +7 дней. Иконка 🔁 рядом с текстом задачи.
- **Cross-week DnD** — при перетаскивании задачи появляются sage-pill зоны «◀ Предыдущая неделя» и «Следующая неделя ▶». Brop на них переносит задачу ±7 дней и плавно переключает неделю.
- **Redesign QuickCapturePopup** (правый клик на overlay) — accent-полоска слева, подсказка «Enter — сохранить, Esc — отмена», умное позиционирование с clamp к границам экрана (не вылазит за край).
- **Sage accent_brand** во всех палитрах — единый sage-зелёный бренд (кнопки, dropdowns, today-strip, update banner) вместо старого синего.
- **Time picker** — показывает `— / —` плейсхолдер когда время не задано (вместо dim `09:00`); при выборе переключается на яркий текст.
- **Window size persistence** — размер окна сохраняется при любом способе закрытия (debounced на resize + at hide/close).
- **Inline edit panel polish** — кнопки Save/День/ЧЧ/ММ теперь явно sage, soft border, top-отступ 20px для визуального простора.

### Фиксы
- Удалён чекбокс «Выполнено» из inline-edit (дублировал чекбокс слева задачи) — заменён на «Повторять каждую неделю».

### Откачено
- Custom title-bar и hide-from-taskbar временно отключены (DWM clash на Win11 давал Windows popup «параметр задан неправильно»). Native Windows рамка вернулась. Вернёмся к борд'рлесс дизайну с другим подходом в будущем.

---

## [0.6.1] — 2026-04-22

### Новое
- **Redesign UpdateBanner** — 420×170, accent-полоска слева, иконка ⬇ в круглом фоне, CTkProgressBar вместо текста «Скачано 50%», slide-down + fade-in анимация 200мс
- **Inline-редактирование** задач слайд-down панелью в окне вместо отдельного popup'а
- **Drag-and-drop** теперь работает на пустые дни (без созданных задач)
- **Global hotkey Alt+Z** — toggle главного окна из любого приложения
- **Diff-rebuild недели** — карточки дней обновляются in-place без мерцания
- **Sync → UI callback** — данные с сервера появляются мгновенно (раньше ждали 30с-таймер)
- **Fade show/hide** главного окна 150мс

### UX
- **Sage-зелёный overlay** (`#A8B89A → #7A9B6B`) вместо синего, +30% размер (56→73px)
- **Crisp badge** с тёмной обводкой для читаемости цифры на светлых обоях
- **Новая иконка** в палитре темы (крем + синий акцент)
- **Стрелки недели** в цвет темы (transparent + text_primary)
- **Тонкая 1px рамка** главного окна для контраста с обоями

### Откачено (для стабильности)
- Custom title-bar (`overrideredirect(True)`) и скрытие из taskbar (`WS_EX_TOOLWINDOW`) вызывали Windows ошибку «параметр задан неправильно» на некоторых DWM-конфигах Win11 — откатили к native Windows рамке. Вернёмся позже с другим подходом.

### Тесты
- 473 passing (+12 новых: fade, diff-rebuild, sync callback, DaySection.set_day_date)

---

## [0.6.0] — 2026-04-22

### Новое
- **Alt+Z** — глобальный хоткей toggle главного окна (работает из любого приложения)
- **Inline-редактирование задачи** — slide-down панель прямо в окне вместо отдельного popup'а (Esc для закрытия)
- **Custom title-bar** — убрана native-полоса Windows, свой мини-header с drag + resize-grip в правом нижнем углу
- **Fade-эффект** 150мс при show/hide главного окна
- **Sync → UI callback** — данные с сервера появляются мгновенно, без 30-секундного лага таймера
- **Diff-rebuild недели** — при смене недели карточки дней обновляются in-place без destroy+recreate (больше не мерцают)
- **Глобальный resize** главного окна с тонкой 1px-рамкой для контраста с обоями

### UX
- **Overlay** — новая sage/оливково-зелёная палитра вместо синей (`#A8B89A → #7A9B6B`)
- **Overlay-badge** — увеличен с 16/56 до 22/56, тёмный outline для читаемости цифры на светлых обоях
- **Overlay +30% размер** — 56→73px для лучшей видимости
- **Иконка** — новая, в палитре темы (крем + синий акцент, multi-size ico)
- **Стрелки недели** — transparent + text_primary вместо синих CTkButton-default; "Сегодня" с тонкой рамкой text_tertiary
- **Border window** — новый токен тёплого серого во всех 3 темах (`#8A7D6B` / `#4A433B` / `#7A6B52`)

### Фиксы
- **DnD на пустой день** — DropZone теперь на всю карточку дня, а не на скрытый body_frame (раньше нельзя было перенести задачу на день без задач)

### Тесты
- 473 passing, 12 новых unit-тестов (fade, diff-rebuild, sync callback, DaySection.set_day_date)

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
