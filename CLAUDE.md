# Личный Еженедельник

## Описание
Десктопное приложение — недельный планировщик задач с боковой панелью.
Прячется за край экрана, выезжает при наведении/клике. Один .exe файл.
Название: **Личный Еженедельник**.

## Владелец
Никита (GitHub: Heyyda, email: zibr@yandex.ru). Язык общения: русский.

## Стек
- **Клиент**: Python 3.12+, CustomTkinter, ctypes/win32gui (sidebar), pystray (tray)
- **Сервер**: FastAPI на VPS 109.94.211.29 (рядом с E-bot device-manager.py)
- **БД**: SQLite на сервере (файл `weekly_planner.db`)
- **Авторизация**: JWT + Telegram (как в E-bot)
- **Сборка**: PyInstaller --onefile
- **Автообновление**: SHA256 проверка, как в E-bot

## Архитектура

```
S:\Проекты\ежедневник\
├── CLAUDE.md              ← ты тут
├── README.md
├── .gitignore
├── requirements.txt
├── main.py                ← точка входа (запуск приложения)
│
├── client/                ← весь клиентский код
│   ├── app.py             ← класс WeeklyPlannerApp (главное окно + sidebar логика)
│   ├── ui/
│   │   ├── sidebar.py     ← авто-скрытие за край экрана, анимация выезда
│   │   ├── week_view.py   ← навигация по неделям (стрелки, номер недели, даты)
│   │   ├── day_panel.py   ← сворачиваемая секция дня (заголовок + список задач)
│   │   ├── task_widget.py ← виджет задачи (checkbox + текст + приоритет + действия)
│   │   ├── notes_panel.py ← свободные заметки к дню
│   │   ├── stats_panel.py ← итоги недели (выполнено/просрочено/процент)
│   │   ├── settings_panel.py ← настройки (тема, автозапуск, хоткей, "не беспокоить")
│   │   └── themes.py      ← тёмная/светлая тема (палитры + шрифты)
│   ├── core/
│   │   ├── models.py      ← dataclass: Task, DayPlan, WeekPlan, Category
│   │   ├── storage.py     ← локальный кеш (JSON файл для оффлайн-работы)
│   │   ├── sync.py        ← синхронизация с сервером (pull/push/merge)
│   │   └── auth.py        ← JWT авторизация, Telegram-регистрация
│   ├── utils/
│   │   ├── hotkeys.py     ← глобальный хоткей (Win+Q) для вызова/скрытия
│   │   ├── tray.py        ← иконка в system tray, badge с кол-вом задач
│   │   ├── autostart.py   ← добавление/удаление из автозагрузки Windows
│   │   ├── updater.py     ← проверка обновлений, скачивание, SHA256
│   │   └── notifications.py ← всплывающие напоминания о просроченных задачах
│   └── assets/
│       └── icon.ico        ← иконка приложения (TODO: нарисовать)
│
├── server/                 ← серверная часть (деплоится на VPS)
│   ├── api.py              ← FastAPI роуты: /auth, /tasks, /weeks, /sync
│   ├── models.py           ← SQLAlchemy модели: User, Task, Category
│   ├── auth.py             ← JWT создание/проверка, Telegram webhook
│   ├── db.py               ← подключение к SQLite, миграции
│   └── config.py           ← серверные настройки (порт, секреты, пути)
│
├── build/
│   └── build.bat           ← скрипт сборки PyInstaller
│
└── docs/
    ├── ARCHITECTURE.md     ← подробная архитектура и решения
    ├── API.md              ← спецификация REST API
    └── FEATURES.md         ← полный список фич с приоритетами
```

## Ключевые решения

### Sidebar-поведение
- Окно `overrideredirect=True` (без рамки), `topmost=True`
- Позиционирование: правый край экрана, `x = screen_width - panel_width`
- Скрытое состояние: видна полоска 4px + иконка, остальное за экраном
- Выезд: анимация через `after()` с шагом 10px/16ms
- Win32: `SetWindowPos` с `HWND_TOPMOST` для поверх всех окон

### Синхронизация
- Optimistic UI: задачи сохраняются локально мгновенно, фоновый sync
- Конфликты: server wins (сервер — source of truth)
- Оффлайн: полноценная работа с локальным кешем, sync при восстановлении сети
- Формат: JSON через REST API

### Задачи
- Поля: id, text, done, priority (1-3), day (ISO date), position (порядок), category_id, created_at, updated_at
- Просроченные: задачи с done=false и day < today подсвечиваются красным
- Перенос: меняет day, сохраняет остальное
- Повторяющиеся: шаблон (template) с cron-подобным правилом, генерация при открытии недели

### Авторизация
- Первый запуск → ввод Telegram username → бот отправляет код → ввод кода → JWT
- JWT хранится в keyring (как пароль E-bot)
- Refresh token для бесшовного продления сессии

## Правила разработки
- Коммиты на русском, спрашивать перед пушем
- Не коммитить .env, секреты, keyring данные
- CustomTkinter стиль: минималистичный, как E-bot но элегантнее
- Один файл main.py для точки входа, вся логика в модулях client/
- Сервер деплоится на VPS отдельно от клиента

## Git
- GitHub: https://github.com/Heyyda/weekly-planner (private, создать при первом пуше)
- Ветка: main

## Сборка
```bash
pyinstaller --clean --onefile --windowed --icon=client/assets/icon.ico --add-data "client/assets/icon.ico;client/assets" --name "Личный Еженедельник" main.py
```

## Связанные проекты
- **E-bot** (`S:\Проекты\е-бот\`) — переиспользуем паттерны: авторизация через Telegram, автообновление, system tray, тёмная тема, keyring
- **VPS** (109.94.211.29) — сервер API будет рядом с device-manager.py
