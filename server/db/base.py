"""
Базовый класс SQLAlchemy 2.x для всех моделей Личного Еженедельника.

Использует новый API SQLAlchemy 2.0 (DeclarativeBase class), а не устаревший
declarative_base() function. Это было рекомендовано в RESEARCH.md §State of the Art.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Общий базовый класс для всех ORM-моделей.

    Все модели в server/db/models.py наследуются от Base — это регистрирует их
    в Base.metadata, которую потом читает Alembic для автогенерации миграций.
    """
    pass


def utcnow() -> datetime:
    """
    Timezone-aware UTC now().

    Используется вместо deprecated datetime.utcnow() (Python 3.12+ выдаёт
    DeprecationWarning, будет ошибкой в 3.14). См. PITFALLS.md Pitfall 7.
    """
    return datetime.now(timezone.utc)
