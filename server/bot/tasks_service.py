"""
Bot task CRUD service — Phase 5.

Тонкая обёртка вокруг SQLAlchemy async ORM для bot handlers. Пишет в ту же таблицу
tasks что и sync API, поэтому изменения через бота автоматически попадают на
desktop при следующем sync-цикле (≤30 сек).

Почему отдельный service (не переиспользуем sync_routes):
- sync_routes принимает batch `TaskChange[]` через HTTP-route; бот не HTTP
- bot работает с одним task за раз и хочет удобный sync-style API
- DRY достигается на уровне SQL (обе точки пишут в tasks table + updated_at через onupdate)
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db.models import Task

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _combine_day_time(day_iso: str, time_hhmm: Optional[str]) -> Optional[datetime]:
    """'2026-04-17' + '14:00' → datetime(2026,4,17,14,0, tzinfo=utc)."""
    if not time_hhmm:
        return None
    try:
        d = date.fromisoformat(day_iso)
        hh, mm = time_hhmm.split(":")
        t = time(int(hh), int(mm))
        return datetime.combine(d, t, tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


async def create_task(
    db: AsyncSession,
    user_id: str,
    text: str,
    day_iso: str,
    time_hhmm: Optional[str] = None,
) -> Task:
    """BOT-03: создать задачу через бота. UUID генерируется тут (SYNC-06 client-side UUID)."""
    task = Task(
        id=str(uuid.uuid4()),
        user_id=user_id,
        text=text,
        day=day_iso,
        time_deadline=_combine_day_time(day_iso, time_hhmm),
        done=False,
        position=0,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_by_id(
    db: AsyncSession, user_id: str, task_id: str,
) -> Optional[Task]:
    stmt = select(Task).where(
        Task.id == task_id,
        Task.user_id == user_id,
        Task.deleted_at.is_(None),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def toggle_done(
    db: AsyncSession, user_id: str, task_id: str,
) -> Optional[bool]:
    """BOT-05: inline 'выполнить' toggle. Возвращает новое значение done или None если task нет."""
    task = await get_by_id(db, user_id, task_id)
    if task is None:
        return None
    task.done = not task.done
    await db.commit()
    return task.done


async def move_to_day(
    db: AsyncSession, user_id: str, task_id: str, new_day_iso: str,
) -> bool:
    """Inline 'на завтра'. Возвращает True если задача перенесена."""
    task = await get_by_id(db, user_id, task_id)
    if task is None:
        return False
    task.day = new_day_iso
    # Сдвигаем time_deadline на новый день (сохраняем время)
    if task.time_deadline is not None:
        try:
            new_date = date.fromisoformat(new_day_iso)
            task.time_deadline = datetime.combine(
                new_date, task.time_deadline.time(), tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    await db.commit()
    return True


async def soft_delete(
    db: AsyncSession, user_id: str, task_id: str,
) -> bool:
    task = await get_by_id(db, user_id, task_id)
    if task is None:
        return False
    task.deleted_at = _utcnow()
    await db.commit()
    return True


async def get_today_tasks(
    db: AsyncSession, user_id: str, today: Optional[date] = None,
) -> list[Task]:
    """BOT-04: /today."""
    if today is None:
        today = date.today()
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.day == today.isoformat(),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.position.asc(), Task.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_week_tasks(
    db: AsyncSession, user_id: str, week_monday: Optional[date] = None,
) -> dict[date, list[Task]]:
    """BOT-04: /week. Возвращает dict[day_date → list[Task]] для 7 дней Пн-Вс."""
    if week_monday is None:
        today = date.today()
        week_monday = today - timedelta(days=today.weekday())

    sunday = week_monday + timedelta(days=6)
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.day >= week_monday.isoformat(),
            Task.day <= sunday.isoformat(),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.day.asc(), Task.position.asc(), Task.created_at.asc())
    )
    result = await db.execute(stmt)
    tasks = list(result.scalars().all())

    by_day: dict[date, list[Task]] = {
        week_monday + timedelta(days=i): [] for i in range(7)
    }
    for t in tasks:
        try:
            td = date.fromisoformat(t.day)
        except ValueError:
            continue
        if td in by_day:
            by_day[td].append(t)
    return by_day
