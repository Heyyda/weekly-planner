# Личный Еженедельник

Десктопный недельный планировщик для Windows с синхронизацией через Telegram-бот.

На рабочем столе живёт перетаскиваемый sage-зелёный квадратик — клик открывает окно с задачами текущей недели. Задачи синхронизируются между ПК и Telegram-ботом.

---

## 📥 Скачать последнюю версию

**[⬇️ Скачать для Windows (~22 МБ)](https://github.com/Heyyda/weekly-planner/releases/latest/download/default.exe)**

Этот файл всегда ведёт на последнюю версию. После первого запуска встроенный автообновлятор сам скачает следующие релизы.

Все версии: [Releases](https://github.com/Heyyda/weekly-planner/releases)

---

## 🚀 Первый запуск

1. Скачай `.exe` по ссылке выше
2. (Опционально) переименуй `default.exe` → `Личный Еженедельник.exe`
3. Двойной клик → откроется окно входа
4. Введи свой Telegram username (без `@`)
5. В чат с [`@Jazzways_bot`](https://t.me/Jazzways_bot) придёт 6-значный код
6. Введи код → JWT сохранится в Windows Credential Manager
7. Появится синий квадратик в правом-верхнем углу экрана — это overlay
8. Клик по квадратику → открывается главное окно с задачами
9. В системном трее — иконка с меню (автозапуск, темы, выход)

---

## ✨ Что умеет

### Десктоп
- **Sage-зелёный overlay-квадратик** на рабочем столе (можно перетаскивать)
- **Главное окно** — 7 дней недели, компактный вид, custom title-bar без native-рамки, fade show/hide
- **Alt+Z** — глобальный хоткей toggle окна из любого приложения
- **Quick-capture**: правый клик на overlay → всплывает поле ввода → "встреча завтра 14:00" → задача на завтра
- **Smart parse** русского текста: `сегодня/завтра/послезавтра/пн-вс + HH:MM`
- **Drag-and-drop** задач между днями мышкой (включая пустые дни)
- **Inline-редактирование** — slide-down панель прямо в окне (Esc / Ctrl+Enter)
- **Undo** удалённых задач (5 секунд на отмену, Gmail-style)
- **Overdue alerts** — просроченные задачи подсвечиваются красным, overlay пульсирует
- **3 стиля задач** (card / line / minimal) — переключаются в tray-меню
- **3 темы** (light / dark / beige)
- **Автообновление** через GitHub Releases (SHA256 verify)

### Telegram-бот [@Jazzways_bot](https://t.me/Jazzways_bot)
- `/add <текст>` — добавить задачу (smart-parse как на десктопе)
- `/today` — список задач на сегодня + inline-кнопки (✅ Выполнить / ⏩ На завтра)
- `/week` — вся неделя одним сообщением

---

## 🔄 Синхронизация

Одна БД на сервере (VPS `planner.heyda.ru`). Десктоп и бот пишут в неё одновременно.

- **Optimistic UI**: задачи появляются мгновенно локально, фоновый sync каждые 30 секунд
- **Offline-first**: всё работает без интернета, синк при восстановлении сети
- **Multi-device**: залогинься на нескольких ПК — задачи те же на всех устройствах
- **Tombstones**: удалённые задачи с отметкой `deleted_at`, не real DELETE

---

## 📋 Changelog

См. [CHANGELOG.md](CHANGELOG.md)

---

## 🛠 Для разработки

```bash
git clone https://github.com/Heyyda/weekly-planner
cd weekly-planner
pip install -r requirements.txt
python main.py
```

Тесты:
```bash
python -m pytest client/tests server/tests
```

Сборка .exe:
```bash
pyinstaller --clean planner.spec
# → dist/Личный Еженедельник.exe
```

---

## 📦 Stack

- **Клиент**: Python 3.12 + CustomTkinter + pystray + winotify + keyring
- **Сервер**: FastAPI + SQLite (aiosqlite) + PyJWT + Alembic
- **Бот**: aiogram 3.x (long-polling)
- **Сборка**: PyInstaller 6.x (onefile, windowed)
- **Deploy**: systemd на VPS, Traefik reverse-proxy

---

## 🔒 Безопасность

- JWT токены в Windows Credential Manager (keyring)
- Telegram allow-list на сервере (`ALLOWED_USERNAMES` env)
- HTTPS через Let's Encrypt
- Bot token в `/etc/planner/planner.env` (chmod 600)

---

Made by [@Heyyda](https://github.com/Heyyda) — zibr@yandex.ru
