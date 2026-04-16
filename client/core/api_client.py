"""
SyncApiClient — обёртка для POST /api/sync с auth + backoff + retry.

Назначение: спрятать HTTP-детали от SyncManager. SyncManager не должен знать
про requests, headers, JSON-сериализацию или 401 retry. Он работает в терминах
ApiResult (ok/error_kind) и вызывает retry через свой _sync_loop.

Backoff state хранится здесь (счётчик _consecutive_errors + _current_backoff).
SyncManager читает .current_backoff чтобы знать сколько ждать перед следующим
циклом.

Правила retry (D-13, D-14):
  - 200 → ApiResult.success + сброс backoff
  - 401 → refresh_access() один раз → retry один раз → если снова 401 → auth_expired()
  - 5xx / network → ApiResult.server/network_error + увеличить backoff (cap 60s)
  - 4xx (не 401) → ApiResult.client_error (нет смысла ретраить)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from client.core import config
from client.core.auth import AuthError, AuthExpiredError, AuthManager
from client.core.models import TaskChange

logger = logging.getLogger(__name__)


@dataclass
class ApiResult:
    """
    Результат HTTP-вызова. Никогда не raise — SyncManager инспектирует поля.

    error_kind:
      "network"     — ConnectionError / Timeout (retry через backoff)
      "server"      — 5xx (retry через backoff)
      "client"      — 4xx кроме 401 (баг клиента, retry бесполезен)
      "auth"        — 401 (внутренний — после retry refresh_access выполняется)
      "auth_expired" — refresh истёк / не удался, нужен Telegram-код
    """
    ok: bool
    status: int = 0
    payload: Optional[dict] = None
    error_kind: Optional[str] = None         # "network" | "server" | "client" | "auth_expired"
    message: Optional[str] = None
    retry_after: Optional[float] = None      # секунд до следующей попытки

    @classmethod
    def success(cls, payload: dict, status: int = 200) -> "ApiResult":
        """Успешный ответ (200)."""
        return cls(ok=True, status=status, payload=payload)

    @classmethod
    def network_error(cls, exc: Exception, retry_after: float) -> "ApiResult":
        """ConnectionError / Timeout — retry через backoff."""
        return cls(
            ok=False,
            status=0,
            error_kind="network",
            message=f"Сетевая ошибка: {exc}",
            retry_after=retry_after,
        )

    @classmethod
    def server_error(cls, status: int, retry_after: float, message: str = "") -> "ApiResult":
        """5xx от сервера — retry через backoff."""
        return cls(
            ok=False,
            status=status,
            error_kind="server",
            message=message or f"Сервер вернул {status}",
            retry_after=retry_after,
        )

    @classmethod
    def client_error(cls, status: int, message: str = "") -> "ApiResult":
        """4xx (не 401) — баг на клиенте, retry бесполезен."""
        return cls(
            ok=False,
            status=status,
            error_kind="client",
            message=message or f"Ошибка клиента {status}",
        )

    @classmethod
    def auth_expired(cls) -> "ApiResult":
        """Refresh не сработал — нужен повторный Telegram-код."""
        return cls(
            ok=False,
            status=401,
            error_kind="auth_expired",
            message="Сессия истекла — нужен повторный логин",
        )


class SyncApiClient:
    """
    Authenticated HTTP-клиент для POST /api/sync.

    Инкапсулирует:
      - инъекцию Bearer токена через AuthManager.bearer_header()
      - 401 retry: при первом 401 вызывает auth.refresh_access() и делает один повтор
      - exponential backoff: счётчик + cap BACKOFF_CAP (D-13)
      - маппинг ошибок в типизированный ApiResult

    Никогда не raise — любая ошибка возвращается в ApiResult.
    SyncManager читает result.ok / result.error_kind для управления sync-циклом.
    """

    def __init__(self, auth_manager: AuthManager) -> None:
        self._auth = auth_manager
        self._api_base = config.API_BASE
        self._session = requests.Session()
        self._consecutive_errors: int = 0
        self._current_backoff: float = config.BACKOFF_BASE

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    @property
    def current_backoff(self) -> float:
        """
        Текущий backoff delay (секунды) для SyncManager._sync_loop.

        SyncManager вызывает: self._wake_event.wait(timeout=client.current_backoff)
        """
        return self._current_backoff

    @property
    def consecutive_errors(self) -> int:
        """Количество последовательных ошибок — для диагностики/логов."""
        return self._consecutive_errors

    def reset_backoff(self) -> None:
        """
        Сбросить backoff в начальное состояние.
        Обычно вызывается автоматически при успешном post_sync().
        """
        self._consecutive_errors = 0
        self._current_backoff = config.BACKOFF_BASE

    def post_sync(
        self,
        since: Optional[str],
        changes: list[TaskChange],
    ) -> ApiResult:
        """
        POST /api/sync с auth + 401 retry.

        Args:
            since: ISO-строка last_sync_at | None (для full resync, D-19)
            changes: список TaskChange — сериализуется через .to_wire()

        Returns:
            ApiResult(ok=True, payload={"server_timestamp": ..., "changes": [...]})
            или ApiResult(ok=False, error_kind=..., retry_after=...)

        Никогда не raise (offline-tolerant).
        """
        wire_changes = [c.to_wire() for c in changes]
        payload = {"since": since, "changes": wire_changes}

        # Первая попытка
        result = self._do_post_sync(payload)

        if result.status != 401:
            return result

        # 401 → пробуем refresh + retry один раз
        logger.info("post_sync: 401 — пробуем refresh access_token")
        try:
            refreshed = self._auth.refresh_access()
        except AuthExpiredError:
            logger.warning("post_sync: refresh expired — нужен повторный логин")
            return ApiResult.auth_expired()

        if not refreshed:
            # Сетевая ошибка в refresh — ретраим через backoff на следующем цикле
            logger.warning("post_sync: refresh не удался (offline?) — backoff")
            retry_after = self._bump_backoff()
            return ApiResult.server_error(401, retry_after, "Refresh не удался")

        # Refresh OK — повторяем POST один раз с новым токеном
        logger.info("post_sync: refresh OK — повторный запрос с новым токеном")
        return self._do_post_sync(payload)

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _do_post_sync(self, payload: dict) -> ApiResult:
        """
        Внутренний: один HTTP POST без retry-логики.

        Управляет backoff: bump на network/5xx, reset на 200.
        При 401 — возвращает сырой ApiResult(status=401) для обработки в post_sync().
        """
        url = f"{self._api_base}/sync"

        # Получаем Bearer токен — может raise AuthError если нет access_token
        try:
            headers = self._auth.bearer_header()
        except AuthError:
            logger.error("_do_post_sync: нет access_token — bearer_header raised AuthError")
            return ApiResult.auth_expired()

        # HTTP запрос
        try:
            resp = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as exc:
            retry_after = self._bump_backoff()
            logger.error(
                "post_sync: сетевая ошибка (backoff %.1fs): %s",
                retry_after, exc,
            )
            return ApiResult.network_error(exc, retry_after)

        # Обработка статус кодов
        if resp.status_code == 200:
            self.reset_backoff()
            try:
                body = resp.json()
            except ValueError as exc:
                # 200 но тело не JSON — серверный баг
                logger.error("post_sync: 200 но JSON не парсится: %s", exc)
                retry_after = self._bump_backoff()
                return ApiResult.server_error(200, retry_after, "Invalid JSON response")
            return ApiResult.success(body)

        if resp.status_code == 401:
            # НЕ bump_backoff здесь — refresh + retry обрабатывается в post_sync()
            logger.debug("_do_post_sync: 401 (будет обработан refresh-retry в post_sync)")
            return ApiResult(ok=False, status=401, error_kind="auth", message="401 Unauthorized")

        if 500 <= resp.status_code < 600:
            retry_after = self._bump_backoff()
            logger.error(
                "post_sync: 5xx %d (backoff %.1fs): %s",
                resp.status_code, retry_after, resp.text[:100],
            )
            return ApiResult.server_error(resp.status_code, retry_after)

        # 4xx (кроме 401) — клиентская ошибка, ретраить бессмысленно
        logger.error("post_sync: 4xx %d: %s", resp.status_code, resp.text[:200])
        return ApiResult.client_error(resp.status_code, resp.text[:200])

    def _bump_backoff(self) -> float:
        """
        Удвоить backoff delay (cap BACKOFF_CAP, D-13).

        Возвращает новое значение для использования в retry_after.
        """
        self._consecutive_errors += 1
        self._current_backoff = min(self._current_backoff * 2, config.BACKOFF_CAP)
        return self._current_backoff
