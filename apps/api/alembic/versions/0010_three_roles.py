"""three roles: owner, assistant, sysadmin

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # An installation always needs someone who can decide: with no owner yet, the oldest
    # system administrator becomes the owner.
    op.execute(
        "UPDATE users SET role = 'owner' WHERE id = ("
        "SELECT id FROM users WHERE role = 'sysadmin' ORDER BY created_at LIMIT 1) "
        "AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'owner')"
    )
    op.execute("UPDATE users SET role = 'owner' WHERE role IN ('diplomatic_editor', 'president_office')")
    op.execute(
        "UPDATE users SET role = 'assistant' WHERE role IN "
        "('trend_analyst', 'media_monitor', 'ai_operator', 'content_lead', 'narrative_strategist')"
    )


def downgrade() -> None:
    pass  # the old roles cannot be reconstructed from the new ones
