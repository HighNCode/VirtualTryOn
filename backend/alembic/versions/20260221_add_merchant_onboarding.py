"""Add merchant onboarding tables and extend stores

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Extend stores table ─────────────────────────────────────────────
    op.add_column('stores', sa.Column(
        'onboarding_step', sa.String(50), server_default='welcome', nullable=False
    ))
    op.add_column('stores', sa.Column('onboarding_completed_at', sa.DateTime(), nullable=True))
    op.add_column('stores', sa.Column(
        'plan_name', sa.String(50), server_default='free', nullable=False
    ))
    op.add_column('stores', sa.Column('plan_shopify_subscription_id', sa.String(255), nullable=True))
    op.add_column('stores', sa.Column('plan_activated_at', sa.DateTime(), nullable=True))
    op.add_column('stores', sa.Column(
        'monthly_tryon_limit', sa.Integer(), server_default='10', nullable=False
    ))

    # ── 2. Create merchant_onboarding table ────────────────────────────────
    op.create_table(
        'merchant_onboarding',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('store_id', UUID(as_uuid=True), nullable=False),
        sa.Column('goals', JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column('referral_source', sa.String(100), nullable=True),
        sa.Column('referral_detail', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.UniqueConstraint('store_id', name='uq_merchant_onboarding_store'),
    )
    op.create_foreign_key(
        'fk_onboarding_store',
        'merchant_onboarding', 'stores',
        ['store_id'], ['store_id'],
        ondelete='CASCADE',
    )

    # ── 3. Create widget_configs table ─────────────────────────────────────
    op.create_table(
        'widget_configs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('store_id', UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', sa.String(20), server_default='all', nullable=False),
        sa.Column('enabled_collection_ids', JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column('enabled_product_ids', JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column('theme_extension_detected', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('theme_id_checked', sa.String(255), nullable=True),
        sa.Column('button_text', sa.String(100), server_default='Try it on', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.UniqueConstraint('store_id', name='uq_widget_configs_store'),
    )
    op.create_foreign_key(
        'fk_widget_config_store',
        'widget_configs', 'stores',
        ['store_id'], ['store_id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    # ── 3. Drop widget_configs ─────────────────────────────────────────────
    op.drop_constraint('fk_widget_config_store', 'widget_configs', type_='foreignkey')
    op.drop_table('widget_configs')

    # ── 2. Drop merchant_onboarding ────────────────────────────────────────
    op.drop_constraint('fk_onboarding_store', 'merchant_onboarding', type_='foreignkey')
    op.drop_table('merchant_onboarding')

    # ── 1. Remove columns from stores ──────────────────────────────────────
    op.drop_column('stores', 'monthly_tryon_limit')
    op.drop_column('stores', 'plan_activated_at')
    op.drop_column('stores', 'plan_shopify_subscription_id')
    op.drop_column('stores', 'plan_name')
    op.drop_column('stores', 'onboarding_completed_at')
    op.drop_column('stores', 'onboarding_step')
