"""tone reviews

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tone_reviews",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("draft_id", sa.String(length=32), nullable=False),
        sa.Column("parts_hash", sa.String(length=64), nullable=False),
        sa.Column("parts_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("suggested_parts", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tone_reviews_draft_id", "tone_reviews", ["draft_id"])


def downgrade() -> None:
    op.drop_table("tone_reviews")
