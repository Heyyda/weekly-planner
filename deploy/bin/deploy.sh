#!/usr/bin/env bash
# deploy.sh — Повторяемый скрипт деплоя (git pull + venv + migrate + reload).
# Запускать от пользователя planner на VPS после первоначального bootstrap-vps.sh.
#
# Использование:
#   ssh planner@109.94.211.29
#   bash /opt/planner/deploy/bin/deploy.sh
#
# Или через sudo с рабочего PC:
#   ssh root@109.94.211.29 "sudo -u planner bash /opt/planner/deploy/bin/deploy.sh"

set -euo pipefail

PLANNER_DIR="/opt/planner"
VENV_DIR="${PLANNER_DIR}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"
ALEMBIC_BIN="${VENV_DIR}/bin/alembic"
API_URL="http://127.0.0.1:8100"

echo "=== Личный Еженедельник: Deploy ==="
echo "Дата: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Пользователь: $(id -un)"
echo ""

# ---- Проверка что мы в нужной директории ----
if [[ ! -d "${PLANNER_DIR}/.git" ]]; then
    echo "ERROR: ${PLANNER_DIR} — не git репозиторий. Выполните STEP 4 из README.md" >&2
    exit 1
fi

# ---- Проверка Python >= 3.10 ----
echo "[1/6] Проверяю Python в venv..."
if [[ ! -f "${PYTHON_BIN}" ]]; then
    echo "    venv не существует, создаю..."
    # Найти системный python >= 3.10
    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            PY_VER=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 10 ]]; then
                "$candidate" -m venv "${VENV_DIR}"
                echo "    venv создан с $candidate ($PY_VER)"
                break
            fi
        fi
    done
    if [[ ! -f "${PYTHON_BIN}" ]]; then
        echo "ERROR: Python >= 3.10 не найден. Установите python3.12." >&2
        exit 1
    fi
else
    PY_VER=$("${PYTHON_BIN}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "    ${PYTHON_BIN} ($PY_VER) — OK"
fi

# ---- Git pull ----
echo "[2/6] Обновляю код из git..."
cd "${PLANNER_DIR}"
git fetch origin main
git reset --hard origin/main
echo "    Commit: $(git log -1 --format='%h %s')"

# ---- Установка зависимостей ----
echo "[3/6] Устанавливаю Python зависимости..."
"${PIP_BIN}" install --quiet --upgrade pip
"${PIP_BIN}" install --quiet -r server/requirements.txt
echo "    Зависимости установлены."

# ---- Alembic миграции ----
echo "[4/6] Применяю Alembic миграции..."
cd "${PLANNER_DIR}/server"
"${ALEMBIC_BIN}" upgrade head
echo "    Миграции применены."
cd "${PLANNER_DIR}"

# ---- Перезапуск systemd units ----
echo "[5/6] Перезапускаю systemd units..."
# Требует sudo (planner user добавлен в sudoers для этих команд)
sudo systemctl restart planner-api planner-bot
echo "    planner-api и planner-bot перезапущены."

# ---- Smoke test ----
echo "[6/6] Smoke test /api/health..."
sleep 5
if curl -fsS "${API_URL}/api/health" --max-time 10 > /dev/null; then
    HEALTH=$(curl -s "${API_URL}/api/health")
    echo "    OK: ${HEALTH}"
else
    echo "ERROR: /api/health не ответил после перезапуска!" >&2
    echo "    Логи planner-api:"
    journalctl -u planner-api --no-pager -n 30 >&2
    exit 1
fi

echo ""
echo "=== Deploy завершён успешно! ==="
echo ""
echo "Для проверки через TLS:"
echo "    curl -fsS https://planner.heyda.ru/api/health"
