"""
Auto Updater — проверка и установка обновлений.

Механизм аналогичен E-bot:
1. При запуске → GET /api/version → сравнить с текущей
2. Если есть новая версия → показать баннер
3. Пользователь нажимает "Обновить" → скачать .exe
4. Проверить SHA256 → заменить через bat-скрипт → перезапуск вручную

Известная проблема из E-bot: bat иногда не подменяет .exe (антивирус/блокировка).
Fallback: кнопка "Скачать" открывает браузер.
"""

import hashlib
import os
import sys
import tempfile
import requests
from typing import Optional, Tuple


UPDATE_URL = "https://heyda.ru/planner/api"  # TODO: финализировать


class UpdateManager:
    """Проверка и установка обновлений."""

    def __init__(self, current_version: str):
        self.current_version = current_version

    def check(self) -> Optional[Tuple[str, str]]:
        """
        Проверить обновления.
        Возвращает (new_version, download_url) или None.
        """
        try:
            resp = requests.get(f"{UPDATE_URL}/version", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data["version"] != self.current_version:
                    return data["version"], data["download_url"]
        except requests.RequestException:
            pass
        return None

    def download_and_verify(self, url: str, expected_sha256: str) -> Optional[str]:
        """
        Скачать новую версию и проверить SHA256.
        Возвращает путь к скачанному файлу или None при ошибке.
        """
        try:
            resp = requests.get(url, timeout=60, stream=True)
            if resp.status_code != 200:
                return None

            tmp_path = os.path.join(tempfile.gettempdir(), "planner_update.exe")
            sha = hashlib.sha256()

            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
                    sha.update(chunk)

            if sha.hexdigest() == expected_sha256:
                return tmp_path
            else:
                os.remove(tmp_path)
                return None
        except (requests.RequestException, OSError):
            return None

    @staticmethod
    def create_update_bat(new_exe: str, current_exe: str) -> str:
        """Создать bat-скрипт для замены .exe."""
        bat_path = os.path.join(tempfile.gettempdir(), "planner_update.bat")
        bat_content = f'''@echo off
setlocal
set LOG=%TEMP%\\planner_update.log
echo [%date% %time%] Starting update >> %LOG%
set ATTEMPTS=0
:wait
timeout /t 1 /nobreak >nul
set /a ATTEMPTS+=1
if %ATTEMPTS% GEQ 10 (
    echo [%date% %time%] Timeout after 10 attempts >> %LOG%
    goto :eof
)
copy /y "{new_exe}" "{current_exe}" >> %LOG% 2>&1
if errorlevel 1 goto :wait
echo [%date% %time%] Update complete >> %LOG%
del "{new_exe}" >> %LOG% 2>&1
del "%~f0"
'''
        with open(bat_path, "w") as f:
            f.write(bat_content)
        return bat_path
