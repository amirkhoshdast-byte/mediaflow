"""source fetch state and gdelt query

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("query", sa.String(length=500), nullable=True))
    op.add_column("sources", sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "last_error")
    op.drop_column("sources", "last_fetched_at")
    op.drop_column("sources", "query")
