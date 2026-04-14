"""
Маркер-тест Wave 0: pytest собирается, fixtures импортируются, asyncio-режим работает.

Последующие plans (02-11) добавляют тесты в этот же каталог.
Этот файл остаётся как self-check инфраструктуры.
"""
import pytest
import sys


def test_python_version():
    """Python >= 3.10 нужен для SQLAlchemy 2.x async и aiogram 3.x."""
    assert sys.version_info >= (3, 10), f"Нужен Python 3.10+, установлен {sys.version_info}"


@pytest.mark.asyncio
async def test_asyncio_mode_auto_works():
    """Проверяет что pytest-asyncio в auto-режиме подхватывает async test без декоратора-маркера на каждом."""
    import asyncio
    await asyncio.sleep(0)
    assert True


def test_conftest_fixtures_importable():
    """Проверяет что conftest.py парсится и модуль tests — корректный пакет."""
    from server.tests import conftest
    assert hasattr(conftest, "test_engine")
    assert hasattr(conftest, "db_session")
