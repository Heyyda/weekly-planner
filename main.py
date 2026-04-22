"""
Личный Еженедельник — точка входа.
Десктопный недельный планировщик задач с draggable-overlay.

Cyrillic-path robustness: используем Path(__file__).resolve().parent
вместо os.path.abspath() — защита от encoding краша на путях
типа s:\\Проекты\\ежедневник\\ (PITFALL: Cyrillic in sys.path on Windows).
"""
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path (резолвим абсолютно — Cyrillic-safe)
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from client.app import WeeklyPlannerApp

VERSION = "0.6.0"


def main() -> None:
    """Точка входа: инициализация логирования + запуск приложения."""
    # Минимальный logging до полноценного setup внутри app (избегаем silent crashes)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    app = WeeklyPlannerApp(version=VERSION)
    app.run()


if __name__ == "__main__":
    main()
