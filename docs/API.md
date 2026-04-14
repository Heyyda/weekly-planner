# API Specification — Личный Еженедельник

Base URL: `https://heyda.ru/planner/api`
Port: 8100 (behind nginx proxy)

## Авторизация

Все эндпоинты (кроме auth/* и version) требуют заголовок:
```
Authorization: Bearer <jwt_token>
```

### POST /api/auth/request
Запросить код подтверждения через Telegram.
```json
// Request
{ "username": "nikita_tg" }

// Response 200
{ "status": "code_sent" }

// Response 404
{ "error": "user_not_found" }
```

### POST /api/auth/verify
```json
// Request
{ "username": "nikita_tg", "code": "123456" }

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user_id": "uuid",
  "username": "nikita_tg"
}
```

### POST /api/auth/refresh
```json
// Request
{ "refresh_token": "eyJ..." }

// Response 200
{ "access_token": "eyJ..." }
```

### GET /api/auth/me
```json
// Response 200
{ "user_id": "uuid", "username": "nikita_tg" }
```

## Задачи и недели

### GET /api/weeks/{week_start}
Получить неделю с задачами и заметками.
`week_start` — ISO date понедельника (например: `2026-04-13`).

```json
// Response 200
{
  "week_start": "2026-04-13",
  "days": [
    {
      "day": "2026-04-13",
      "tasks": [
        {
          "id": "uuid",
          "text": "Проверить остатки",
          "done": false,
          "priority": 1,
          "position": 0,
          "category_id": null,
          "created_at": "2026-04-13T09:00:00",
          "updated_at": "2026-04-13T09:00:00"
        }
      ],
      "notes": "Звонил поставщику"
    }
  ]
}
```

### POST /api/sync
Отправить пакет изменений и получить актуальное состояние.

```json
// Request
{
  "changes": [
    {
      "op": "create_task",
      "data": {
        "id": "uuid",
        "text": "Новая задача",
        "priority": 2,
        "day": "2026-04-14",
        "position": 0
      },
      "timestamp": "2026-04-14T10:30:00"
    },
    {
      "op": "update_task",
      "data": { "id": "uuid", "done": true },
      "timestamp": "2026-04-14T11:00:00"
    },
    {
      "op": "delete_task",
      "id": "uuid",
      "timestamp": "2026-04-14T11:05:00"
    },
    {
      "op": "update_notes",
      "data": { "day": "2026-04-14", "text": "Заметка" },
      "timestamp": "2026-04-14T12:00:00"
    }
  ]
}

// Response 200
{
  "applied": 4,
  "weeks": {
    "2026-04-13": { ... полная неделя ... }
  }
}
```

### GET /api/overdue
Все просроченные задачи (done=false, day < today).
```json
// Response 200
{
  "tasks": [
    { "id": "uuid", "text": "...", "day": "2026-04-10", "priority": 1 }
  ],
  "count": 3
}
```

## Категории

### GET /api/categories
```json
// Response 200
[
  { "id": "uuid", "name": "Закупки", "color": "#4a9eff" },
  { "id": "uuid", "name": "Клиенты", "color": "#ff4757" }
]
```

### POST /api/categories
```json
// Request
{ "name": "Внутреннее", "color": "#2ed573" }

// Response 201
{ "id": "uuid", "name": "Внутреннее", "color": "#2ed573" }
```

## Шаблоны

### GET /api/templates
```json
// Response 200
[
  {
    "id": "uuid",
    "text": "Проверить остатки",
    "priority": 2,
    "weekdays": [0, 2, 4]
  }
]
```

### POST /api/templates
```json
// Request
{ "text": "Еженедельный отчёт", "priority": 1, "weekdays": [4] }
```

## Обновления

### GET /api/version
```json
// Response 200
{
  "version": "0.2.0",
  "download_url": "https://heyda.ru/planner/download",
  "sha256": "abc123..."
}
```
