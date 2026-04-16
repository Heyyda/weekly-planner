# Roadmap: Личный Еженедельник

**Milestone:** v1 — Полный рабочий продукт
**Granularity:** standard
**Coverage:** 58/58 требований распределены по фазам

---

## Phases

- [ ] **Фаза 1: Сервер и авторизация** — REST API + SQLite + Telegram JWT-авторизация задеплоены и проверены curl'ом
- [ ] **Фаза 2: Клиентское ядро** — Модели данных, локальный кеш, фоновая синхронизация — фундамент для UI
- [ ] **Фаза 3: Оверлей и системная интеграция** — Кружок-оверлей, system tray, уведомления — всё работает на Windows
- [ ] **Фаза 4: Недельный вид и задачи** — Полноценный UI недели, CRUD задач, drag-and-drop (риск: DnD на CustomTkinter)
- [ ] **Фаза 5: Telegram-бот** — Мобильный quick-capture: /add, /week, /today, отметить выполненным
- [ ] **Фаза 6: Дистрибуция и автообновление** — Один .exe через PyInstaller, SHA256 автообновление, автозапуск

---

## Phase Details

### Phase 1: Сервер и авторизация

**Goal**: Сервер работает в продакшне на VPS, авторизация через Telegram выдаёт JWT — это gate для всего остального

**Depends on**: Ничего (первая фаза)

**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, SRV-01, SRV-02, SRV-03, SRV-04, SRV-05, SRV-06

**Success Criteria** (что должно быть ИСТИННО после завершения фазы):
  1. Пользователь вводит Telegram username → бот присылает 6-значный код → пользователь вводит код → получает JWT; всё через curl или Postman
  2. `GET /health` и `GET /version` отвечают 200 на `http://109.94.211.29:8100`
  3. `POST /sync` принимает список изменений и возвращает дельту задач, авторизованных через JWT Bearer
  4. SQLite работает в WAL-режиме: два одновременных запроса не вызывают `OperationalError: database is locked`
  5. Сервер запущен как systemd-юнит и автоматически рестартует после перезагрузки VPS

**Research flags**: Нет (сервер без риска — паттерн из E-bot, stack zafixirован)

**Plans:** 11/11 plans complete

Plans:
- [x] 01-01-PLAN.md — Wave 0: тестовая инфраструктура (pytest, conftest, requirements-dev), структура server/{api,auth,db,bot}
- [x] 01-02-PLAN.md — Wave 1: SQLAlchemy модели (User, AuthCode, Session, Task) + Alembic первая миграция — SRV-04, SRV-06
- [x] 01-03-PLAN.md — Wave 1: async engine + PRAGMA WAL/busy_timeout event + pydantic-settings config — SRV-03
- [x] 01-04-PLAN.md — Wave 2: JWT (PyJWT) + SessionService + get_current_user dependency — AUTH-02..05
- [x] 01-05-PLAN.md — Wave 2: AuthCodeService (bcrypt hash, single-use) + Telegram send via httpx — AUTH-01, SRV-01
- [x] 01-06-PLAN.md — Wave 3: 5 auth endpoints (request-code, verify, refresh, logout, me) + FastAPI app — AUTH-01..05, SRV-01
- [x] 01-07-PLAN.md — Wave 3: POST /api/sync (delta + tombstones) — SRV-02, SRV-06
- [x] 01-08-PLAN.md — Wave 3: GET /api/health + /version + rate-limit через slowapi — SRV-01
- [x] 01-09-PLAN.md — Wave 4: aiogram /start handler (запись chat_id) — AUTH-01
- [x] 01-10-PLAN.md — Wave 5: deploy на VPS (systemd, reverse-proxy, env, runbook, checkpoint) — SRV-05
- [x] 01-11-PLAN.md — Wave 5: e2e integration test + smoke-test.sh + final ROADMAP verify checkpoint

---

### Phase 2: Клиентское ядро

**Goal**: Десктопный клиент умеет хранить задачи локально и синхронизировать их с сервером — без UI, но проверяемо через логи

**Depends on**: Фаза 1 (нужен рабочий /sync эндпойнт)

**Requirements**: SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06, SYNC-07, SYNC-08

**Success Criteria** (что должно быть ИСТИННО после завершения фазы):
  1. Задача, созданная в `cache.json` offline, автоматически появляется на сервере при восстановлении сети (проверяется через `/tasks` API)
  2. 50 задач, созданных подряд при отключённой сети, все доходят до сервера после reconnect — без потерь и дублей
  3. Задача, удалённая на одном устройстве, не воссоздаётся при синхронизации с другого (tombstone работает)
  4. `threading.Lock` защищает `pending_changes` — нет race condition при одновременном добавлении из UI и сбросе sync-потоком

