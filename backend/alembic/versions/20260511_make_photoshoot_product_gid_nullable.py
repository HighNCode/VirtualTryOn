"""Allow photoshoot jobs without pre-bound Shopify product

Revision ID: u1v2w3x4y5z6
Revises: r8s9t0u1v2w3
Create Date: 2026-05-11 11:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "photoshoot_jobs",
        "shopify_product_gid",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE photoshoot_jobs SET shopify_product_gid = 'gid://shopify/Product/0' "
        "WHERE shopify_product_gid IS NULL"
    )
    op.alter_column(
        "photoshoot_jobs",
        "shopify_product_gid",
        existing_type=sa.String(length=255),
        nullable=False,
    )
