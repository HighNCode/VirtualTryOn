"""Seed professional and scale billing plans

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-05-13 11:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "w3x4y5z6a7b8"
down_revision: Union[str, None] = "v2w3x4y5z6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROFESSIONAL_PLAN_ID = "8f2753f9-6d4f-4a4f-b79f-5486614da04e"
SCALE_PLAN_ID = "ca2ee20e-2c48-4daf-83c6-0576da50be4a"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO plans
            (
                id,
                name,
                display_name,
                price_monthly,
                price_annual_total,
                price_annual_per_month,
                annual_discount_pct,
                credits_monthly,
                credits_annual,
                overage_usd_per_tryon,
                trial_days,
                trial_credits,
                usage_cap_usd,
                features,
                is_active,
                sort_order,
                created_at,
                updated_at
            )
        VALUES
            (
                '{PROFESSIONAL_PLAN_ID}'::uuid,
                'professional',
                'Professional',
                49.99,
                499.00,
                41.58,
                17,
                1680,
                21000,
                0.0780,
                14,
                80,
                500.00,
                '["420 AI experiences","Advanced analytics","Priority speed","Photostudio","Social sharing","Priority support"]'::jsonb,
                true,
                3,
                NOW(),
                NOW()
            ),
            (
                '{SCALE_PLAN_ID}'::uuid,
                'scale',
                'Scale',
                99.99,
                999.00,
                83.25,
                17,
                3500,
                42000,
                0.0680,
                14,
                80,
                500.00,
                '["1,000 AI experiences","Dedicated support","Full API access","Advanced analytics","Priority speed","Custom widget branding"]'::jsonb,
                true,
                4,
                NOW(),
                NOW()
            )
        ON CONFLICT (name) DO UPDATE
        SET
            display_name = EXCLUDED.display_name,
            price_monthly = EXCLUDED.price_monthly,
            price_annual_total = EXCLUDED.price_annual_total,
            price_annual_per_month = EXCLUDED.price_annual_per_month,
            annual_discount_pct = EXCLUDED.annual_discount_pct,
            credits_monthly = EXCLUDED.credits_monthly,
            credits_annual = EXCLUDED.credits_annual,
            overage_usd_per_tryon = EXCLUDED.overage_usd_per_tryon,
            trial_days = EXCLUDED.trial_days,
            trial_credits = EXCLUDED.trial_credits,
            usage_cap_usd = EXCLUDED.usage_cap_usd,
            features = EXCLUDED.features,
            is_active = true,
            sort_order = EXCLUDED.sort_order,
            updated_at = NOW();
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE name IN ('professional', 'scale')")
