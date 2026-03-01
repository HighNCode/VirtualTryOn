"""Extend photoshoot: merge studio_backgrounds, add faces + ghost refs

- Adds age + body_type columns to photoshoot_models
- Copies all studio_backgrounds rows into photoshoot_models
  (image_path is prefixed with "studio/" to keep serving from static/studio/)
- Re-points try_ons.studio_background_id FK → photoshoot_models.id
- Drops studio_backgrounds table
- Creates photoshoot_model_faces table
- Creates ghost_mannequin_refs table

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-02-22 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add age + body_type to photoshoot_models ──────────────────────────
    op.add_column('photoshoot_models', sa.Column('age', sa.String(10), nullable=True))
    op.add_column('photoshoot_models', sa.Column('body_type', sa.String(20), nullable=True))

    # ── 2. Copy studio_backgrounds → photoshoot_models ───────────────────────
    #    Prefix the stored image_path with "studio/" so the unified serve
    #    endpoint can open static/{image_path} correctly.
    op.execute("""
        INSERT INTO photoshoot_models
            (id, gender, image_path, is_active, created_at, updated_at)
        SELECT
            id,
            gender,
            'studio/' || image_path,
            is_active,
            created_at,
            updated_at
        FROM studio_backgrounds
        ON CONFLICT (id) DO NOTHING
    """)

    # ── 3. Re-point try_ons.studio_background_id FK ──────────────────────────
    op.drop_constraint('try_ons_studio_background_id_fkey', 'try_ons', type_='foreignkey')
    op.create_foreign_key(
        'try_ons_studio_background_id_fkey',
        'try_ons', 'photoshoot_models',
        ['studio_background_id'], ['id'],
        ondelete='SET NULL',
    )

    # ── 4. Drop studio_backgrounds table ─────────────────────────────────────
    op.drop_table('studio_backgrounds')

    # ── 5. Create photoshoot_model_faces ─────────────────────────────────────
    op.create_table(
        'photoshoot_model_faces',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('gender', sa.String(10), nullable=False),
        sa.Column('age', sa.String(10), nullable=True),
        sa.Column('skin_tone', sa.String(10), nullable=True),
        sa.Column('image_path', sa.String(300), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # ── 6. Create ghost_mannequin_refs ───────────────────────────────────────
    op.create_table(
        'ghost_mannequin_refs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clothing_type', sa.String(20), nullable=False),
        sa.Column('pose', sa.String(10), nullable=False),
        sa.Column('image_path', sa.String(300), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('idx_ghost_mannequin_refs_type', 'ghost_mannequin_refs', ['clothing_type'])


def downgrade() -> None:
    # Reverse in opposite order
    op.drop_index('idx_ghost_mannequin_refs_type', table_name='ghost_mannequin_refs')
    op.drop_table('ghost_mannequin_refs')
    op.drop_table('photoshoot_model_faces')

    # Re-create studio_backgrounds
    op.create_table(
        'studio_backgrounds',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('gender', sa.String(10), nullable=False),
        sa.Column('image_path', sa.String(300), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Move rows back (strip "studio/" prefix)
    op.execute("""
        INSERT INTO studio_backgrounds
            (id, gender, image_path, is_active, created_at, updated_at)
        SELECT
            id,
            gender,
            REPLACE(image_path, 'studio/', ''),
            is_active,
            created_at,
            updated_at
        FROM photoshoot_models
        WHERE image_path LIKE 'studio/%'
        ON CONFLICT (id) DO NOTHING
    """)

    # Remove migrated rows from photoshoot_models
    op.execute("DELETE FROM photoshoot_models WHERE image_path LIKE 'studio/%'")

    # Restore FK
    op.drop_constraint('try_ons_studio_background_id_fkey', 'try_ons', type_='foreignkey')
    op.create_foreign_key(
        'try_ons_studio_background_id_fkey',
        'try_ons', 'studio_backgrounds',
        ['studio_background_id'], ['id'],
    )

    op.drop_column('photoshoot_models', 'body_type')
    op.drop_column('photoshoot_models', 'age')
