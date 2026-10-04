"""Email and password accounts, password reset links, and profiles saved per account.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "google_sub", existing_type=sa.Text(), nullable=True)
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Every account so far signed in with Google, which only accepts verified addresses.
    op.execute("UPDATE users SET email = lower(email), email_verified = true")
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
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
    op.create_index("ix_password_reset_tokens_user", "password_reset_tokens", ["user_id"])

    op.create_table(
        "profile_states",
        sa.Column(
            "user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("profile_states")
    op.drop_index("ix_password_reset_tokens_user", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    # Accounts without Google can't exist in the old schema; downgrading deletes them.
    op.execute("DELETE FROM users WHERE google_sub IS NULL")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_hash")
    op.alter_column("users", "google_sub", existing_type=sa.Text(), nullable=False)
