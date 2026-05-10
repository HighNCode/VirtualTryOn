"""Add daily overage settlement metadata and unsettled-events index

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-05-10 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("last_overage_settlement_local_date", sa.Date(), nullable=True))
    op.add_column("stores", sa.Column("last_overage_settlement_at", sa.DateTime(), nullable=True))
    op.create_index(
        "idx_usage_events_unsettled_overage",
        "usage_events",
        ["store_id", "status", "usage_charge_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_usage_events_unsettled_overage", table_name="usage_events")
    op.drop_column("stores", "last_overage_settlement_at")
    op.drop_column("stores", "last_overage_settlement_local_date")
