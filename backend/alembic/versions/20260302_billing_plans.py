"""Billing plans: add plans table, rename monthly_tryon_limit, add billing_interval + trial_ends_at

- Creates plans table with seed data (Starter + Growth)
- Renames stores.monthly_tryon_limit → stores.credits_limit
- Adds stores.billing_interval VARCHAR(10)
- Adds stores.trial_ends_at TIMESTAMP

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-03-02 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6g7h8i9j0k1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create plans table ─────────────────────────────────────────────────
    op.create_table(
        'plans',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('price_monthly', sa.Numeric(8, 2), nullable=False),
        sa.Column('price_annual_total', sa.Numeric(8, 2), nullable=False),
        sa.Column('price_annual_per_month', sa.Numeric(8, 2), nullable=False),
        sa.Column('annual_discount_pct', sa.Integer(), nullable=False, server_default='17'),
        sa.Column('credits_monthly', sa.Integer(), nullable=False),
        sa.Column('credits_annual', sa.Integer(), nullable=False),
        sa.Column('trial_days', sa.Integer(), nullable=True),
        sa.Column('trial_credits', sa.Integer(), nullable=True),
        sa.Column('features', JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('name', name='uq_plans_name'),
    )

    # ── 2. Seed starter + growth plans ───────────────────────────────────────
    now = "NOW()"
    op.execute(f"""
        INSERT INTO plans
            (id, name, display_name,
             price_monthly, price_annual_total, price_annual_per_month, annual_discount_pct,
             credits_monthly, credits_annual,
             trial_days, trial_credits,
             features, is_active, sort_order,
             created_at, updated_at)
        VALUES
        (
            '{uuid.uuid4()}',
            'starter',
            'Starter',
            17.00, 179.00, 14.00, 17,
            600, 7600,
            14, 80,
            '["600 credits/month","AI Try-On","AI Studio Look","Fit heatmap","Analytics","Email support"]'::jsonb,
            true, 1,
            {now}, {now}
        ),
        (
            '{uuid.uuid4()}',
            'growth',
            'Growth',
            29.00, 299.00, 24.00, 17,
            1000, 12800,
            14, 80,
            '["1,000 credits/month","AI Try-On","AI Studio Look","Fit heatmap","Analytics","Priority support","Custom widget branding"]'::jsonb,
            true, 2,
            {now}, {now}
        )
    """)

    # ── 3. Rename monthly_tryon_limit → credits_limit in stores ──────────────
    op.alter_column('stores', 'monthly_tryon_limit', new_column_name='credits_limit')

    # Update existing stores: free-plan stores had limit=10 which was the old free default.
    # Reset to 0 (free plan has no credits under the new model).
    op.execute("UPDATE stores SET credits_limit = 0 WHERE plan_name = 'free'")

    # ── 4. Add billing_interval column to stores ──────────────────────────────
    op.add_column('stores', sa.Column('billing_interval', sa.String(10), nullable=True))

    # ── 5. Add trial_ends_at column to stores ────────────────────────────────
    op.add_column('stores', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # ── 5. Drop trial_ends_at ─────────────────────────────────────────────────
    op.drop_column('stores', 'trial_ends_at')

    # ── 4. Drop billing_interval ──────────────────────────────────────────────
    op.drop_column('stores', 'billing_interval')

    # ── 3. Rename credits_limit → monthly_tryon_limit ─────────────────────────
    op.alter_column('stores', 'credits_limit', new_column_name='monthly_tryon_limit')

    # Restore old free-plan default (10)
    op.execute("UPDATE stores SET monthly_tryon_limit = 10 WHERE plan_name = 'free'")

    # ── 2. (Seed rows deleted automatically with table drop) ─────────────────

    # ── 1. Drop plans table ───────────────────────────────────────────────────
    op.drop_table('plans')
