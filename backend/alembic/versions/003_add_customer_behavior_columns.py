"""add customer behavior and checkout columns to synthetic_events

Revision ID: 003
Revises: 002
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "synthetic_events",
        sa.Column("customer_tenure_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "synthetic_events",
        sa.Column(
            "previous_failed_payments",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "synthetic_events",
        sa.Column("average_order_value", sa.Integer(), nullable=True),
    )
    op.add_column(
        "synthetic_events",
        sa.Column(
            "time_since_last_successful_payment_hours",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "synthetic_events",
        sa.Column(
            "time_since_last_recovery_attempt_hours",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "synthetic_events",
        sa.Column("checkout_duration_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "synthetic_events",
        sa.Column("payment_method", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("synthetic_events", "payment_method")
    op.drop_column("synthetic_events", "checkout_duration_seconds")
    op.drop_column("synthetic_events", "time_since_last_recovery_attempt_hours")
    op.drop_column("synthetic_events", "time_since_last_successful_payment_hours")
    op.drop_column("synthetic_events", "average_order_value")
    op.drop_column("synthetic_events", "previous_failed_payments")
    op.drop_column("synthetic_events", "customer_tenure_days")
