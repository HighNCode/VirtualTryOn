"""Add intro trial and billing lock fields to stores

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-04-20 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("trial_mode", sa.String(length=20), nullable=False, server_default="none"))
    op.add_column("stores", sa.Column("has_used_intro_trial", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("stores", sa.Column("trial_end_reason", sa.String(length=40), nullable=True))
    op.add_column("stores", sa.Column("billing_lock_reason", sa.String(length=60), nullable=True))

    # Backfill founding merchants as intro-trial users so they don't receive paid-plan trial again.
    op.execute(
        """
        UPDATE stores
        SET trial_mode = 'intro_free',
            has_used_intro_trial = true
        WHERE plan_name = 'founding_trial'
        """
    )


def downgrade() -> None:
    op.drop_column("stores", "billing_lock_reason")
    op.drop_column("stores", "trial_end_reason")
    op.drop_column("stores", "has_used_intro_trial")
    op.drop_column("stores", "trial_mode")
