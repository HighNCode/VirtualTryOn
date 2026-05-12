"""Add uninstall idempotency and consented research retention tables

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-05-12 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_data_deletion_queue_store",
        "data_deletion_queue",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "idx_data_deletion_queue_due",
        "data_deletion_queue",
        ["status", "scheduled_for"],
        unique=False,
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("delivery_id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("webhook_id", sa.String(length=120), nullable=False),
        sa.Column("shop_domain", sa.String(length=255), nullable=True),
        sa.Column("triggered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("delivery_id"),
        sa.UniqueConstraint("topic", "webhook_id", name="uq_webhook_delivery_topic_id"),
    )
    op.create_index(
        "idx_webhook_deliveries_topic_created",
        "webhook_deliveries",
        ["topic", "created_at"],
        unique=False,
    )

    op.create_table(
        "consented_research_datasets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_store_id", sa.UUID(), nullable=True),
        sa.Column("source_session_id", sa.UUID(), nullable=True),
        sa.Column("source_measurement_id", sa.UUID(), nullable=True),
        sa.Column("consent_granted_at", sa.DateTime(), nullable=False),
        sa.Column("consent_policy_version", sa.String(length=50), nullable=False),
        sa.Column("consent_source", sa.String(length=100), nullable=False),
        sa.Column("front_image_object_path", sa.String(length=500), nullable=False),
        sa.Column("side_image_object_path", sa.String(length=500), nullable=False),
        sa.Column("measurements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_research_dataset_expiry",
        "consented_research_datasets",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "idx_research_dataset_store_time",
        "consented_research_datasets",
        ["source_store_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_research_dataset_store_time", table_name="consented_research_datasets")
    op.drop_index("idx_research_dataset_expiry", table_name="consented_research_datasets")
    op.drop_table("consented_research_datasets")

    op.drop_index("idx_webhook_deliveries_topic_created", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index("idx_data_deletion_queue_due", table_name="data_deletion_queue")
    op.drop_index("idx_data_deletion_queue_store", table_name="data_deletion_queue")
