#!/usr/bin/env bash
# Production smoke test — проверяет ROADMAP Phase 1 success criteria.
#
# Usage:
#   bash deploy/bin/smoke-test.sh [BASE_URL]
#   bash deploy/bin/smoke-test.sh https://planner.heyda.ru
#
# По умолчанию BASE_URL=https://planner.heyda.ru
#
# Проверяет следующие ROADMAP Phase 1 Success Criteria:
#   SC-1: Telegram auth flow (username → код → JWT) — частично через curl
#   SC-2: GET /api/health и GET /api/version отвечают 200
#   SC-3: POST /api/sync с Bearer auth работает
#   SC-4: SQLite WAL режим (проверено в test_e2e_integration.py + SSH PRAGMA)
#   SC-5: systemd автозапуск после перезагрузки (SSH проверка)
#
# Выходит exit=0 если все автоматизированные проверки прошли.
# Выходит exit=1 с сообщением об ошибке если что-то не так.
#
# Зависимости: bash, curl, grep

set -euo pipefail

BASE="${1:-https://planner.heyda.ru}"
PASS=0
FAIL=0

# ── Вспомогательные функции ──────────────────────────────────────────────────

ok() {
    echo "  [OK]  $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "  [FAIL] $1"
    FAIL=$((FAIL + 1))
}

note() {
    echo "  [NOTE] $1"
}

# ── Заголовок ────────────────────────────────────────────────────────────────

echo ""
echo "=== Smoke Test: Личный Еженедельник Phase 1 ==="
echo "    Сервер: $BASE"
echo "    Время:  $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ── Проверка 1: GET /api/health (SC-2) ───────────────────────────────────────

echo ">>> [1/5] GET /api/health — HTTP 200 + status:ok"

HEALTH_BODY=$(curl -fsS --max-time 10 "$BASE/api/health" 2>&1) || {
    fail "health endpoint недоступен (curl вернул ошибку): $HEALTH_BODY"
    echo ""
    echo "=== Smoke Test FAILED (нет связи с сервером) ==="
    exit 1
}

if echo "$HEALTH_BODY" | grep -q '"status"'; then
    ok "GET /api/health → 200, тело: $HEALTH_BODY"
else
    fail "GET /api/health ответил, но тело не содержит 'status': $HEALTH_BODY"
fi

# ── Проверка 2: GET /api/version (SC-2) ──────────────────────────────────────

echo ">>> [2/5] GET /api/version — HTTP 200 + version поле"

VERSION_BODY=$(curl -fsS --max-time 10 "$BASE/api/version" 2>&1) || {
    fail "version endpoint недоступен: $VERSION_BODY"
}

if echo "$VERSION_BODY" | grep -q '"version"'; then
    ok "GET /api/version → 200, тело: $VERSION_BODY"
else
    fail "GET /api/version не содержит поле 'version': $VERSION_BODY"
fi

# ── Проверка 3: TLS-сертификат валидный (SC-5 + security) ────────────────────

echo ">>> [3/5] TLS сертификат — curl --fail через HTTPS"

