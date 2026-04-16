# Личный Еженедельник

## What This Is

Десктопный недельный планировщик для Windows с мобильным дополнением через Telegram-бот. На рабочем столе живёт перетаскиваемый круглый оверлей — клик открывает компактное окно с задачами текущей недели. Задачи синхронизируются между несколькими PC и Telegram-ботом. Владелец и единственный подтверждённый пользователь — Никита, менеджер по снабжению; коллеги возможны как расширение аудитории после валидации на себе.

## Core Value

Быстро записать задачу, которая прилетела "в моменте" (в перерыве между делами), и не забыть её — даже если записываю на работе с двух экранов и потом доделываю дома. Если speed-of-capture сломан — продукт не нужен. Всё остальное (синхронизация, архив, мобилка) существует чтобы обеспечить этот цикл.

## Requirements

### Validated

<!-- Shipped and confirmed working. -->

**Сервер (Phase 1 complete 2026-04-15):**
- ✓ FastAPI + SQLite (WAL + busy_timeout=5000) развёрнут на VPS 109.94.211.29 — `planner-api.service` + `planner-bot.service` активны и автозапускаются
- ✓ Reverse-proxy через Traefik → `https://planner.heyda.ru` (TLS auto-ACME)
- ✓ REST API: `/api/auth/{request-code,verify,refresh,logout,me}`, `/api/sync` (delta + tombstones + server-wins), `/api/health`, `/api/version`
- ✓ Telegram JWT-авторизация: 6-значный код → PyJWT access (15мин) + refresh (30д rolling)
- ✓ aiogram 3.x `/start` handler захватывает `chat_id` для доставки кодов
- ✓ Rate-limit через slowapi (1/мин + 5/час per IP) на `/auth/request-code`
- ✓ Allow-list пользователей через `ALLOWED_USERNAMES` env
- ✓ 92 pytest (unit + integration + E2E), 5/5 smoke-tests на проде
- ⚠ Soft-unverified (отложено): реальная доставка Telegram-кода самопроверится при первой авторизации Phase 3-6; VPS-reboot survival при следующем плановом обслуживании

**Клиентское ядро (Phase 2 complete 2026-04-16):**
- ✓ Локальный кеш `cache.json` в `%APPDATA%/ЛичныйЕженедельник/` с atomic write (`os.replace`)
- ✓ Optimistic UI: operation queue `pending_changes` в-памяти + persisted под `threading.Lock` (race-free доказано 5000-op stress test)
- ✓ Фоновый `SyncManager` — daemon thread с `threading.Event` wake (30s poll + immediate push)
- ✓ Exponential backoff 1s→60s, infinite retries, passive offline detection через HTTP errors
- ✓ Server-wins silent merge, soft-delete tombstones, opportunistic cleanup после 1h
- ✓ Full resync (since=None) при >5min offline; pending push ПЕРЕД resync
- ✓ AuthManager: correct `/auth/request-code` endpoints, keyring rotation, access-token RAM-only
- ✓ SecretFilter — JWT/refresh не попадают в логи (D-29 verified в реальном flow)
- ✓ 106 pytest (unit + stress + E2E через `requests-mock` FakeServer), Phase 1 сервер без регрессии

### Active

<!-- v1 scope — "всё сразу" по решению владельца. Это гипотезы, пока не отгружены и не отработали хотя бы неделю реального использования. -->

**Клиент Windows — Overlay:**
- [ ] Перетаскиваемый круглый оверлей на рабочем столе (2 монитора, позиция запоминается)
- [ ] Клик по кружку открывает компактное окно с текущей неделей
- [ ] Пульсация кружка при просроченных задачах
- [ ] Режим "поверх всех окон" (переключаемый, распространяется и на кружок, и на окно)

**Клиент Windows — Окно с задачами:**
- [ ] Недельный вид (7 дней, задачи как минималистичные закруглённые блоки)
- [ ] Добавить задачу: текст + день + время/дедлайн (ввод в 2-3 действия)
- [ ] Отметить задачу выполненной
- [ ] Drag-and-drop задач между днями
- [ ] Drag-and-drop задач на следующую неделю
- [ ] Подсветка просроченных (done=false && day < today)
- [ ] Навигация "предыдущая/следующая неделя" (стрелки)
- [ ] Архив прошлых недель (отмотать назад и увидеть что было)

**Клиент Windows — Системная интеграция:**
- [ ] Иконка в system tray с меню настроек (on/off фишки, закрепить поверх, "не беспокоить")
- [ ] Настраиваемые уведомления (пульсация / Windows toast / тихо)
- [ ] Автозапуск Windows (опциональный тоггл)
- [ ] Один .exe через PyInstaller

**Telegram-бот (мобильный ввод):**
- [ ] Авторизация по Telegram username (код подтверждения)
- [ ] Команда "добавить задачу" с быстрым вводом
- [ ] Просмотр текущей недели
- [ ] Отметить выполнение

### Out of Scope

