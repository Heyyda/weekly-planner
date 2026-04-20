# Deploy Runbook — Личный Еженедельник

Пошаговая инструкция для первого деплоя на VPS 109.94.211.29.

**Время выполнения:** ~30-40 минут (включая DNS propagation)

---

## STEP 0 (КРИТИЧНО, ОБЯЗАТЕЛЬНО ПЕРВЫМ): Ревокнуть Bot Token

> Старый токен `@Jazzways_bot` был скомпрометирован — попал в чат 2026-04-14.
> До деплоя нужно получить НОВЫЙ токен. Без этого шага деплоить нельзя.

1. Откройте Telegram
2. Найдите `@BotFather`
3. Отправьте команду `/revoke`
4. BotFather спросит выбрать бота — выберите `@Jazzways_bot`
5. Подтвердите отзыв токена
6. BotFather пришлёт НОВЫЙ токен вида `123456789:ABCdef...`
7. **Сохраните новый токен** — он понадобится в STEP 3

---

## STEP 1: SSH на VPS и запуск bootstrap

```bash
# С локальной машины
ssh root@109.94.211.29

# На VPS — клонируем репозиторий (если ещё не склонирован)
git clone https://github.com/Heyyda/weekly-planner /opt/planner

# Запускаем one-shot setup скрипт
bash /opt/planner/deploy/bin/bootstrap-vps.sh
```

Скрипт создаст:
- Пользователя `planner`
- Директории `/opt/planner`, `/var/lib/planner`, `/etc/planner`, `/var/log/planner`
- Установит Python 3.12, sqlite3, git
- Определит тип reverse proxy (Caddy или nginx)
- Установит и включит systemd units

---

## STEP 2: Генерация JWT секретов

```bash
# На VPS, как root
echo "JWT_SECRET:"
openssl rand -hex 32

echo "JWT_REFRESH_SECRET (другой, не тот же!):"
openssl rand -hex 32
```

Скопируйте оба значения — они понадобятся в STEP 3.

---

## STEP 3: Создание файла секретов на VPS

```bash
# На VPS, как root
cp /opt/planner/server/.env.example /etc/planner/planner.env
nano /etc/planner/planner.env
```

Заполните все обязательные переменные:
```env
BOT_TOKEN=<новый токен из STEP 0>
JWT_SECRET=<первое значение из STEP 2>
JWT_REFRESH_SECRET=<второе значение из STEP 2>
DATABASE_URL=sqlite+aiosqlite:////var/lib/planner/weekly_planner.db
ALLOWED_USERNAMES=nikita_heyyda
```

Установите права (файл содержит секреты!):
```bash
chmod 600 /etc/planner/planner.env
chown root:planner /etc/planner/planner.env
```

---

## STEP 4: Настройка репозитория и venv

```bash
# Убедитесь что репозиторий на месте
ls /opt/planner/server/

# Устанавливаем права
chown -R planner:planner /opt/planner

# Создаём venv от имени planner
sudo -u planner python3.12 -m venv /opt/planner/venv

# Устанавливаем зависимости
sudo -u planner /opt/planner/venv/bin/pip install --upgrade pip
sudo -u planner /opt/planner/venv/bin/pip install -r /opt/planner/server/requirements.txt
```

---

## STEP 5: Настройка DNS

Создайте A-запись в DNS-провайдере:
```
Type: A
Name: planner
Domain: heyda.ru
Value: 109.94.211.29
TTL: 300 (или минимум)
```

После создания проверьте propagation (может занять до 5-10 минут):
```bash
# На VPS или локально
dig planner.heyda.ru +short
# Должен вернуть: 109.94.211.29
```

---

## STEP 6: Настройка reverse proxy

Определите какой proxy используется (bootstrap-vps.sh уже определил — смотрите вывод):

### Вариант A: Caddy (рекомендуется если уже установлен)

```bash
# Проверяем что Caddy активен
systemctl status caddy

# Добавляем блок в Caddyfile
cat /opt/planner/deploy/planner-Caddyfile.snippet
# Скопируйте содержимое и добавьте в /etc/caddy/Caddyfile

nano /etc/caddy/Caddyfile
# Добавьте содержимое planner-Caddyfile.snippet в конец файла

# Перезагружаем Caddy (Caddy сам получит TLS сертификат от Let's Encrypt)
systemctl reload caddy

# Проверяем
journalctl -u caddy -n 20
```

### Вариант B: nginx

```bash
# Проверяем что nginx активен
systemctl status nginx

# Копируем конфиг
cp /opt/planner/deploy/planner-nginx.snippet /etc/nginx/sites-available/planner.heyda.ru

# Создаём символическую ссылку
ln -sf /etc/nginx/sites-available/planner.heyda.ru /etc/nginx/sites-enabled/

# Проверяем конфиг
nginx -t

# Получаем TLS сертификат через certbot
certbot --nginx -d planner.heyda.ru

# Перезагружаем nginx
systemctl reload nginx
```

