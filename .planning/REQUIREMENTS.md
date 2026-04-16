# Requirements: Личный Еженедельник

**Defined:** 2026-04-14
**Core Value:** Быстро записать задачу, прилетевшую "в моменте", и не забыть её — даже при работе с двух Windows-компьютеров и Telegram на мобиле.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Authentication (AUTH)

- [x] **AUTH-01**: Пользователь может запросить код авторизации через Telegram (ввод username в клиенте → бот присылает 6-значный код)
- [x] **AUTH-02**: Пользователь может ввести полученный код и получить JWT (access + refresh)
- [x] **AUTH-03**: JWT хранится в keyring (Windows Credential Manager) между запусками приложения
- [x] **AUTH-04**: Клиент автоматически обновляет access-token через refresh-token при истечении
- [x] **AUTH-05**: Пользователь может разлогиниться через tray-меню (очистка keyring и локального кеша)

### Server + Data (SRV)

- [x] **SRV-01**: REST API `/auth/request-code`, `/auth/verify`, `/auth/refresh` — Telegram-авторизация с кодом
- [x] **SRV-02**: REST API `/sync` — delta-синхронизация по `since` timestamp с soft-delete (tombstones)
- [x] **SRV-03**: SQLite с WAL-режимом и `busy_timeout=5000` для безопасной параллельной записи от нескольких клиентов
- [x] **SRV-04**: Модели данных: `User`, `Task` (с UUID id, `deleted_at`, `updated_at`), `AuthCode`, `Session`
- [ ] **SRV-05**: FastAPI deployed на VPS 109.94.211.29 как отдельный systemd-юнит рядом с E-bot
- [x] **SRV-06**: API отдаёт согласованные timestamp'ы (server-side `updated_at` — source of truth)

### Client Storage + Sync (SYNC)

- [x] **SYNC-01**: Локальный кеш задач в JSON-файле `cache.json` в AppData (оффлайн-работа)
- [x] **SYNC-02**: Optimistic UI: операции применяются к кешу мгновенно, ставятся в очередь `pending_changes`
- [x] **SYNC-03**: Фоновый sync-поток периодически отправляет `pending_changes` и забирает delta с сервера
- [x] **SYNC-04**: `threading.Lock` на доступ к `pending_changes` из UI- и sync-потоков (предотвращение race condition)
- [x] **SYNC-05**: При конфликте server-wins (серверный `updated_at` переопределяет локальный)
- [x] **SYNC-06**: UUID ID генерируются на клиенте — CREATE идемпотентен, не ждёт сервер
- [x] **SYNC-07**: При восстановлении сети после оффлайн — автоматический full resync всех накопленных изменений
- [x] **SYNC-08**: Tombstone для удалений (`deleted_at`) — не создавать задачу заново на другом устройстве

### Overlay — Кружок (OVR)

- [x] **OVR-01**: Перетаскиваемый круглый оверлей на рабочем столе Windows (overrideredirect + topmost)
- [x] **OVR-02**: Позиция кружка запоминается между запусками (`settings.json`)
- [x] **OVR-03**: Работает на multi-monitor setup (ctypes EnumDisplayMonitors)
- [x] **OVR-04**: Клик по кружку открывает/закрывает главное окно с недельным планом
- [x] **OVR-05**: Кружок визуально пульсирует при наличии просроченных задач (`done=false && day < today`)
- [x] **OVR-06**: Режим "всегда поверх всех окон" — переключаемый, применяется и к кружку, и к окну

### Week View — Главное окно (WEEK)

- [ ] **WEEK-01**: Окно отображает текущую неделю (Пн-Вс, 7 дней-колонок или секций)
- [ ] **WEEK-02**: Стрелки навигации: предыдущая/следующая неделя; показывается номер недели и диапазон дат
- [ ] **WEEK-03**: Кнопка "Сегодня" — быстрый возврат к текущей неделе
- [ ] **WEEK-04**: Просроченные задачи подсвечены красным (визуальная метка)
- [ ] **WEEK-05**: Минималистичный закруглённый дизайн задач-блоков (следуя UI-SPEC из `/gsd:ui-phase`)
- [ ] **WEEK-06**: Архив прошлых недель — через те же стрелки навигации можно отмотать назад и увидеть что было

### Task CRUD + Drag (TASK)

- [ ] **TASK-01**: Добавление задачи: текст + день + время/дедлайн (2-3 действия)
- [ ] **TASK-02**: Отметить задачу выполненной (checkbox или тап)
- [ ] **TASK-03**: Редактировать текст/время существующей задачи
- [ ] **TASK-04**: Удалить задачу (мягкое удаление, попадает в server tombstone)
- [ ] **TASK-05**: Drag-and-drop задачи между днями текущей недели
- [ ] **TASK-06**: Drag-and-drop задачи на следующую неделю (drop zone / стрелка)
- [ ] **TASK-07**: Позиция задачи в дне (`position`) запоминается — ручная сортировка возможна

