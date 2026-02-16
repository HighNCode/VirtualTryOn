"""Make try_ons.measurement_id nullable and drop size_name

Revision ID: a1b2c3d4e5f6
Revises: 7513a4ced961
Create Date: 2026-02-16 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7513a4ced961'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('try_ons', 'measurement_id', nullable=True)
    op.drop_column('try_ons', 'size_name')


def downgrade() -> None:
    op.add_column('try_ons', sa.Column('size_name', sa.String(length=20), nullable=True))
    op.alter_column('try_ons', 'measurement_id', nullable=False)
