"""drop the knowledge base (removed from the product)

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_docs")


def downgrade() -> None:
    # Recreates the empty tables only; removed documents are not recoverable.
    op.create_table(
        "knowledge_docs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("doc_type", sa.String(length=16), nullable=False),
        sa.Column("sensitivity", sa.String(length=16), nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("embed_provider", sa.String(length=32), nullable=True),
        sa.Column("created_by", sa.String(length=32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("doc_id", sa.String(length=32), sa.ForeignKey("knowledge_docs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