### System Tray + Settings (TRAY)

- [ ] **TRAY-01**: Иконка в system tray (pystray) с контекстным меню
- [ ] **TRAY-02**: Через меню — toggle "Поверх всех окон", "Не беспокоить", "Показывать уведомления", "Разлогиниться", "Выход"
- [ ] **TRAY-03**: Настройки сохраняются в `settings.json` и применяются мгновенно
- [ ] **TRAY-04**: pystray использует `run_detached()` + `root.after(0, ...)` (избежать Tkinter thread crash)

### Notifications (NOTIF)

- [ ] **NOTIF-01**: Настраиваемый режим уведомлений: "пульсация кружка" / "пульсация + Windows toast" / "тихо"
- [ ] **NOTIF-02**: Toast через Windows 10/11 toast-нотификации (plyer или win10toast_click)
- [ ] **NOTIF-03**: Уведомления приходят при наступлении времени/дедлайна задачи (done=false)
- [ ] **NOTIF-04**: Режим "Не беспокоить" полностью блокирует toast (пульсация остаётся как пассивный сигнал)

### Telegram Bot (BOT)

- [ ] **BOT-01**: Бот развёрнут на VPS как отдельный процесс (aiogram 3.x), авторизуется тем же JWT что и desktop-клиент
- [ ] **BOT-02**: Команда `/start` — привязка Telegram username к аккаунту
- [ ] **BOT-03**: Команда `/add <текст>` — быстро создать задачу на сегодня
- [ ] **BOT-04**: Команда `/today` и `/week` — просмотр текущего дня / текущей недели
- [ ] **BOT-05**: Кнопка "отметить выполненной" на inline-клавиатуре под каждой задачей
- [ ] **BOT-06**: Бот отправляет 6-значные коды подтверждения для авторизации desktop-клиента

### Distribution + Autostart (DIST)

- [ ] **DIST-01**: Сборка в один установочный артефакт (`.exe` или одна папка) через PyInstaller
- [ ] **DIST-02**: `.spec` файл с `collect_data_files('customtkinter')` и `--noupx` для минимизации AV false-positives
- [ ] **DIST-03**: keyring Windows backend явно импортируется для работы в frozen exe
- [ ] **DIST-04**: Опциональный автозапуск Windows (tray-тоггл, регистрация в реестре `HKCU\...\Run`)
- [ ] **DIST-05**: Auto-update: при старте проверяется новая версия на сервере, скачивается, SHA256 verify, `.bat`-trick для замены .exe (паттерн из E-bot)
- [ ] **DIST-06**: Установщик работает из пути с кириллицей (`s:\Проекты\...`) — тест на реальной машине владельца

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Task extensions

- **TASKX-01**: Приоритет задачи (1-3)
- **TASKX-02**: Категории/проекты
- **TASKX-03**: Повторяющиеся задачи (cron-подобное правило, генерация при открытии недели)
- **TASKX-04**: Подзадачи (чек-лист внутри задачи)
- **TASKX-05**: Теги

### UX improvements

- **UXI-01**: Глобальный хоткей вызова (Win+Q или настраиваемый) — через pynput или Win32 RegisterHotKey с fallback
- **UXI-02**: Быстрый add через хоткей (mini-input overlay без открытия главного окна)
- **UXI-03**: Drag-and-drop между произвольными неделями (не только следующая)
- **UXI-04**: Undo последнего действия (Ctrl+Z)
- **UXI-05**: Поиск по задачам (всем неделям)

### Social / Multi-user

- **SOC-01**: Shared-списки для команды снабжения (колаборация)
- **SOC-02**: Приглашение коллег через Telegram-бот
- **SOC-03**: Permissions (read-only / edit)

### Analytics

- **ANA-01**: Статистика выполненных/просроченных за неделю (процент)
- **ANA-02**: Heatmap продуктивности по дням

### Platform

