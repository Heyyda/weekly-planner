---
status: partial
phase: 01-server-auth
source: [01-VERIFICATION.md]
started: 2026-04-16
updated: 2026-04-16
---

## Current Test

[awaiting human testing — non-blocking, deferred to natural verification points]

## Tests

### 1. Real Telegram code delivery (SC-1)

**expected:** User sends `/start` to @Jazzways_bot; bot replies with welcome. User POSTs to `/api/auth/request-code` with their username; within seconds, a 6-digit code arrives in the bot chat with the D-05 formatted message. User POSTs to `/api/auth/verify` with request_id + code; receives valid access+refresh JWT pair. Subsequent `GET /api/auth/me` with Bearer returns user info.

**result:** pending

**self-verification path:** будет выполнено естественно в Phase 2-3 когда desktop-клиент впервые авторизуется. Если сломается — начнём gap-closure на Phase 1 тогда.

### 2. VPS reboot survival (SC-5)

**expected:** `sudo reboot` on VPS 109.94.211.29. After ~60 seconds, `systemctl is-active planner-api planner-bot` returns `active active`. `curl https://planner.heyda.ru/api/health` returns 200.

**result:** pending

**self-verification path:** при следующем плановом обслуживании VPS (перезагрузке по любой причине). `Restart=always` + `WantedBy=multi-user.target` сконфигурированы — reboot-survival логически гарантирован, но не проверен эмпирически.

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

(none — both items are soft-verification deferrals, not implementation gaps)
