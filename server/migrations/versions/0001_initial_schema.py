"""initial schema: users, auth_codes, sessions, tasks

Revision ID: 0001
Revises:
Create Date: 2026-04-14

Покрывает SRV-04 (4 модели) и закладывает основу для SRV-06 (server-side updated_at).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users — пользователь Telegram, привязан к chat_id после /start
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("telegram_username", sa.String(), nullable=False, unique=True),
        sa.Column("telegram_chat_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_telegram_username", "users", ["telegram_username"], unique=True)

    # auth_codes — коды подтверждения (bcrypt-hash, 5min TTL, single-use)
    op.create_table(
        "auth_codes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auth_codes_username", "auth_codes", ["username"])

    # sessions — refresh-токены активных устройств
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("device_name", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # tasks — задачи с tombstone (deleted_at) для SYNC
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),  # UUID от клиента
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("time_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_day", "tasks", ["day"])
    op.create_index("ix_tasks_user_updated", "tasks", ["user_id", "updated_at"])


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("sessions")
    op.drop_table("auth_codes")
    op.drop_table("users")
