"""Add photoshoot_models and photoshoot_jobs tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-02-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'photoshoot_models',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('gender', sa.String(10), nullable=False),
        sa.Column('image_path', sa.String(300), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'photoshoot_jobs',
        sa.Column('job_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('store_id', UUID(as_uuid=True), sa.ForeignKey('stores.store_id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_type', sa.String(20), nullable=False),
        sa.Column('shopify_product_gid', sa.String(255), nullable=False),
        sa.Column('processing_status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('result_cache_key', sa.String(200), nullable=True),
        sa.Column('processing_time_seconds', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('shopify_media_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('idx_photoshoot_jobs_store', 'photoshoot_jobs', ['store_id'])
    op.create_index('idx_photoshoot_jobs_status', 'photoshoot_jobs', ['processing_status'])


def downgrade() -> None:
    op.drop_index('idx_photoshoot_jobs_status', table_name='photoshoot_jobs')
    op.drop_index('idx_photoshoot_jobs_store', table_name='photoshoot_jobs')
    op.drop_table('photoshoot_jobs')
    op.drop_table('photoshoot_models')
