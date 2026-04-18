"""Plan-specific overage pricing per try-on

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-18 18:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("overage_usd_per_tryon", sa.Numeric(10, 4), server_default="0.1400", nullable=False),
    )

    op.execute("UPDATE plans SET overage_usd_per_tryon = 0.1400 WHERE name = 'starter'")
    op.execute("UPDATE plans SET overage_usd_per_tryon = 0.0980 WHERE name = 'growth'")
    op.execute("UPDATE plans SET overage_usd_per_tryon = 0.0780 WHERE name = 'professional'")
    op.execute("UPDATE plans SET overage_usd_per_tryon = 0.0680 WHERE name = 'scale'")


def downgrade() -> None:
    op.drop_column("plans", "overage_usd_per_tryon")
