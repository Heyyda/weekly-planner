"""
Pydantic v2 схемы для /api/sync endpoint.

Протокол:
  Request:  SyncIn {since: datetime | None, changes: list[TaskChange]}
  Response: SyncOut {server_timestamp: datetime, changes: list[TaskState]}

TaskChange — операция от клиента (create/update/delete).
TaskState — полное состояние task с серверными полями (updated_at, deleted_at).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SyncOp(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class TaskChange(BaseModel):
    """
    Операция от клиента.

    CREATE: требуется task_id (UUID) + все поля task (text, day обязательные).
    UPDATE: task_id + partial fields (те что меняются).
    DELETE: только task_id.
    """
    op: SyncOp
    task_id: str = Field(..., description="UUID от клиента (SYNC-06: client-generated id)")
    text: Optional[str] = None
    day: Optional[str] = Field(default=None, description="ISO date: 2026-04-14")
    time_deadline: Optional[datetime] = None
    done: Optional[bool] = None
    position: Optional[int] = None

    @field_validator("day")
    @classmethod
    def validate_day_format(cls, v):
        if v is None:
            return v
        # Простая ISO date проверка — не strict parse, пусть datetime.fromisoformat разбирается
        if len(v) != 10 or v[4] != "-" or v[7] != "-":
            raise ValueError("day должен быть ISO date 'YYYY-MM-DD'")
        return v


class SyncIn(BaseModel):
    since: Optional[datetime] = Field(
        default=None,
        description="Клиент присылает updated_at последней успешной синхронизации; null = полный sync",
    )
    changes: List[TaskChange] = Field(default_factory=list)


class TaskState(BaseModel):
    """Полное серверное состояние task — возвращается в delta."""
    task_id: str
    text: str
    day: str
    time_deadline: Optional[datetime] = None
    done: bool
    position: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class SyncOut(BaseModel):
    server_timestamp: datetime = Field(
        ...,
        description="Время ответа; клиент сохраняет как новый since для следующего sync",
    )
    changes: List[TaskState] = Field(default_factory=list)
