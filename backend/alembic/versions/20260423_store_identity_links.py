"""Add store identity links for anon-to-customer migration

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-04-23 14:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_identity_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("anon_identifier", sa.String(length=255), nullable=False),
        sa.Column("customer_identifier", sa.String(length=255), nullable=False),
        sa.Column("last_migrated_week_start_utc", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "store_id",
            "anon_identifier",
            "customer_identifier",
            name="uq_store_identity_link",
        ),
    )
    op.create_index(
        "idx_store_identity_links_store_customer",
        "store_identity_links",
        ["store_id", "customer_identifier"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_store_identity_links_store_customer", table_name="store_identity_links")
    op.drop_table("store_identity_links")
