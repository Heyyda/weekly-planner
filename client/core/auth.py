"""
AuthManager — Telegram-авторизация клиента + хранение JWT.

Контракт сервера (server/api/auth_routes.py — Phase 1 production):
    POST /api/auth/request-code → {request_id, expires_in}
    POST /api/auth/verify       → {access_token, refresh_token, expires_in, user_id, token_type}
    POST /api/auth/refresh      → {access_token, refresh_token, expires_in, token_type}  # D-13 rotation
    POST /api/auth/logout       → 204 (Bearer required)
    GET  /api/auth/me           → {user_id, username, created_at} (Bearer required)

Хранение токенов (D-26):
    access_token  — только в RAM (TTL 15 минут)
    refresh_token — keyring (KEYRING_SERVICE='WeeklyPlanner', D-25)
    username      — keyring (для повторного логина)

Thread safety: get_access_token() и bearer_header() читают/пишут self.access_token
под self._lock — безопасно для вызова из sync daemon thread.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

import keyring
import requests

from client.core import config

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Базовая ошибка авторизации."""


class AuthNetworkError(AuthError):
    """Сетевая ошибка (offline / timeout / connection refused)."""


class AuthRateLimitError(AuthError):
    """Сервер вернул 429 — слишком много запросов /request-code."""


class AuthInvalidCodeError(AuthError):
    """Код неверный, истёк или уже использован (400)."""


class AuthExpiredError(AuthError):
    """Refresh token недействителен (401) — нужен новый Telegram-код."""


