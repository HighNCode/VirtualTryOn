"""Add GCS object-path columns for photoshoot jobs and admin libraries

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-05-10 18:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("photoshoot_jobs", sa.Column("input1_object_path", sa.String(length=500), nullable=True))
    op.add_column("photoshoot_jobs", sa.Column("input2_object_path", sa.String(length=500), nullable=True))
    op.add_column("photoshoot_jobs", sa.Column("output_object_path", sa.String(length=500), nullable=True))

    op.add_column("photoshoot_models", sa.Column("object_path", sa.String(length=500), nullable=True))
    op.add_column("photoshoot_model_faces", sa.Column("object_path", sa.String(length=500), nullable=True))
    op.add_column("ghost_mannequin_refs", sa.Column("object_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("ghost_mannequin_refs", "object_path")
    op.drop_column("photoshoot_model_faces", "object_path")
    op.drop_column("photoshoot_models", "object_path")

    op.drop_column("photoshoot_jobs", "output_object_path")
    op.drop_column("photoshoot_jobs", "input2_object_path")
    op.drop_column("photoshoot_jobs", "input1_object_path")

