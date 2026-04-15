"""
POST /api/sync — delta-синхронизация задач (SRV-02, SRV-06).

Алгоритм:
1. Авторизация через Bearer (get_current_user)
2. Для каждой TaskChange в request.changes:
   - CREATE: INSERT OR IGNORE (идемпотентно — SYNC-06 UUID client-generated)
   - UPDATE: SET only переданные поля + updated_at = server_now (SRV-06)
   - DELETE: SET deleted_at = now (tombstone — не hard delete)
3. Выполнить delta-query: SELECT tasks WHERE user_id=? AND updated_at > since
   (если since None — все tasks user'а)
4. Вернуть server_timestamp + changes (включая tombstones с deleted_at != None)

Server-wins конфликт-резолюция: клиент присылает изменения — сервер применяет их
без версий/vector clocks; при конфликте последний writer wins (простой подход для
single-user проекта). См. ARCHITECTURE.md §Key Architectural Tradeoffs.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.sync_schemas import SyncIn, SyncOp, SyncOut, TaskChange, TaskState
from server.auth.dependencies import get_current_user
from server.db.engine import get_db
from server.db.models import Task, User

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _apply_create(db: AsyncSession, user_id: str, change: TaskChange) -> None:
    """
    INSERT OR IGNORE idempotent — при повторной попытке create с тем же task_id
    просто скипаем (SYNC-06: CREATE идемпотентен).
    """
    existing_stmt = select(Task).where(Task.id == change.task_id, Task.user_id == user_id)
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        # Идемпотентность: уже есть — трактуем как update (клиент возможно retry'ит)
        await _apply_update(db, user_id, change, existing)
        return

    task = Task(
        id=change.task_id,
        user_id=user_id,
        text=change.text or "",
        day=change.day or "",
        time_deadline=change.time_deadline,
        done=bool(change.done) if change.done is not None else False,
        position=change.position if change.position is not None else 0,
    )
    db.add(task)


async def _apply_update(
    db: AsyncSession, user_id: str, change: TaskChange, existing: Task | None = None
) -> None:
    """Apply partial update to task (updated_at выставится сервером через onupdate)."""
    if existing is None:
        stmt = select(Task).where(Task.id == change.task_id, Task.user_id == user_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is None:
        # Апдейт для несуществующей task — игнорируем (клиент пропустил CREATE; resync подтянет)
        return

    if change.text is not None:
        existing.text = change.text
    if change.day is not None:
        existing.day = change.day
    if change.time_deadline is not None:
        existing.time_deadline = change.time_deadline
    if change.done is not None:
        existing.done = change.done
    if change.position is not None:
        existing.position = change.position
    # updated_at обновляется автоматически через onupdate=func.now() в модели


async def _apply_delete(db: AsyncSession, user_id: str, change: TaskChange) -> None:
    """Soft-delete — ставим deleted_at (tombstone)."""
    stmt = select(Task).where(Task.id == change.task_id, Task.user_id == user_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return
    if existing.deleted_at is None:
        existing.deleted_at = _utcnow()


def _to_state(t: Task) -> TaskState:
    return TaskState(
        task_id=t.id,
        text=t.text,
        day=t.day,
        time_deadline=t.time_deadline,
        done=t.done,
        position=t.position,
        created_at=t.created_at,
        updated_at=t.updated_at,
        deleted_at=t.deleted_at,
    )


@router.post("", response_model=SyncOut)
async def sync(
    body: SyncIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delta-sync endpoint (SRV-02).

    SRV-06: updated_at всегда из БД (onupdate=func.now() у Task), не из клиента.
    """
    # Применить changes
    for change in body.changes:
        if change.op == SyncOp.CREATE:
            await _apply_create(db, current_user.id, change)
        elif change.op == SyncOp.UPDATE:
            await _apply_update(db, current_user.id, change)
        elif change.op == SyncOp.DELETE:
            await _apply_delete(db, current_user.id, change)

    # Commit — заставит onupdate применить к обновлённым rows
    await db.commit()

    # Delta: все tasks user с updated_at > since (или все если since=None)
    server_now = _utcnow()
    stmt = select(Task).where(Task.user_id == current_user.id)
    if body.since is not None:
        stmt = stmt.where(Task.updated_at > body.since)
    stmt = stmt.order_by(Task.updated_at.asc())

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return SyncOut(
        server_timestamp=server_now,
        changes=[_to_state(t) for t in tasks],
    )