class AuthManager:
    """JWT-авторизация + keyring storage. См. CONTEXT.md D-25, D-26."""

    def __init__(self) -> None:
        self._api_base: str = config.API_BASE
        self._lock = threading.Lock()
        self.access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self.username: Optional[str] = None
        self._user_id: Optional[str] = None
        self._session = requests.Session()

    def is_authenticated(self) -> bool:
        with self._lock:
            return self.access_token is not None

    def get_access_token(self) -> Optional[str]:
        with self._lock:
            return self.access_token

    def bearer_header(self) -> dict:
        with self._lock:
            if self.access_token is None:
                raise AuthError("Не авторизован — нет access_token в RAM")
            return {"Authorization": f"Bearer {self.access_token}"}

    @property
    def user_id(self) -> Optional[str]:
        return self._user_id

    def request_code(self, username: str, hostname: str = "неизвестно") -> str:
        url = f"{self._api_base}/auth/request-code"
        try:
            resp = self._session.post(
                url,
                json={"username": username, "hostname": hostname},
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("request_code network error: %s", exc)
            raise AuthNetworkError(f"Не удалось связаться с сервером: {exc}") from exc

        if resp.status_code == 429:
            logger.warning("request_code rate-limited (429)")
            raise AuthRateLimitError("Слишком много попыток. Подождите минуту.")
        if resp.status_code != 200:
            msg = self._extract_error_message(resp)
            logger.error("request_code HTTP %d: %s", resp.status_code, msg)
            raise AuthError(msg or f"Ошибка сервера (HTTP {resp.status_code})")

        data = resp.json()
        request_id = data.get("request_id")
        if not request_id:
            raise AuthError("Ответ сервера без request_id")
        with self._lock:
            self.username = username
        logger.info("request_code OK для username=%s, expires_in=%s",
                    username, data.get("expires_in"))
        return request_id

    def verify_code(self, request_id: str, code: str,
                    device_name: Optional[str] = None) -> bool:
        url = f"{self._api_base}/auth/verify"
        try:
            resp = self._session.post(
                url,
                json={
                    "request_id": request_id,
                    "code": code,
                    "device_name": device_name,
                },
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("verify_code network error: %s", exc)
            raise AuthNetworkError(f"Не удалось связаться с сервером: {exc}") from exc

        if resp.status_code == 400:
            msg = self._extract_error_message(resp)
            logger.warning("verify_code 400: %s", msg)
            raise AuthInvalidCodeError(msg or "Неверный или истёкший код")
        if resp.status_code != 200:
            logger.error("verify_code HTTP %d", resp.status_code)
            raise AuthError(f"Ошибка сервера (HTTP {resp.status_code})")

        data = resp.json()
        with self._lock:
            self.access_token = data["access_token"]
            self._refresh_token = data["refresh_token"]
            self._user_id = data.get("user_id")

        self._save_refresh_to_keyring()
        logger.info("verify_code OK, user_id=%s", self._user_id)
        return True

    def refresh_access(self) -> bool:
        with self._lock:
            refresh = self._refresh_token

        if not refresh:
            logger.debug("refresh_access: нет refresh_token")
            return False

        url = f"{self._api_base}/auth/refresh"
        try:
            resp = self._session.post(
                url,
                json={"refresh_token": refresh},
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("refresh_access network error: %s", exc)
            return False

        if resp.status_code == 401:
            logger.warning("refresh_access 401 — нужен новый Telegram-код")
            with self._lock:
                self.access_token = None
                self._refresh_token = None
            raise AuthExpiredError("Сессия истекла — нужен повторный логин")

        if resp.status_code != 200:
            logger.error("refresh_access HTTP %d", resp.status_code)
            return False

        data = resp.json()
        new_access = data.get("access_token")
        new_refresh = data.get("refresh_token")
        if not new_access:
            logger.error("refresh_access: ответ без access_token")
            return False

        with self._lock:
            self.access_token = new_access
            if new_refresh:
                self._refresh_token = new_refresh

        if new_refresh:
            self._save_refresh_to_keyring()
        logger.info("refresh_access OK (rotation: %s)", bool(new_refresh))
        return True

    def load_saved_token(self) -> bool:
        try:
            refresh = keyring.get_password(config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY)
            username = keyring.get_password(config.KEYRING_SERVICE, config.KEYRING_USERNAME_KEY)
        except Exception as exc:
            logger.error("Keyring read error: %s", exc)
            return False

        if not refresh:
            logger.debug("load_saved_token: keyring пустой")
            return False

        with self._lock:
            self._refresh_token = refresh
            self.username = username

        try:
            return self.refresh_access()
        except AuthExpiredError:
            logger.info("load_saved_token: refresh expired, нужен новый код")
            return False

    def logout(self) -> None:
        try:
            if self.access_token:
                self._session.post(
                    f"{self._api_base}/auth/logout",
                    json={"refresh_token": self._refresh_token} if self._refresh_token else None,
                    headers=self.bearer_header(),
                    timeout=config.HTTP_TIMEOUT_SECONDS,
                )
        except (requests.exceptions.RequestException, AuthError) as exc:
            logger.warning("logout network error (игнорируем): %s", exc)

        for key in (config.KEYRING_REFRESH_KEY, config.KEYRING_USERNAME_KEY):
            try:
                keyring.delete_password(config.KEYRING_SERVICE, key)
            except Exception as exc:
                logger.debug("logout keyring delete %s: %s", key, exc)

        with self._lock:
            self.access_token = None
            self._refresh_token = None
            self.username = None
            self._user_id = None
        logger.info("logout OK")

    def _save_refresh_to_keyring(self) -> None:
        try:
            if self._refresh_token:
                keyring.set_password(
                    config.KEYRING_SERVICE,
                    config.KEYRING_REFRESH_KEY,
                    self._refresh_token,
                )
            if self.username:
                keyring.set_password(
                    config.KEYRING_SERVICE,
                    config.KEYRING_USERNAME_KEY,
                    self.username,
                )
        except Exception as exc:
            logger.error("Keyring write error: %s", exc)

    @staticmethod
    def _extract_error_message(resp: requests.Response) -> str:
        try:
            payload = resp.json()
            err = payload.get("error", {})
            return err.get("message", "")
        except (ValueError, AttributeError):
            return ""
