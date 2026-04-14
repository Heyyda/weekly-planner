"""
Личный Еженедельник — точка входа.
Десктопный недельный планировщик задач с боковой панелью.
"""

import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.app import WeeklyPlannerApp


VERSION = "0.1.0"


def main():
    app = WeeklyPlannerApp(version=VERSION)
    app.run()


if __name__ == "__main__":
    main()
