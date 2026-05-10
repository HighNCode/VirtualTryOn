"""Add customer media archival object path fields

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-05-10 14:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_measurements", sa.Column("front_image_object_path", sa.String(length=500), nullable=True))
    op.add_column("user_measurements", sa.Column("side_image_object_path", sa.String(length=500), nullable=True))
    op.add_column("try_ons", sa.Column("result_object_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("try_ons", "result_object_path")
    op.drop_column("user_measurements", "side_image_object_path")
    op.drop_column("user_measurements", "front_image_object_path")
