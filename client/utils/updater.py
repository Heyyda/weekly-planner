"""
Auto Updater — проверка и установка обновлений клиента.

Flow:
  1. При запуске → GET {API_BASE}/version → сравнить с текущей версией
  2. Если есть новая — UpdateBanner показывает "Доступна v0.3.1 · Обновить"
  3. Click "Обновить" → download → SHA256 verify → bat-rename trick → sys.exit()
  4. Bat-скрипт ждёт завершения текущего процесса, копирует новый .exe, перезапускает
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import tempfile
from typing import Callable, Optional, Tuple

import requests

from client.core import config as client_config

logger = logging.getLogger(__name__)


class UpdateManager:
    """Проверка и установка обновлений через /api/version + GitHub release."""

    def __init__(self, current_version: str) -> None:
        self.current_version = current_version
        self._api_base = client_config.API_BASE

    def check(self) -> Optional[Tuple[str, str, str]]:
        """GET /api/version — вернуть (new_version, download_url, sha256) или None."""
        try:
            resp = requests.get(f"{self._api_base}/version", timeout=5)
            if resp.status_code != 200:
                logger.debug("check: HTTP %d", resp.status_code)
                return None
            data = resp.json()
            server_ver = str(data.get("version", "")).strip()
            if not server_ver or server_ver == self.current_version:
                return None
            url = str(data.get("download_url", "")).strip()
            sha = str(data.get("sha256", "")).strip()
            if not url:
                logger.warning("check: новая %s но download_url пуст", server_ver)
                return None
            return (server_ver, url, sha)
        except (requests.RequestException, ValueError) as exc:
            logger.debug("check failed: %s", exc)
            return None

    def download_and_verify(
        self,
        url: str,
        expected_sha256: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[str]:
        """Скачать + SHA256 verify. Возвращает путь к tmp-файлу или None."""
        try:
            resp = requests.get(url, timeout=60, stream=True, allow_redirects=True)
            if resp.status_code != 200:
                logger.error("download HTTP %d", resp.status_code)
                return None

            tmp_path = os.path.join(tempfile.gettempdir(), "planner_update.exe")
            total = int(resp.headers.get("Content-Length", "0") or 0)
            received = 0
            sha = hashlib.sha256()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    f.write(chunk)
                    sha.update(chunk)
                    received += len(chunk)
                    if progress_cb is not None:
                        try:
                            progress_cb(received, total)
                        except Exception:
                            pass

            if expected_sha256:
                actual = sha.hexdigest()
                if actual != expected_sha256:
                    logger.error("SHA256 mismatch: expected=%s got=%s", expected_sha256, actual)
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                    return None
            return tmp_path
        except (requests.RequestException, OSError) as exc:
            logger.error("download failed: %s", exc)
            return None

    def apply_update(self, new_exe: str) -> bool:
        """Запустить bat-скрипт замены detached. После return — вызывающий должен sys.exit()."""
        current_exe = self._current_exe_path()
        if current_exe is None:
            logger.error("apply_update: не могу определить .exe (dev-mode?)")
            return False
        bat_path = self._create_update_bat(new_exe, current_exe)
        try:
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        except OSError as exc:
            logger.error("apply_update Popen: %s", exc)
            return False
        logger.info("Update bat запущен")
        return True

    @staticmethod
    def _current_exe_path() -> Optional[str]:
        """Путь к текущему .exe. None если dev-mode (python main.py)."""
        if getattr(sys, "frozen", False):
            return sys.executable
        return None

    @staticmethod
    def _create_update_bat(new_exe: str, current_exe: str) -> str:
        bat_path = os.path.join(tempfile.gettempdir(), "planner_update.bat")
        bat_content = f"""@echo off
setlocal
set LOG=%TEMP%\\planner_update.log
echo [%date% %time%] Starting update >> %LOG%
set ATTEMPTS=0
:wait
timeout /t 1 /nobreak >nul
set /a ATTEMPTS+=1
if %ATTEMPTS% GEQ 15 (
    echo [%date% %time%] Timeout after 15 attempts >> %LOG%
    goto :eof
)
copy /y "{new_exe}" "{current_exe}" >> %LOG% 2>&1
if errorlevel 1 goto :wait
echo [%date% %time%] Copy done, restarting >> %LOG%
start "" "{current_exe}"
del "{new_exe}" >> %LOG% 2>&1
del "%~f0"
"""
        with open(bat_path, "w", encoding="cp866") as f:
            f.write(bat_content)
        return bat_path
