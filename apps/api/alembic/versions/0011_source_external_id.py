"""source external id (resolved X user id)

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("external_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "external_id")