**Research flags**: Нет (паттерны operation queue + tombstone описаны в research/ARCHITECTURE.md)

**Plans:** 8/8 plans complete

Plans:
- [x] 02-01-PLAN.md — Wave 0: pytest-инфраструктура (conftest, pyproject, requirements-dev, fixtures tmp_appdata + mock_api)
- [x] 02-02-PLAN.md — Wave 1: client/core/models.py (Task + TaskChange + utcnow_iso) + paths.py + config.py — SYNC-06
- [x] 02-03-PLAN.md — Wave 1: logging_setup с RotatingFileHandler + SecretFilter (D-27, D-29)
- [x] 02-04-PLAN.md — Wave 2: AuthManager rewrite (правильные endpoints, keyring rotation, threading.Lock)
- [x] 02-05-PLAN.md — Wave 2: LocalStorage rewrite (Lock + atomic write + drain + soft-delete + merge) — SYNC-01,02,04,08
- [x] 02-06-PLAN.md — Wave 3: SyncApiClient (auth + 401-retry + exponential backoff) — SYNC-06
- [x] 02-07-PLAN.md — Wave 3: SyncManager rewrite (Event wake + stale detection + tombstone cleanup) — SYNC-03,05,07
- [x] 02-08-PLAN.md — Wave 4: E2E integration tests + log-safety verification — SYNC-01..08

---

### Phase 3: Оверлей и системная интеграция

**Goal**: Кружок живёт на рабочем столе — перетаскивается, запоминает позицию, пульсирует при просрочке; tray и уведомления работают без краша

**Depends on**: Фаза 2 (нужны модели Task и LocalStorage для overdue-detection)

**Requirements**: OVR-01, OVR-02, OVR-03, OVR-04, OVR-05, OVR-06, TRAY-01, TRAY-02, TRAY-03, TRAY-04, NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04

**Success Criteria** (что должно быть ИСТИННО после завершения фазы):
  1. Кружок перетаскивается на любой из двух мониторов мышью, позиция сохраняется между перезапусками приложения
  2. Клик по кружку открывает/закрывает главное окно; кружок пульсирует при наличии просроченных задач и останавливается когда все сделаны
  3. Правый клик на tray-иконке показывает меню; переключение "Поверх всех окон" применяется мгновенно — к кружку и к окну одновременно
  4. 20 быстрых кликов по tray-меню подряд: приложение не зависает, не падает с `RuntimeError: main thread is not in main loop`
  5. В режиме "Не беспокоить" Windows toast не появляется; при наступлении дедлайна задачи в обычном режиме toast приходит

**UI Phase required**: Да — `/gsd:ui-phase` должен сгенерировать `UI-SPEC.md` (палитра, кружок-дизайн, анимация) перед планированием этой фазы

**Research flags**:
  - `overrideredirect(True)` на Windows 11 требует `after(100, ...)` delay — см. PITFALLS.md Pitfall 1 / STACK.md Gotcha 1
  - pystray + Tkinter: использовать `run_detached()` + `root.after(0, callback)` — см. PITFALLS.md Pitfall 2

**Plans:** 7/11 plans executed

Plans:
- [x] 03-01-PLAN.md — Wave 0: extend conftest.py с headless_tk + mock_pystray/winotify/winreg/ctypes_dpi fixtures
- [x] 03-02-PLAN.md — Wave 1: ThemeManager (3 палитры UI-SPEC) + UISettings dataclass + SettingsStore
- [x] 03-03-PLAN.md — Wave 1: icon_compose.render_overlay_image (Pillow композитор overlay/tray иконки)
- [x] 03-04-PLAN.md — Wave 2: OverlayManager — draggable 56×56 + position persist + multi-monitor — OVR-01, 02, 03, 04, 06
- [x] 03-05-PLAN.md — Wave 2: PulseAnimator — 60fps root.after driver — OVR-05
- [x] 03-06-PLAN.md — Wave 3: MainWindow shell — resizable + аккордеон Пн-Вс + theme subscribe
- [x] 03-07-PLAN.md — Wave 3: TrayManager — pystray run_detached + все callbacks через root.after(0) — TRAY-01..04
- [ ] 03-08-PLAN.md — Wave 4: NotificationManager — winotify daemon thread + 3 режима + deadline detection — NOTIF-01..04
- [ ] 03-09-PLAN.md — Wave 4: autostart.py rewrite — ASCII value name LichnyEzhednevnik (frozen-exe safety)
- [ ] 03-10-PLAN.md — Wave 5: WeeklyPlannerApp integration — wire all 6 компонентов, Cyrillic-path main.py
- [ ] 03-11-PLAN.md — Wave 5: E2E tests + 03-VALIDATION.md update + human-verify checkpoint (17 пунктов)

