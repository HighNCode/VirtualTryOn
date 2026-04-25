"""Enforce DB-level cascades for customer-flow foreign keys

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-04-20 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_TARGETS = [
    # table, constrained_cols, referred_table, referred_cols
    ("analytics_events", ["store_id"], "stores", ["store_id"]),
    ("sessions", ["store_id"], "stores", ["store_id"]),
    ("sessions", ["product_id"], "products", ["product_id"]),
    ("user_measurements", ["session_id"], "sessions", ["session_id"]),
    ("try_ons", ["measurement_id"], "user_measurements", ["measurement_id"]),
    ("try_ons", ["product_id"], "products", ["product_id"]),
    ("try_ons", ["parent_try_on_id"], "try_ons", ["try_on_id"]),
    ("size_recommendations", ["measurement_id"], "user_measurements", ["measurement_id"]),
    ("size_recommendations", ["product_id"], "products", ["product_id"]),
]


def _find_fk(bind, table_name, constrained_cols, referred_table, referred_cols):
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (
            fk.get("constrained_columns") == constrained_cols
            and fk.get("referred_table") == referred_table
            and fk.get("referred_columns") == referred_cols
        ):
            return fk
    return None


def _replace_ondelete(bind, table_name, constrained_cols, referred_table, referred_cols, ondelete):
    fk = _find_fk(bind, table_name, constrained_cols, referred_table, referred_cols)
    if not fk:
        return

    current = (fk.get("options") or {}).get("ondelete")
    current_norm = current.upper() if isinstance(current, str) else None
    target_norm = ondelete.upper() if isinstance(ondelete, str) else None
    if current_norm == target_norm:
        return

    name = fk.get("name")
    if not name:
        return

    op.drop_constraint(name, table_name, type_="foreignkey")
    op.create_foreign_key(
        name,
        table_name,
        referred_table,
        constrained_cols,
        referred_cols,
        ondelete=ondelete,
    )


def upgrade() -> None:
    bind = op.get_bind()
    for table_name, constrained_cols, referred_table, referred_cols in FK_TARGETS:
        _replace_ondelete(
            bind,
            table_name,
            constrained_cols,
            referred_table,
            referred_cols,
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, constrained_cols, referred_table, referred_cols in FK_TARGETS:
        _replace_ondelete(
            bind,
            table_name,
            constrained_cols,
            referred_table,
            referred_cols,
            ondelete=None,
        )
