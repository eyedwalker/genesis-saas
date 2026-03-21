"""SQLAlchemy ORM models — ported from wabah Prisma schema (Genesis models)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import JSON as _JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Use PostgreSQL JSONB when available, fall back to generic JSON (for SQLite tests)
try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = _JSON  # type: ignore[assignment,misc]


def _cuid() -> str:
    return uuid.uuid4().hex[:25]


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map = {dict[str, Any]: _JSON}


# ── Tenant (new for SaaS) ─────────────────────────────────────────────────────


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    credits_used: Mapped[float] = mapped_column(Float, default=0.0)
    credits_limit: Mapped[float] = mapped_column(Float, default=50.0)
    max_concurrent_builds: Mapped[int] = mapped_column(Integer, default=3)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    users: Mapped[list[TenantUser]] = relationship(back_populates="tenant")
    factories: Mapped[list[Factory]] = relationship(back_populates="tenant")
    assistants: Mapped[list[Assistant]] = relationship(back_populates="tenant")


# ── User ───────────────────────────────────────────────────────────────────────


class TenantUser(Base):
    __tablename__ = "tenant_users"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), default="")
    hashed_password: Mapped[str] = mapped_column(String(255), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenant: Mapped[Tenant] = relationship(back_populates="users")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_tenant_user_email"),
        Index("ix_tenant_users_tenant", "tenant_id"),
    )


# ── Factory ────────────────────────────────────────────────────────────────────


class Factory(Base):
    __tablename__ = "factories"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="setup")
    fast_track: Mapped[bool] = mapped_column(Boolean, default=False)
    interview_data: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    guardrails: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    export_templates: Mapped[dict[str, Any] | None] = mapped_column(
        _JSON, nullable=True
    )
    github_repo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    tenant: Mapped[Tenant] = relationship(back_populates="factories")
    builds: Mapped[list[Build]] = relationship(back_populates="factory")
    members: Mapped[list[FactoryMember]] = relationship(back_populates="factory")
    invitations: Mapped[list[Invitation]] = relationship(back_populates="factory")
    deployments: Mapped[list[Deployment]] = relationship(
        back_populates="factory", foreign_keys="Deployment.factory_id"
    )

    __table_args__ = (
        Index("ix_factories_tenant", "tenant_id"),
        Index("ix_factories_status", "status"),
    )


# ── Factory Member ─────────────────────────────────────────────────────────────


class FactoryMember(Base):
    __tablename__ = "factory_members"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("tenant_users.id"))
    role: Mapped[str] = mapped_column(String(20), default="reviewer")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    factory: Mapped[Factory] = relationship(back_populates="members")
    user: Mapped[TenantUser] = relationship()

    __table_args__ = (
        UniqueConstraint("factory_id", "user_id", name="uq_factory_member"),
        Index("ix_factory_members_factory", "factory_id"),
    )


# ── Build ──────────────────────────────────────────────────────────────────────


class Build(Base):
    __tablename__ = "builds"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.id"))
    requested_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("tenant_users.id"), nullable=True
    )
    feature_request: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="requirements")
    # Pipeline stage data (JSON blobs)
    interview_log: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    requirements_data: Mapped[dict[str, Any] | None] = mapped_column(
        _JSON, nullable=True
    )
    design_data: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    design_brief: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    plan: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_map: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    original_file_map: Mapped[dict[str, Any] | None] = mapped_column(
        _JSON, nullable=True
    )
    # Review
    vibe_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vibe_grade: Mapped[str | None] = mapped_column(String(5), nullable=True)
    findings: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    # Lineage
    parent_build_id: Mapped[str | None] = mapped_column(
        ForeignKey("builds.id"), nullable=True
    )
    refine_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Export
    exported_repo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exported_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Agent provisioning
    workspace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provisioned_agents: Mapped[dict[str, Any] | None] = mapped_column(
        _JSON, nullable=True
    )
    build_mode: Mapped[str] = mapped_column(String(20), default="feature")
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    factory: Mapped[Factory] = relationship(back_populates="builds")
    requested_by: Mapped[TenantUser | None] = relationship()
    parent_build: Mapped[Build | None] = relationship(
        remote_side="Build.id", foreign_keys=[parent_build_id]
    )
    approvals: Mapped[list[Approval]] = relationship(back_populates="build")
    comments: Mapped[list[BuildComment]] = relationship(back_populates="build")
    work_items: Mapped[list[WorkItem]] = relationship(back_populates="build")
    documents: Mapped[list[Document]] = relationship(back_populates="build")
    activities: Mapped[list[Activity]] = relationship(back_populates="build")
    build_deployments: Mapped[list[Deployment]] = relationship(
        back_populates="build", foreign_keys="Deployment.build_id"
    )

    __table_args__ = (
        Index("ix_builds_factory", "factory_id"),
        Index("ix_builds_status", "status"),
    )


# ── Approval ───────────────────────────────────────────────────────────────────


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("tenant_users.id"))
    type: Mapped[str] = mapped_column(String(20))
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    build: Mapped[Build] = relationship(back_populates="approvals")
    user: Mapped[TenantUser] = relationship()

    __table_args__ = (
        UniqueConstraint("build_id", "user_id", "type", name="uq_approval"),
        Index("ix_approvals_build", "build_id"),
    )


# ── Build Comment ──────────────────────────────────────────────────────────────


class BuildComment(Base):
    __tablename__ = "build_comments"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("tenant_users.id"))
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("build_comments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    build: Mapped[Build] = relationship(back_populates="comments")
    user: Mapped[TenantUser] = relationship()
    parent: Mapped[BuildComment | None] = relationship(
        remote_side="BuildComment.id", foreign_keys=[parent_id]
    )

    __table_args__ = (
        Index("ix_build_comments_build", "build_id"),
        Index("ix_build_comments_parent", "parent_id"),
    )


# ── Activity ───────────────────────────────────────────────────────────────────


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id"))
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("tenant_users.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(50))
    stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", _JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    build: Mapped[Build] = relationship(back_populates="activities")
    user: Mapped[TenantUser | None] = relationship()

    __table_args__ = (
        Index("ix_activities_build", "build_id"),
        Index("ix_activities_build_time", "build_id", "created_at"),
    )


# ── Work Item ──────────────────────────────────────────────────────────────────


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id"))
    type: Mapped[str] = mapped_column(String(30))
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("work_items.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(
        ForeignKey("tenant_users.id"), nullable=True
    )
    estimate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", _JSON, nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    build: Mapped[Build] = relationship(back_populates="work_items")
    parent: Mapped[WorkItem | None] = relationship(
        remote_side="WorkItem.id", foreign_keys=[parent_id]
    )
    assignee: Mapped[TenantUser | None] = relationship()

    __table_args__ = (
        Index("ix_work_items_build", "build_id"),
        Index("ix_work_items_build_type", "build_id", "type"),
    )


# ── Document ───────────────────────────────────────────────────────────────────


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id"))
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(20), default="markdown")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    build: Mapped[Build] = relationship(back_populates="documents")

    __table_args__ = (
        Index("ix_documents_build", "build_id"),
        Index("ix_documents_build_type", "build_id", "type"),
    )


# ── Deployment ─────────────────────────────────────────────────────────────────


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id"))
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.id"))
    tier: Mapped[str] = mapped_column(String(20), default="shared")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    app_slug: Mapped[str] = mapped_column(String(100), unique=True)
    subdomain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    container_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    host_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # AWS fields
    ecr_image_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amplify_app_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    s3_bucket_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cloudfront_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Health
    health_check_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    deploy_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    build: Mapped[Build] = relationship(
        back_populates="build_deployments", foreign_keys=[build_id]
    )
    factory: Mapped[Factory] = relationship(
        back_populates="deployments", foreign_keys=[factory_id]
    )

    __table_args__ = (
        Index("ix_deployments_build", "build_id"),
        Index("ix_deployments_factory", "factory_id"),
        Index("ix_deployments_status", "status"),
    )


# ── Invitation ─────────────────────────────────────────────────────────────────


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.id"))
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="reviewer")
    token: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    invited_by: Mapped[str] = mapped_column(ForeignKey("tenant_users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    factory: Mapped[Factory] = relationship(back_populates="invitations")
    inviter: Mapped[TenantUser] = relationship()

    __table_args__ = (
        UniqueConstraint("factory_id", "email", name="uq_invitation_email"),
        Index("ix_invitations_token", "token"),
    )


# ── Assistant ──────────────────────────────────────────────────────────────────


class Assistant(Base):
    __tablename__ = "assistants"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=_cuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    patterns: Mapped[dict[str, Any]] = mapped_column(_JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tenant: Mapped[Tenant] = relationship(back_populates="assistants")

    __table_args__ = (
        Index("ix_assistants_tenant", "tenant_id"),
        Index("ix_assistants_tenant_domain", "tenant_id", "domain"),
    )
