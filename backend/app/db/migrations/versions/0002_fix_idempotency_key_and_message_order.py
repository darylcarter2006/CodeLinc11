"""Scope idempotency records per session; order messages by insertion sequence.

* idempotency_records: the primary key was client_request_id alone, so two sessions
  using the same ID shared (and overwrote) one record. The key is now
  (session_id, client_request_id). Existing records are short-lived replay caches,
  so they are cleared rather than migrated.
* messages: a turn's user and assistant messages share created_at, so ordering by it
  was ambiguous. A monotonically increasing seq column now defines the order.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM idempotency_records")
    op.drop_constraint("idempotency_records_pkey", "idempotency_records", type_="primary")
    op.create_primary_key(
        "idempotency_records_pkey", "idempotency_records", ["session_id", "client_request_id"]
    )

    # Existing rows get sequence numbers in table order; new rows are numbered on insert.
    op.add_column(
        "messages",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
    )
    op.drop_index("ix_messages_session_created", table_name="messages")
    op.create_index("ix_messages_session_seq", "messages", ["session_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_messages_session_seq", table_name="messages")
    op.create_index("ix_messages_session_created", "messages", ["session_id", "created_at"])
    op.drop_column("messages", "seq")

    op.execute("DELETE FROM idempotency_records")
    op.drop_constraint("idempotency_records_pkey", "idempotency_records", type_="primary")
    op.create_primary_key("idempotency_records_pkey", "idempotency_records", ["client_request_id"])
