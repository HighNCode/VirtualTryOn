"""Add photo validation audit events

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-19 17:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "photo_validation_events",
        sa.Column("event_id", UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("pose_type", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pose_accuracy", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.String(length=20), nullable=False, server_default="low"),
        sa.Column("reasons_json", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metrics_json", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("image_meta_json", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "idx_photo_validation_store_time",
        "photo_validation_events",
        ["store_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_photo_validation_session_time",
        "photo_validation_events",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_photo_validation_status",
        "photo_validation_events",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_photo_validation_status", table_name="photo_validation_events")
    op.drop_index("idx_photo_validation_session_time", table_name="photo_validation_events")
    op.drop_index("idx_photo_validation_store_time", table_name="photo_validation_events")
    op.drop_table("photo_validation_events")
