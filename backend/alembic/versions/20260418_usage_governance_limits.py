"""Usage governance: weekly limits, cycle accounting, and billing metadata

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-18 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # stores: billing metadata + usage capability
    op.add_column("stores", sa.Column("subscription_status", sa.String(length=20), nullable=True))
    op.add_column("stores", sa.Column("billing_cycle_start_at", sa.DateTime(), nullable=True))
    op.add_column("stores", sa.Column("billing_cycle_end_at", sa.DateTime(), nullable=True))
    op.add_column("stores", sa.Column("billing_status_synced_at", sa.DateTime(), nullable=True))
    op.add_column("stores", sa.Column("store_timezone", sa.String(length=64), nullable=True))
    op.add_column("stores", sa.Column("has_usage_billing", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("stores", sa.Column("usage_line_item_id", sa.String(length=255), nullable=True))

    # widget config: merchant weekly limit
    op.add_column(
        "widget_configs",
        sa.Column("weekly_tryon_limit", sa.Integer(), server_default="10", nullable=False),
    )

    # plans: configurable Shopify usage cap
    op.add_column(
        "plans",
        sa.Column("usage_cap_usd", sa.Numeric(10, 2), server_default="500.00", nullable=False),
    )

    # usage event ledger
    op.create_table(
        "usage_events",
        sa.Column("event_id", UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_identifier", sa.String(length=255), nullable=True),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="reserved"),
        sa.Column("reserved_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overage_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overage_amount_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("usage_charge_id", sa.String(length=255), nullable=True),
        sa.Column("billing_error_code", sa.String(length=50), nullable=True),
        sa.Column("billing_error_message", sa.Text(), nullable=True),
        sa.Column("reference_type", sa.String(length=50), nullable=False),
        sa.Column("reference_id", sa.String(length=255), nullable=True),
        sa.Column("week_start_utc", sa.DateTime(), nullable=True),
        sa.Column("cycle_start_at", sa.DateTime(), nullable=True),
        sa.Column("cycle_end_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("idx_usage_events_store_time", "usage_events", ["store_id", "created_at"], unique=False)
    op.create_index("idx_usage_events_status", "usage_events", ["status"], unique=False)
    op.create_index("idx_usage_events_ref", "usage_events", ["reference_type", "reference_id"], unique=False)

    # weekly customer counters
    op.create_table(
        "usage_customer_weeks",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_identifier", sa.String(length=255), nullable=False),
        sa.Column("week_start_utc", sa.DateTime(), nullable=False),
        sa.Column("week_end_utc", sa.DateTime(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "customer_identifier", "week_start_utc", name="uq_usage_customer_week"),
    )
    op.create_index(
        "idx_usage_customer_weeks_store_week",
        "usage_customer_weeks",
        ["store_id", "week_start_utc"],
        unique=False,
    )

    # cycle aggregates
    op.create_table(
        "usage_store_cycles",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_start_at", sa.DateTime(), nullable=False),
        sa.Column("cycle_end_at", sa.DateTime(), nullable=False),
        sa.Column("included_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overage_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overage_amount_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("overage_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("overage_block_reason", sa.String(length=80), nullable=True),
        sa.Column("overage_block_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "cycle_start_at", "cycle_end_at", name="uq_usage_store_cycle"),
    )
    op.create_index("idx_usage_store_cycles_store_end", "usage_store_cycles", ["store_id", "cycle_end_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_usage_store_cycles_store_end", table_name="usage_store_cycles")
    op.drop_table("usage_store_cycles")

    op.drop_index("idx_usage_customer_weeks_store_week", table_name="usage_customer_weeks")
    op.drop_table("usage_customer_weeks")

    op.drop_index("idx_usage_events_ref", table_name="usage_events")
    op.drop_index("idx_usage_events_status", table_name="usage_events")
    op.drop_index("idx_usage_events_store_time", table_name="usage_events")
    op.drop_table("usage_events")

    op.drop_column("plans", "usage_cap_usd")
    op.drop_column("widget_configs", "weekly_tryon_limit")

    op.drop_column("stores", "usage_line_item_id")
    op.drop_column("stores", "has_usage_billing")
    op.drop_column("stores", "store_timezone")
    op.drop_column("stores", "billing_status_synced_at")
    op.drop_column("stores", "billing_cycle_end_at")
    op.drop_column("stores", "billing_cycle_start_at")
    op.drop_column("stores", "subscription_status")
