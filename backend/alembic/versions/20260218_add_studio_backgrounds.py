"""Add studio_backgrounds table and extend try_ons

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create studio_backgrounds table
    op.create_table(
        'studio_backgrounds',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('gender', sa.String(10), nullable=False),
        sa.Column('image_path', sa.String(300), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # Add studio columns to try_ons
    op.add_column('try_ons', sa.Column('studio_background_id', UUID(as_uuid=True), nullable=True))
    op.add_column('try_ons', sa.Column('parent_try_on_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_try_ons_studio_bg', 'try_ons', 'studio_backgrounds', ['studio_background_id'], ['id'])
    op.create_foreign_key('fk_try_ons_parent', 'try_ons', 'try_ons', ['parent_try_on_id'], ['try_on_id'])


def downgrade() -> None:
    op.drop_constraint('fk_try_ons_parent', 'try_ons', type_='foreignkey')
    op.drop_constraint('fk_try_ons_studio_bg', 'try_ons', type_='foreignkey')
    op.drop_column('try_ons', 'parent_try_on_id')
    op.drop_column('try_ons', 'studio_background_id')
    op.drop_table('studio_backgrounds')
