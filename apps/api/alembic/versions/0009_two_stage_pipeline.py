"""two-stage pipeline: the separate review stage is gone

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drafts that waited in review go back to editing; the tone review now runs on its own.
    op.execute("UPDATE drafts SET stage = 'draft' WHERE stage = 'tone_review'")


def downgrade() -> None:
    pass  # nothing to restore: the stage no longer exists
