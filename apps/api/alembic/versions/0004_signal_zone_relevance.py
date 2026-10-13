"""signal zone and relevance

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("zone", sa.String(length=16), nullable=True))
    op.add_column("signals", sa.Column("relevance", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "relevance")
    op.drop_column("signals", "zone")
