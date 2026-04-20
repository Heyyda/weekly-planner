"""
Database — SQLite через SQLAlchemy.

Таблицы:
- users: id, telegram_username, created_at
- tasks: id, user_id, text, done, priority, day, position, category_id, created_at, updated_at
- categories: id, user_id, name, color
- recurring_templates: id, user_id, text, priority, category_id, weekdays (JSON)
- day_notes: user_id, day, text, updated_at
"""

from sqlalchemy import create_engine, Column, String, Boolean, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

from server.config import DB_PATH


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    telegram_username = Column(String, unique=True, nullable=False)
    telegram_chat_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("TaskRecord", back_populates="user")
    categories = relationship("CategoryRecord", back_populates="user")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    done = Column(Boolean, default=False)
    priority = Column(Integer, default=2)
    day = Column(String, nullable=False)  # ISO date
    position = Column(Integer, default=0)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tasks")
    category = relationship("CategoryRecord")


class CategoryRecord(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, default="#4a9eff")

    user = relationship("User", back_populates="categories")


class DayNote(Base):
    __tablename__ = "day_notes"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    day = Column(String, primary_key=True)
    text = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecurringTemplate(Base):
    __tablename__ = "recurring_templates"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    priority = Column(Integer, default=2)
    category_id = Column(String, nullable=True)
    weekdays = Column(String, default="[]")  # JSON array: [0,2,4] = Пн, Ср, Пт


# Инициализация
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Создать таблицы."""
    Base.metadata.create_all(engine)
