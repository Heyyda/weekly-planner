#!/usr/bin/env bash
# bootstrap-vps.sh — Одноразовый setup VPS для Личного Еженедельника.
# Запускать как root. Идемпотентен — безопасно повторить.
#
# Использование:
#   ssh root@109.94.211.29
#   bash /opt/planner/deploy/bin/bootstrap-vps.sh
#
# После успешного выполнения — перейти к deploy/README.md STEP 2.

set -euo pipefail

echo "=== Личный Еженедельник: Bootstrap VPS ==="
echo "Дата: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# ---- Проверка что запущено от root ----
if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: Этот скрипт должен запускаться от root (sudo)." >&2
    exit 1
fi

# ---- Проверка Python >= 3.10 ----
echo "[1/7] Проверяю Python..."
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        PY_VER=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 10 ]]; then
            PYTHON_BIN="$candidate"
            echo "    Найден: $candidate ($PY_VER) — OK"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "    Python >= 3.10 не найден, устанавливаю python3.12..."
    apt-get update -qq
    apt-get install -y python3.12 python3.12-venv python3.12-distutils python3-pip
    PYTHON_BIN="python3.12"
fi

# ---- Установка системных пакетов ----
echo "[2/7] Устанавливаю системные пакеты..."
apt-get update -qq
apt-get install -y \
    "${PYTHON_BIN}" \
    "${PYTHON_BIN}-venv" \
    python3-pip \
    sqlite3 \
    git \
    curl \
    --no-install-recommends
echo "    Готово."

# ---- Создание пользователя planner ----
echo "[3/7] Создаю пользователя planner..."
if id "planner" &>/dev/null; then
    echo "    Пользователь planner уже существует — пропускаю."
else
    useradd -r -s /bin/bash -d /opt/planner -m planner
    echo "    Пользователь planner создан."
fi

# ---- Создание директорий ----
echo "[4/7] Создаю директории..."
mkdir -p /opt/planner
mkdir -p /var/lib/planner    # SQLite база данных (D-19)
mkdir -p /etc/planner        # Secrets (D-27)
mkdir -p /var/log/planner    # Опциональные логи

# Права
chown -R planner:planner /opt/planner /var/lib/planner /var/log/planner
chmod 700 /etc/planner       # Только root может читать secrets!
chmod 755 /opt/planner /var/lib/planner /var/log/planner
echo "    Готово: /opt/planner, /var/lib/planner, /etc/planner, /var/log/planner"

# ---- Cyrillic-safe проверка (CONTEXT.md Pitfall 11) ----
echo "[5/7] Проверяю поддержку Unicode путей..."
TEST_FILE="/var/lib/planner/.unicode_test_кириллица"
if touch "$TEST_FILE" 2>/dev/null && rm "$TEST_FILE"; then
    echo "    Unicode пути работают — OK"
else
    echo "    WARNING: Проблемы с Unicode в /var/lib/planner. Проверьте locale." >&2
    locale
fi

# ---- Обнаружение reverse proxy ----
echo "[6/7] Обнаруживаю reverse proxy..."
PROXY_TYPE="unknown"
if systemctl is-active --quiet caddy 2>/dev/null; then
    PROXY_TYPE="caddy"
    echo "    Обнаружен: Caddy (активен)"
elif systemctl is-active --quiet nginx 2>/dev/null; then
    PROXY_TYPE="nginx"
    echo "    Обнаружен: nginx (активен)"
elif command -v caddy &>/dev/null; then
    PROXY_TYPE="caddy"
    echo "    Обнаружен: caddy (установлен, но не активен)"
elif command -v nginx &>/dev/null; then
    PROXY_TYPE="nginx"
    echo "    Обнаружен: nginx (установлен, но не активен)"
else
    echo "    WARNING: Ни Caddy, ни nginx не обнаружены. Настройте reverse-proxy вручную." >&2
fi

# ---- Установка systemd units ----
echo "[7/7] Устанавливаю systemd units..."
if [[ -f /opt/planner/deploy/planner-api.service ]]; then
    cp /opt/planner/deploy/planner-api.service /etc/systemd/system/
    cp /opt/planner/deploy/planner-bot.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable planner-api planner-bot
    echo "    Units установлены и включены в автозапуск."
else
    echo "    Репозиторий ещё не склонирован в /opt/planner. Units установятся в deploy.sh."
fi

# ---- Итоговые инструкции ----
echo ""
echo "=== Bootstrap завершён! ==="
echo ""
echo "Следующие шаги (deploy/README.md):"
echo ""
echo "  STEP 0 (если ещё не сделано):"
echo "    Откройте @BotFather в Telegram → /revoke → @Jazzways_bot → сохраните НОВЫЙ токен"
echo ""
echo "  STEP 2: Генерируйте JWT секреты:"
echo "    openssl rand -hex 32  # для JWT_SECRET"
echo "    openssl rand -hex 32  # для JWT_REFRESH_SECRET"
echo ""
echo "  STEP 3: Создайте /etc/planner/planner.env:"
echo "    cp /opt/planner/server/.env.example /etc/planner/planner.env"
echo "    nano /etc/planner/planner.env  # заполните реальные значения"
echo "    chmod 600 /etc/planner/planner.env"
echo ""
if [[ "$PROXY_TYPE" == "caddy" ]]; then
    echo "  STEP 6 (Caddy обнаружен):"
    echo "    Добавьте содержимое deploy/planner-Caddyfile.snippet в /etc/caddy/Caddyfile"
    echo "    systemctl reload caddy"
elif [[ "$PROXY_TYPE" == "nginx" ]]; then
    echo "  STEP 6 (nginx обнаружен):"
    echo "    cp /opt/planner/deploy/planner-nginx.snippet /etc/nginx/sites-available/planner.heyda.ru"
    echo "    ln -sf /etc/nginx/sites-available/planner.heyda.ru /etc/nginx/sites-enabled/"
    echo "    certbot --nginx -d planner.heyda.ru"
    echo "    systemctl reload nginx"
fi
echo ""
echo "  Полный runbook: /opt/planner/deploy/README.md"
