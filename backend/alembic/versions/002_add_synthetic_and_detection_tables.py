"""add synthetic_events and detection_results tables

Revision ID: 002
Revises: 001
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "synthetic_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("customer_ref", sa.String(), nullable=False),
        sa.Column(
            "previous_successful_payments",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "previous_recovery_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column(
            "ground_truth_recoverable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "ground_truth_outcome",
            sa.String(),
            nullable=False,
            server_default="not_applicable",
        ),
        sa.Column(
            "ground_truth_recovered_amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "detection_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "synthetic_event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("synthetic_events.id"),
            nullable=False,
        ),
        sa.Column(
            "at_risk",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "recoverability",
            sa.String(),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "risk_reason",
            sa.String(),
            nullable=False,
            server_default="NOT_AT_RISK",
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("detection_results")
    op.drop_table("synthetic_events")