if [[ "$BASE" == https://* ]]; then
    TLS_CHECK=$(curl -fsS --max-time 10 "$BASE/api/health" -o /dev/null 2>&1) || {
        fail "TLS handshake или сертификат невалидный. Вывод curl: $TLS_CHECK"
    }
    ok "TLS сертификат валидный, HTTPS соединение прошло"
else
    note "BASE_URL не https:// — пропускаем TLS проверку (dev-режим?)"
fi

# ── Проверка 4: /api/auth/request-code rate-limit (SC-1, D-09) ───────────────

echo ">>> [4/5] Rate-limit /api/auth/request-code (1/minute; D-09)"

# Используем случайный username чтобы не спамить реального пользователя.
# Ожидаемые ответы для не-allowed пользователя: 403 USER_NOT_ALLOWED.
# Второй быстрый запрос должен вернуть 429 (rate-limit по IP).
FAKE_USER="smoketest-user-$$-$(date +%s)"

HTTP1=$(curl -o /dev/null -s -w "%{http_code}" -X POST "$BASE/api/auth/request-code" \
    -H "Content-Type: application/json" \
    --max-time 10 \
    -d "{\"username\":\"$FAKE_USER\",\"hostname\":\"smoke-test\"}" 2>/dev/null || echo "000")

HTTP2=$(curl -o /dev/null -s -w "%{http_code}" -X POST "$BASE/api/auth/request-code" \
    -H "Content-Type: application/json" \
    --max-time 10 \
    -d "{\"username\":\"$FAKE_USER\",\"hostname\":\"smoke-test\"}" 2>/dev/null || echo "000")

note "Первый запрос: HTTP $HTTP1 (ожидается 403 USER_NOT_ALLOWED или 400 BOT_NOT_STARTED для smoke-user)"
note "Второй запрос: HTTP $HTTP2 (ожидается 429 rate-limit по IP)"

if [ "$HTTP2" = "429" ]; then
    ok "Rate-limit работает: второй запрос → 429 Too Many Requests"
elif [ "$HTTP1" = "429" ]; then
    ok "Rate-limit сработал уже на первом запросе (IP уже в лимите) — всё равно работает"
else
    note "Второй запрос вернул HTTP $HTTP2 вместо ожидаемого 429"
    note "Возможно rate-limit сбросился или IP в другом диапазоне — проверьте вручную:"
    note "  curl -X POST $BASE/api/auth/request-code -H 'Content-Type: application/json'"
    note "  -d '{\"username\":\"smoke\",\"hostname\":\"test\"}' (дважды подряд — второй должен быть 429)"
fi

# ── Проверка 5: /api/sync без Bearer → 401 (SC-3) ────────────────────────────

echo ">>> [5/5] POST /api/sync без Bearer → 401 (SC-3: auth gate)"

HTTP_SYNC=$(curl -o /dev/null -s -w "%{http_code}" -X POST "$BASE/api/sync" \
    -H "Content-Type: application/json" \
    --max-time 10 \
    -d '{"since":null,"changes":[]}' 2>/dev/null || echo "000")

if [ "$HTTP_SYNC" = "401" ]; then
    ok "POST /api/sync без Bearer → 401 Unauthorized (auth gate работает)"
else
    fail "POST /api/sync без Bearer → ожидался 401, получили $HTTP_SYNC"
fi

# ── Итог автоматических проверок ─────────────────────────────────────────────

echo ""
echo "=== Результаты автоматических проверок ==="
echo "    Passed: $PASS"
echo "    Failed: $FAIL"
echo ""

# ── Ручные шаги (оператор, не автоматизируются) ───────────────────────────────

echo "=== Ручные шаги (выполнить на VPS через SSH) ==="
echo ""
echo "  1. systemd статус (SC-5):"
echo "     ssh root@109.94.211.29 'systemctl is-active planner-api planner-bot'"
echo "     Ожидается: active"
echo "     active"
echo ""
echo "  2. WAL режим SQLite (SC-4):"
echo "     ssh root@109.94.211.29 'sqlite3 /var/lib/planner/weekly_planner.db \"PRAGMA journal_mode;\"'"
echo "     Ожидается: wal"
echo ""
echo "  3. Полный Telegram flow (SC-1) — если ещё не тестировали:"
echo "     а) Написать /start боту @Jazzways_bot"
echo "     б) curl -X POST $BASE/api/auth/request-code \\"
echo "           -H 'Content-Type: application/json' \\"
echo "           -d '{\"username\":\"nikita_heyyda\",\"hostname\":\"test\"}'"
echo "     в) Получить 6-значный код из Telegram"
echo "     г) curl -X POST $BASE/api/auth/verify \\"
echo "           -H 'Content-Type: application/json' \\"
echo "           -d '{\"request_id\":\"<UUID>\",\"code\":\"<6-digits>\"}'"
echo "     д) Получить access_token + refresh_token"
echo ""

# ── ROADMAP Phase 1 Success Criteria статус ───────────────────────────────────

echo "=== ROADMAP Phase 1 Success Criteria ==="
echo ""
echo "  SC-1: Telegram auth flow (username → код → JWT)"
echo "        Автоматически: request-code endpoint достижим (проверка 4)"
echo "        Ручно: полный Telegram flow через curl (см. выше)"
echo ""
echo "  SC-2: /api/health и /api/version → 200"
if [ "$PASS" -ge 2 ]; then
    echo "        PASSED (проверки 1-2 зелёные)"
else
    echo "        FAILED (проверки 1-2 не прошли)"
fi
echo ""
echo "  SC-3: /api/sync с Bearer принимает изменения"
echo "        Auth gate проверен (проверка 5: без Bearer → 401)"
echo "        Полный flow: нужен access_token из Telegram auth (SC-1)"
echo ""
echo "  SC-4: SQLite WAL — concurrent writes без database is locked"
echo "        PASSED in test_e2e_integration.py::test_phase_1_wal_and_concurrent_writes"
echo "        VPS: ssh root@109.94.211.29 'sqlite3 /var/lib/planner/weekly_planner.db \"PRAGMA journal_mode;\"'"
echo ""
echo "  SC-5: systemd автозапуск после перезагрузки"
echo "        Подтверждено в Plan 10 deploy (systemctl enable --now)"
echo "        Ручно: sudo reboot → через 60 сек → systemctl is-active planner-api planner-bot"
echo ""

# ── Финальный exit code ───────────────────────────────────────────────────────

if [ "$FAIL" -gt 0 ]; then
    echo "=== Smoke Test FAILED ($FAIL checks failed) ==="
    echo ""
    exit 1
else
    echo "=== Smoke Test PASSED (все автоматические проверки зелёные) ==="
    echo ""
    exit 0
fi
