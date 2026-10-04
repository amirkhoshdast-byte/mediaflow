import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


def _id() -> Mapped[str]:
    return mapped_column(String(32), primary_key=True, default=new_id)


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = _id()
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    totp_secret_enc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ui_language: Mapped[str] = mapped_column(String(8), default="fa")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts()


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = _id()
    type: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(160))
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    domain: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()


class RawItem(Base):
    __tablename__ = "raw_items"
    id: Mapped[str] = _id()
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = _ts()


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[str] = _id()
    raw_item_id: Mapped[str] = mapped_column(ForeignKey("raw_items.id"))
    status: Mapped[str] = mapped_column(String(16), default="analyzing")
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    risk: Mapped[str | None] = mapped_column(String(16), nullable=True)
    approach: Mapped[str | None] = mapped_column(String(32), nullable=True)
    opportunity: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)  # -1..1
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts()

    raw_item: Mapped[RawItem] = relationship(lazy="joined")


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[str] = _id()
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8))
    persona: Mapped[str] = mapped_column(String(40))
    pillar: Mapped[str] = mapped_column(String(40))
    angle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generation_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parts: Mapped[list] = mapped_column(JSON)
    stage: Mapped[str] = mapped_column(String(16), default="draft")
    risk: Mapped[str] = mapped_column(String(16), default="medium")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DraftVersion(Base):
    __tablename__ = "draft_versions"
    id: Mapped[str] = _id()
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"), index=True)
    parts: Mapped[list] = mapped_column(JSON)
    author_type: Mapped[str] = mapped_column(String(8))  # human | ai
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = _ts()


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = _id()
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"), index=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_at_decision: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = _ts()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = _id()
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = _ts()


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[str] = _id()
    name: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    system_text: Mapped[str] = mapped_column(Text)
    user_template: Mapped[str] = mapped_column(Text)
    default_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = _ts()
