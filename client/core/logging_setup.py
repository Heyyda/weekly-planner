"""
Единая инициализация логирования клиента.

Использование (один раз при старте app):
    from client.core.paths import AppPaths
    from client.core.logging_setup import setup_client_logging

    paths = AppPaths(); paths.ensure()
    setup_client_logging(paths)

После этого все `logging.getLogger("client.X")` пишут в logs/client.log с rotation.

D-27: RotatingFileHandler, maxBytes=1MB, backupCount=5
D-28: requests/urllib3 → WARNING
D-29: SecretFilter маскирует JWT-токены в любых log-записях
"""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Константы с fallback-значениями если config.py ещё недоступен (параллельная сборка).
# При наличии client.core.config они будут переопределены.
try:
    from client.core import config as _config

    _LOG_FILE_NAME: str = _config.LOG_FILE_NAME
    _LOG_ROTATION_MAX_BYTES: int = _config.LOG_ROTATION_MAX_BYTES
    _LOG_ROTATION_BACKUP_COUNT: int = _config.LOG_ROTATION_BACKUP_COUNT
except ImportError:
    # Fallback — те же значения что и в config.py (D-27)
    _LOG_FILE_NAME = "client.log"
    _LOG_ROTATION_MAX_BYTES = 1_000_000
    _LOG_ROTATION_BACKUP_COUNT = 5

# Атрибут-маркер на root logger — для идемпотентности setup_client_logging.
_SETUP_MARKER = "_planner_client_logging_initialized"

# Регулярки для маскировки секретов в log-сообщениях (D-29).
# Покрываем варианты: token=value, "token": "value", Bearer value
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE), r"\1***"),
    (re.compile(r'(access_token["\'\s:=]+)[A-Za-z0-9._\-]+', re.IGNORECASE), r"\1***"),
    (re.compile(r'(refresh_token["\'\s:=]+)[A-Za-z0-9._\-]+', re.IGNORECASE), r"\1***"),
]


class SecretFilter(logging.Filter):
    """
    Маскирует JWT и refresh tokens в log-записях (D-29).

    Применяется к record.msg и каждому элементу record.args.
    Возвращает True (запись пропускается, но с замаскированным содержимым).
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            if isinstance(record.msg, str):
                record.msg = self._mask(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: self._mask_value(v) for k, v in record.args.items()}
                elif isinstance(record.args, tuple):
                    record.args = tuple(self._mask_value(a) for a in record.args)
        except Exception:  # filter не должен ронять логирование
            pass
        return True

    @staticmethod
    def _mask(text: str) -> str:
        """Применить все _SECRET_PATTERNS к строке."""
        for pattern, repl in _SECRET_PATTERNS:
            text = pattern.sub(repl, text)
        return text

    @classmethod
    def _mask_value(cls, value: Any) -> Any:
        """Маскировать строковое значение, не трогать нестроковые типы."""
        if isinstance(value, str):
            return cls._mask(value)
        return value


def setup_client_logging(
    paths: Any,
    level: int = logging.DEBUG,
) -> RotatingFileHandler:
    """
    Настроить root logger клиента (один раз).

    Параметры:
        paths: объект с атрибутом logs_dir (Path) — AppPaths уже с вызванным ensure().
               Принимает duck-typed объект для совместимости при параллельной разработке.
        level: уровень root logger (default DEBUG для богатой диагностики в файле).

    Возвращает: созданный RotatingFileHandler (полезно для unit testing).

    Идемпотентность: повторный вызов возвращает существующий handler из root logger.
    """
    root = logging.getLogger()

    # Идемпотентность через маркер на root logger
    if getattr(root, _SETUP_MARKER, False):
        for h in root.handlers:
            if isinstance(h, RotatingFileHandler):
                return h
        # Нет handler но маркер есть — странное состояние, продолжим установку

    logs_dir: Path = paths.logs_dir
    log_file = logs_dir / _LOG_FILE_NAME

    handler = RotatingFileHandler(
        log_file,
        maxBytes=_LOG_ROTATION_MAX_BYTES,
        backupCount=_LOG_ROTATION_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
    ))
    handler.addFilter(SecretFilter())

    root.addHandler(handler)
    root.setLevel(level)
    setattr(root, _SETUP_MARKER, True)

    # Шумные библиотеки → WARNING (D-28)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("keyring").setLevel(logging.WARNING)

    return handler


def reset_client_logging() -> None:
    """
    Сбросить состояние логирования (только для тестов!).

    Удаляет все handlers и снимает маркер с root logger.
    Также сбрасывает уровни 'requests'/'urllib3' чтобы не влиять на другие тесты.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    if hasattr(root, _SETUP_MARKER):
        delattr(root, _SETUP_MARKER)
    # Сбрасываем уровни шумных логгеров (изоляция тестов)
    for name in ("requests", "urllib3", "keyring"):
        logging.getLogger(name).setLevel(logging.NOTSET)