- **Native мобильное приложение (iOS/Android)** — Telegram-бот покрывает мобильный юзкейс быстрого ввода, собственный клиент сильно увеличивает объём работы без валидированной пользы
- **macOS / Linux поддержка** — владелец на Windows, целевой контекст — рабочий Windows-десктоп
- **Многопользовательские списки / колаборация** — продукт single-user, общие задачи в скоуп не входят
- **OAuth (Google/Apple/email)** — Telegram-авторизация достаточна, паттерн уже работает в E-bot
- **Аналитика и графики продуктивности** — архив прошлых недель покрывает "что сделал / что забыл"; BI-функции не нужны
- **Повторяющиеся задачи (cron-шаблоны)** — упомянуты в CLAUDE.md, но v1 обходится без них; перенесено в v2
- **Категории задач** — упомянуты в исходной архитектуре, но v1 сознательно уходит от этой сложности (минимализм ввода)
- **Приоритеты задач** — сознательно убраны из v1 модели задачи (text + day + time); добавить — увеличить форму ввода
- **Комплексная система напоминаний со звуком** — v1 ограничивается пульсацией и опциональным Windows toast

## Context

**Владелец и пользователь**: Никита (Heyyda / zibr@yandex.ru), работает менеджером по снабжению. Типичная рабочая ситуация — задачи сыплются от людей в течение дня, часть из них нужна не сразу, а через несколько часов/дней, и эти "отложенные" легко теряются. Существующие планировщики (Todoist, Notion, календари) ему кажутся перегруженными или требующими большое окно для ввода.

**Дизайн-риск (важно)**: владелец явно отметил, что код и процессы я делаю хорошо, но **дизайн — мой слабый угол**. Митигация:
- Для UI-фаз использовать `/gsd:ui-phase` — генерирует `UI-SPEC.md` (палитра, типографика, layout-контракт), который владелец утверждает до кода
- `/gsd:ui-review` — аудит написанного UI по 6 пилларам
- Референс-driven design вместо импровизации (скриншот TickTick / Things 3 / макет в Figma)
- Figma MCP подключён — если владелец нарисует макет, читаем и следуем, не додумываем
- Атомарные GSD-коммиты позволяют откатить "некрасивый" UI

**Связанный проект — E-bot** (`S:\Проекты\е-бот\`): переиспользуемые паттерны, уже работающие в продакшне — Telegram-авторизация с кодом подтверждения, хранение JWT в keyring, автообновление с SHA256-проверкой, иконка в system tray, тёмная тема.

**VPS 109.94.211.29**: здесь уже крутится `device-manager.py` от E-bot; FastAPI-сервер нового проекта деплоим рядом (отдельный порт/юнит).

**Codebase сейчас**: каркас создан (`main.py`, `client/`, `server/`, `docs/`), все модули — заглушки (см. `.planning/codebase/` — полная карта). Детальная архитектура уже записана в корневом `CLAUDE.md` (stack-решения, sidebar-поведение, синхронизация, авторизация).

## Constraints

- **Tech stack (client)**: Python 3.12+, CustomTkinter, ctypes/win32gui, pystray — зафиксировано в CLAUDE.md и скелете, менять нецелесообразно
- **Tech stack (server)**: FastAPI + SQLite + SQLAlchemy + python-jose — зафиксировано
- **Инфраструктура**: сервер деплоится на VPS 109.94.211.29 рядом с E-bot-сервисами
- **Дистрибуция**: один `.exe` через `PyInstaller --onefile --windowed` — требование для простоты установки на рабочих PC
- **Коммуникация**: коммиты и документация на русском, UI на русском
- **Аудитория**: Windows 10/11 (DWM-совместимость `overrideredirect`/`SetWindowPos` — потенциальный риск, упомянут в CLAUDE.md)
- **Безопасность**: `.env`, секреты, keyring-данные не коммитятся; JWT в keyring аналогично E-bot
- **Дизайн-ресурс**: визуальная сложность UI должна оставаться низкой (минимализм — требование владельца, а не компромисс)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Кружок-оверлей вместо sidebar-за-краем | Пользователь прямо сказал что кружок удобнее; работает на 2 мониторах; перетаскиваемый | — Pending |
| Модель задачи: text + day + time/deadline | Минимизация формы ввода = скорость capture. Приоритет, категория — в v2 | — Pending |
| v1 включает сервер + синхрон + TG-бот сразу | Пользователь явно выбрал "всё сразу". Риск скоупа — митигируется разбиением на фазы | ⚠ Revisit (на milestone-аудите) |
| Telegram для мобильного ввода вместо native-app | Переиспользуем паттерн из E-bot, снимаем скоуп mobile-разработки | — Pending |
| CustomTkinter (не PyQt/Tauri/Electron) | Уже в скелете и requirements.txt; знаком по E-bot; достаточный для минималистичного UI | — Pending |
| JWT в keyring + Telegram-регистрация | Паттерн уже отработан в E-bot, безопасен, не требует email-инфраструктуры | — Pending |
| Один .exe через PyInstaller --onefile | Требование простой установки на рабочих PC коллег | — Pending |
| Server wins при конфликтах синхрона | Упрощает логику, соответствует single-user контексту | — Pending |
| Настройки приложения — через tray-меню | Пользователь прямо попросил. Избегаем перегрузки главного окна | — Pending |
| Дизайн-фазы через `/gsd:ui-phase` + референсы | Митигация признанной слабости в дизайне | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-16 after Phase 2 completion — client core (storage + sync) ready, 106 tests green*
