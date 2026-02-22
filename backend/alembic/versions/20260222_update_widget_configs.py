"""Update widget_configs: drop button_text, add widget_color

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-02-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('widget_configs', 'button_text')
    op.add_column('widget_configs', sa.Column('widget_color', sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column('widget_configs', 'widget_color')
    op.add_column('widget_configs', sa.Column('button_text', sa.String(100), nullable=True))