- **PLAT-01**: macOS-порт (CustomTkinter поддерживает; тестировать overlay на Cocoa)
- **PLAT-02**: Native Android/iOS приложение (если Telegram-бот окажется недостаточным)
- **PLAT-03**: Web-интерфейс (мобильный браузер как fallback)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Приоритет в v1 task-model | Сознательный минимализм ввода. Пользователь подтвердил: `text + day + time`. Приоритет в v2 (TASKX-01) |
| Категории/проекты в v1 | Таксономия в момент capture замедляет ввод → нарушает Core Value. Research (FEATURES.md) подтверждает как anti-feature для minimalist-планировщиков |
| Recurring tasks в v1 | Добавляет UI-сложность (выбор правила повторения). v2 (TASKX-03) |
| Native мобильное приложение (iOS/Android) | Telegram-бот покрывает мобильный quick-capture. Снимает значительный объём работы |
| macOS / Linux поддержка | Владелец на Windows; целевой контекст — рабочий десктоп Windows |
| Многопользовательские списки / колаборация | Продукт single-user; общие задачи не нужны Никите в v1 |
| OAuth (Google / Apple / email) | Telegram-авторизация достаточна и уже отлажена в E-bot |
| Аналитика и графики продуктивности | Архив прошлых недель покрывает "что сделал / что забыл" без BI |
| Комплексные звуковые напоминания | v1 ограничивается пульсацией и опциональным Windows toast (plyer) |
| Поиск по задачам | Добавляет сложность UI; в v1 достаточно визуальной навигации по неделям |
| AI-фичи (автокатегоризация, AI-ассистент) | Anti-feature для минималистичного планировщика (подтверждено research/FEATURES.md) |
| Code-signing (EV cert) в v1 | ~$300/год — принимается сознательно; AV false-positives митигируются через `--noupx` и спец-сборку |
| Global hotkey в v1 | Низкоуровневые кейборд-хуки требуют elevation, работают ненадёжно. Вызов через кружок достаточен. v2 (UXI-01) |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Complete |
| AUTH-02 | Phase 1 | Complete |
| AUTH-03 | Phase 1 | Complete |
| AUTH-04 | Phase 1 | Complete |
| AUTH-05 | Phase 1 | Complete |
| SRV-01 | Phase 1 | Complete |
| SRV-02 | Phase 1 | Complete |
| SRV-03 | Phase 1 | Complete |
| SRV-04 | Phase 1 | Complete |
| SRV-05 | Phase 1 | Pending |
| SRV-06 | Phase 1 | Complete |
| SYNC-01 | Phase 2 | Complete |
| SYNC-02 | Phase 2 | Complete |
| SYNC-03 | Phase 2 | Complete |
| SYNC-04 | Phase 2 | Complete |
| SYNC-05 | Phase 2 | Complete |
| SYNC-06 | Phase 2 | Complete |
| SYNC-07 | Phase 2 | Complete |
| SYNC-08 | Phase 2 | Complete |
| OVR-01 | Phase 3 | Complete |
| OVR-02 | Phase 3 | Complete |
| OVR-03 | Phase 3 | Complete |
| OVR-04 | Phase 3 | Complete |
| OVR-05 | Phase 3 | Complete |
| OVR-06 | Phase 3 | Complete |
| TRAY-01 | Phase 3 | Pending |
| TRAY-02 | Phase 3 | Pending |
| TRAY-03 | Phase 3 | Pending |
| TRAY-04 | Phase 3 | Pending |
| NOTIF-01 | Phase 3 | Pending |
| NOTIF-02 | Phase 3 | Pending |
| NOTIF-03 | Phase 3 | Pending |
| NOTIF-04 | Phase 3 | Pending |
| WEEK-01 | Phase 4 | Pending |
| WEEK-02 | Phase 4 | Pending |
| WEEK-03 | Phase 4 | Pending |
| WEEK-04 | Phase 4 | Pending |
| WEEK-05 | Phase 4 | Pending |
| WEEK-06 | Phase 4 | Pending |
| TASK-01 | Phase 4 | Pending |
| TASK-02 | Phase 4 | Pending |
| TASK-03 | Phase 4 | Pending |
| TASK-04 | Phase 4 | Pending |
| TASK-05 | Phase 4 | Pending |
| TASK-06 | Phase 4 | Pending |
| TASK-07 | Phase 4 | Pending |
| BOT-01 | Phase 5 | Pending |
| BOT-02 | Phase 5 | Pending |
| BOT-03 | Phase 5 | Pending |
| BOT-04 | Phase 5 | Pending |
| BOT-05 | Phase 5 | Pending |
| BOT-06 | Phase 5 | Pending |
| DIST-01 | Phase 6 | Pending |
| DIST-02 | Phase 6 | Pending |
| DIST-03 | Phase 6 | Pending |
| DIST-04 | Phase 6 | Pending |
| DIST-05 | Phase 6 | Pending |
| DIST-06 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 58 enumerated (header said 55; actual count from requirement IDs is 58)
- Mapped to phases: 58
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 — traceability populated by roadmapper*