---

## STEP 7: Применение Alembic миграций

```bash
# Как пользователь planner
cd /opt/planner/server
sudo -u planner /opt/planner/venv/bin/alembic upgrade head
```

Ожидаемый вывод:
```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> <hash>, initial schema
```

---

## STEP 8: Запуск systemd units

```bash
# Устанавливаем units (если bootstrap-vps.sh не сделал это автоматически)
cp /opt/planner/deploy/planner-api.service /etc/systemd/system/
cp /opt/planner/deploy/planner-bot.service /etc/systemd/system/
systemctl daemon-reload

# Включаем и запускаем
systemctl enable --now planner-api planner-bot

# Проверяем статус
systemctl status planner-api
systemctl status planner-bot
```

Ожидаемый вывод статуса:
```
● planner-api.service - Личный Еженедельник API (FastAPI)
   Active: active (running) since ...
```

Если есть ошибки:
```bash
journalctl -u planner-api -n 50
journalctl -u planner-bot -n 50
```

---

## STEP 9: Базовая проверка (HTTP → backend)

Сначала проверяем локально (без TLS):
```bash
# Прямой запрос к backend (на VPS)
curl -fsS http://127.0.0.1:8100/api/health
# Ожидается: {"status":"ok","version":"0.1.0"}

# Через reverse proxy с TLS (потребует DNS propagation из STEP 5)
curl -fsS https://planner.heyda.ru/api/health
# Ожидается: {"status":"ok","version":"0.1.0"}
```

Если `https://` не работает — проверьте DNS и TLS сертификат:
```bash
# Проверка DNS
dig planner.heyda.ru

# Для Caddy — проверьте получение сертификата
journalctl -u caddy -n 30

# Для nginx — проверьте certbot
certbot certificates
```

---

## STEP 10: Проверка Telegram бота

1. Откройте Telegram
2. Найдите `@Jazzways_bot`
3. Отправьте `/start`
4. Бот должен ответить приветственным сообщением

Если нет ответа:
```bash
# Проверяем что бот запущен
systemctl status planner-bot

# Логи бота
journalctl -u planner-bot -n 30
```

---

## STEP 11: Полный тест авторизации

```bash
# Тест 1: Запрос кода авторизации
curl -X POST https://planner.heyda.ru/api/auth/request-code \
  -H 'Content-Type: application/json' \
  -d '{"username":"nikita_heyyda","hostname":"test-deploy"}'
# Ожидается: {"request_id":"...", "expires_in":300}
# Бот должен прислать 6-значный код в Telegram!

# Тест 2: Проверка кода (замените CODE на полученный код)
CODE="123456"
REQUEST_ID="<request_id из предыдущего ответа>"
curl -X POST https://planner.heyda.ru/api/auth/verify \
  -H 'Content-Type: application/json' \
  -d "{\"request_id\":\"${REQUEST_ID}\",\"code\":\"${CODE}\"}"
# Ожидается: {"access_token":"...", "refresh_token":"...", ...}

echo "=== Deploy полностью завершён! ==="
```

---

## Troubleshooting

### planner-api не запускается

```bash
# Полные логи
journalctl -u planner-api -n 100 --no-pager

# Частые причины:
# 1. Неверная DATABASE_URL в planner.env
# 2. Нет прав на /var/lib/planner
# 3. Alembic миграции не применены
# 4. JWT_SECRET короче 32 символов

# Проверка файла env
cat /etc/planner/planner.env | grep -v '^#' | grep -v '^$'
```

### planner-bot не запускается

```bash
journalctl -u planner-bot -n 100 --no-pager

# Частые причины:
# 1. Неверный BOT_TOKEN (старый скомпрометированный токен)
# 2. Telegram API недоступен с VPS
# 3. Конфликт — другой процесс уже polling этот бот

# Проверка Telegram API
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
```

### 502 Bad Gateway через reverse proxy

```bash
# Убедитесь что backend слушает
curl http://127.0.0.1:8100/api/health

# Проверьте порт
ss -tlnp | grep 8100
```

---

## Обновление (повторный деплой)

После первоначального deploy — для обновлений используйте `deploy.sh`:

```bash
ssh planner@109.94.211.29
bash /opt/planner/deploy/bin/deploy.sh
```

Скрипт выполнит: `git pull` → `pip install` → `alembic upgrade head` → `systemctl restart` → smoke test.

---

## Мониторинг

```bash
# Статус обоих сервисов
systemctl status planner-api planner-bot

# Живые логи API
journalctl -u planner-api -f

# Живые логи бота
journalctl -u planner-bot -f

# Последние 100 строк обоих
journalctl -u planner-api -u planner-bot -n 100 --no-pager
```
