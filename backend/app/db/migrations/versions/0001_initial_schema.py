"""Initial schema: sessions, messages, assessments, session_tokens, idempotency_records.

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("schema_version", sa.Text(), nullable=False, server_default="v1"),
        sa.Column("profile", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("conversation_state", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("turn_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_session_created", "messages", ["session_id", "created_at"])

    op.create_table(
        "assessments",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile_revision", sa.Integer(), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessments_session_created", "assessments", ["session_id", "created_at"])

    op.create_table(
        "session_tokens",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_tokens_session", "session_tokens", ["session_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("client_request_id", sa.Text(), nullable=False),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_cache", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_pending", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("client_request_id"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_tokens_session", table_name="session_tokens")
    op.drop_table("session_tokens")
    op.drop_index("ix_assessments_session_created", table_name="assessments")
    op.drop_table("assessments")
    op.drop_index("ix_messages_session_created", table_name="messages")
    op.drop_table("messages")
    op.drop_table("sessions")