---

### Phase 4: Недельный вид и задачи

**Goal**: Пользователь видит полную картину недели, добавляет задачи за 2-3 действия, перетаскивает их между днями — всё работает в реальном использовании

**Depends on**: Фаза 3 (кружок открывает это окно; нужен overlay рабочий)

**Requirements**: WEEK-01, WEEK-02, WEEK-03, WEEK-04, WEEK-05, WEEK-06, TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-06, TASK-07

**Success Criteria** (что должно быть ИСТИННО после завершения фазы):
  1. Пользователь открывает приложение и видит текущую неделю (Пн-Вс); стрелки навигации переключают недели; кнопка "Сегодня" возвращает к текущей
  2. Добавить задачу: ввести текст + выбрать день + опционально время — не более 3 действий; задача появляется немедленно (optimistic UI)
  3. Drag-and-drop задачи на другой день в той же неделе работает без глитчей; drag на "следующую неделю" переносит задачу и подтверждается визуально
  4. Просроченные задачи (done=false && day < today) отображаются красным; выполненные визуально отличаются от невыполненных
  5. Листая назад через стрелки навигации, видно прошлые недели с задачами — "архив" без отдельного экрана

**UI Phase required**: Да — `/gsd:ui-phase` должен сгенерировать `UI-SPEC.md` (week view layout, task widget design, DnD visual feedback) перед планированием этой фазы

**Research flags**:
  - **DnD на CustomTkinter — высокий риск**: нет встроенного drag-and-drop; требует ctypes mouse events или Canvas-based DnD. Провести phase-research перед планированием: какой подход (Canvas overlay? ctypes WH_MOUSE hook?) работает в CustomTkinter 5.2.2 без конфликта с mainloop
  - Полная перерисовка при каждом изменении задачи → потеря scroll position; нужны partial updates (только изменённый TaskWidget)
  - `after(100, overrideredirect)` для главного окна — та же проблема что у overlay

**Plans**: TBD

---

### Phase 5: Telegram-бот

**Goal**: Пользователь добавляет задачи из Telegram на телефоне и видит текущую неделю — мобильный quick-capture работает

**Depends on**: Фаза 1 (стабильный сервер); Фаза 4 желательна (чтобы тестировать сквозной flow: бот добавил → десктоп показал)

**Requirements**: BOT-01, BOT-02, BOT-03, BOT-04, BOT-05, BOT-06

**Success Criteria** (что должно быть ИСТИННО после завершения фазы):
  1. `/add купить молоко` — задача создаётся на сегодня и появляется в десктопном клиенте после следующего sync-цикла (≤30 сек)
  2. `/today` и `/week` возвращают форматированный список задач; выполненные отмечены визуально в тексте ответа
  3. Inline-кнопка "Выполнено" под задачей меняет её статус; при следующем sync на десктопе задача тоже отмечена выполненной
  4. Бот запущен как отдельный systemd-юнит на VPS и не падает при рестарте сервера FastAPI

**Research flags**: Нет (aiogram 3.x long-polling как отдельный процесс — паттерн описан в research/ARCHITECTURE.md)

**Plans**: TBD

---

### Phase 6: Дистрибуция и автообновление

**Goal**: Один .exe-файл запускается на чистом Windows без Python; автообновляется; автозапуск работает из трея

**Depends on**: Фазы 2-4 (стабильный клиент для упаковки)

**Requirements**: DIST-01, DIST-02, DIST-03, DIST-04, DIST-05, DIST-06

**Success Criteria** (что должно быть ИСТИННО после завершения фазы):
  1. `.exe` запускается на чистой Windows 10/11 без Python — нет "missing DLL" или "unstyled widgets" ошибок
  2. Авторизация через Telegram работает в упакованном `.exe` — keyring Windows backend находится (нет `NoKeyringError`)
  3. Тоггл автозапуска в tray-меню добавляет/удаляет `.exe` из `HKCU\...\Run`; приложение появляется при следующей загрузке Windows
  4. Автообновление: сервер публикует новую версию → `.exe` при запуске скачивает, проверяет SHA256, применяет rename-trick, перезапускается
  5. `.exe` запускается с пути с кириллицей (`s:\Проекты\...`) без encoding crash

