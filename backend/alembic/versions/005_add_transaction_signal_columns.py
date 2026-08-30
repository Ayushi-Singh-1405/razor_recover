"""add failure_reason and previous_recovery_attempts to transactions

Allows real transactions to carry the same observed signals the Phase 1
detector evaluates on synthetic events (status, failure_reason,
previous_recovery_attempts), so the execution policy can classify real
orders. Amount and status already exist on transactions.

Revision ID: 005
Revises: 004
Create Date: 2026-08-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("failure_reason", sa.String(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "previous_recovery_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "previous_recovery_attempts")
    op.drop_column("transactions", "failure_reason")
