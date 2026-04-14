"""
Авторизация через Telegram (как в E-bot).

Поток:
1. Пользователь вводит Telegram username
2. Клиент отправляет POST /api/auth/request {username}
3. Telegram бот отправляет пользователю код подтверждения
4. Пользователь вводит код в приложении
5. Клиент отправляет POST /api/auth/verify {username, code}
6. Сервер возвращает JWT token
7. Клиент сохраняет JWT в keyring

JWT refresh:
- Access token: 7 дней
- Refresh token: 30 дней
- При 401 — автоматический refresh, если не удалось — показать экран логина
"""

import keyring
import requests
from typing import Optional


SERVICE_NAME = "ЛичныйЕженедельник"
API_BASE = "https://heyda.ru/planner/api"  # TODO: финализировать


class AuthManager:
    """Управление авторизацией."""

    def __init__(self):
        self.jwt_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.username: Optional[str] = None

    def load_saved_token(self) -> bool:
        """Загрузить JWT из keyring. Возвращает True если токен валиден."""
        try:
            self.jwt_token = keyring.get_password(SERVICE_NAME, "jwt")
            self.refresh_token = keyring.get_password(SERVICE_NAME, "refresh")
            self.username = keyring.get_password(SERVICE_NAME, "username")
            if self.jwt_token:
                return self._validate_token()
        except Exception:
            pass
        return False

    def request_code(self, username: str) -> bool:
        """Запросить код подтверждения через Telegram."""
        try:
            resp = requests.post(
                f"{API_BASE}/auth/request",
                json={"username": username},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def verify_code(self, username: str, code: str) -> bool:
        """Подтвердить код и получить JWT."""
        try:
            resp = requests.post(
                f"{API_BASE}/auth/verify",
                json={"username": username, "code": code},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.jwt_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.username = username
                self._save_tokens()
                return True
        except requests.RequestException:
            pass
        return False

    def logout(self):
        """Выход: удалить токены."""
        keyring.delete_password(SERVICE_NAME, "jwt")
        keyring.delete_password(SERVICE_NAME, "refresh")
        keyring.delete_password(SERVICE_NAME, "username")
        self.jwt_token = None
        self.refresh_token = None
        self.username = None

    def _validate_token(self) -> bool:
        """Проверить токен на сервере."""
        try:
            resp = requests.get(
                f"{API_BASE}/auth/me",
                headers={"Authorization": f"Bearer {self.jwt_token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                return True
            if resp.status_code == 401 and self.refresh_token:
                return self._refresh()
        except requests.RequestException:
            return True  # оффлайн — считаем токен валидным
        return False

    def _refresh(self) -> bool:
        """Обновить JWT через refresh token."""
        try:
            resp = requests.post(
                f"{API_BASE}/auth/refresh",
                json={"refresh_token": self.refresh_token},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.jwt_token = data["access_token"]
                self._save_tokens()
                return True
        except requests.RequestException:
            pass
        return False

    def _save_tokens(self):
        """Сохранить токены в keyring."""
        keyring.set_password(SERVICE_NAME, "jwt", self.jwt_token)
        if self.refresh_token:
            keyring.set_password(SERVICE_NAME, "refresh", self.refresh_token)
        if self.username:
            keyring.set_password(SERVICE_NAME, "username", self.username)