**Research flags**:
  - **CustomTkinter + --onefile**: требует `.spec` файл с `collect_data_files('customtkinter')` + `sys._MEIPASS` chdir — см. PITFALLS.md Pitfall 1
  - keyring в frozen exe: явный import `keyring.backends.Windows` + `hiddenimports` в `.spec` — см. PITFALLS.md Pitfall 7
  - Автообновление: файл-блокировка на Windows — rename trick, не прямая замена `.exe` — см. PITFALLS.md Pitfall 6
  - Проверить на чистой Windows VM (не dev-машине) перед финальным релизом

**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Сервер и авторизация | 11/11 | Complete    | 2026-04-15 |
| 2. Клиентское ядро | 8/8 | Complete    | 2026-04-16 |
| 3. Оверлей и системная интеграция | 7/11 | In Progress|  |
| 4. Недельный вид и задачи | 0/? | Not started | - |
| 5. Telegram-бот | 0/? | Not started | - |
| 6. Дистрибуция и автообновление | 0/? | Not started | - |

---

## Coverage Map

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | 1 | Pending |
| AUTH-02 | 1 | Pending |
| AUTH-03 | 1 | Pending |
| AUTH-04 | 1 | Pending |
| AUTH-05 | 1 | Pending |
| SRV-01 | 1 | Pending |
| SRV-02 | 1 | Pending |
| SRV-03 | 1 | Pending |
| SRV-04 | 1 | Pending |
| SRV-05 | 1 | Pending |
| SRV-06 | 1 | Pending |
| SYNC-01 | 2 | Pending |
| SYNC-02 | 2 | Pending |
| SYNC-03 | 2 | Pending |
| SYNC-04 | 2 | Pending |
| SYNC-05 | 2 | Pending |
| SYNC-06 | 2 | Pending |
| SYNC-07 | 2 | Pending |
| SYNC-08 | 2 | Pending |
| OVR-01 | 3 | Pending |
| OVR-02 | 3 | Pending |
| OVR-03 | 3 | Pending |
| OVR-04 | 3 | Pending |
| OVR-05 | 3 | Pending |
| OVR-06 | 3 | Pending |
| TRAY-01 | 3 | Pending |
| TRAY-02 | 3 | Pending |
| TRAY-03 | 3 | Pending |
| TRAY-04 | 3 | Pending |
| NOTIF-01 | 3 | Pending |
| NOTIF-02 | 3 | Pending |
| NOTIF-03 | 3 | Pending |
| NOTIF-04 | 3 | Pending |
| WEEK-01 | 4 | Pending |
| WEEK-02 | 4 | Pending |
| WEEK-03 | 4 | Pending |
| WEEK-04 | 4 | Pending |
| WEEK-05 | 4 | Pending |
| WEEK-06 | 4 | Pending |
| TASK-01 | 4 | Pending |
| TASK-02 | 4 | Pending |
| TASK-03 | 4 | Pending |
| TASK-04 | 4 | Pending |
| TASK-05 | 4 | Pending |
| TASK-06 | 4 | Pending |
| TASK-07 | 4 | Pending |
| BOT-01 | 5 | Pending |
| BOT-02 | 5 | Pending |
| BOT-03 | 5 | Pending |
| BOT-04 | 5 | Pending |
| BOT-05 | 5 | Pending |
| BOT-06 | 5 | Pending |
| DIST-01 | 6 | Pending |
| DIST-02 | 6 | Pending |
| DIST-03 | 6 | Pending |
| DIST-04 | 6 | Pending |
| DIST-05 | 6 | Pending |
| DIST-06 | 6 | Pending |

**Coverage: 58/58 ✓**

> Note: REQUIREMENTS.md header says 55 requirements; actual enumerated IDs total 58 (5+6+8+6+6+7+4+4+6+6). All 58 enumerated IDs are mapped above. The discrepancy is in the header count — all actual requirements are covered.

---

## Notes for Plan-Phase

**Фазы 3 и 4 требуют `/gsd:ui-phase` до планирования.**
Запустить `/gsd:ui-phase` перед `/gsd:plan-phase 3` и снова перед `/gsd:plan-phase 4`.
Фаза 3 — дизайн кружка, анимация, tray-иконка.
Фаза 4 — week view layout, task widget, DnD visual feedback.

**Фаза 4: DnD требует phase-research перед планированием.**
Drag-and-drop между колонками дней в CustomTkinter 5.2.2 не документирован официально.
Исследовать: Canvas overlay vs ctypes WH_MOUSE hook vs widget motion binding.
Без чёткого решения этот риск блокирует планирование фазы.

---

*Roadmap created: 2026-04-14*
*Last updated: 2026-04-14 after initialization*
