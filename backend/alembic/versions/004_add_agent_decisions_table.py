"""add agent_decisions table

Revision ID: 004
Revises: 003
Create Date: 2026-08-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "synthetic_event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("synthetic_events.id"),
            nullable=False,
        ),
        sa.Column("diagnosis", sa.String(), nullable=False),
        sa.Column("recovery_probability", sa.Float(), nullable=False),
        sa.Column("recommended_action", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("decision_path", sa.String(), nullable=False),
        sa.Column("override_reason", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_decisions")
