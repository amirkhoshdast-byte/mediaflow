"""knowledge base: documents and embedded chunks

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_docs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("doc_type", sa.String(length=16), nullable=False),
        sa.Column("sensitivity", sa.String(length=16), nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("embed_provider", sa.String(length=32), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("doc_id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.ForeignKeyConstraint(["doc_id"], ["knowledge_docs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_doc_id", "knowledge_chunks", ["doc_id"])
    op.create_index(
        "ix_knowledge_chunks_embedding",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_docs")
