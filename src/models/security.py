from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from src.db.database import Base


class DataWorkspace(Base):
    __tablename__ = "data_workspaces"

    workspace_id = Column(String(128), primary_key=True)
    display_name = Column(String(200), nullable=False)
    status = Column(String(32), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"

    membership_id = Column(Integer, primary_key=True)
    workspace_id = Column(
        String(128),
        ForeignKey("data_workspaces.workspace_id"),
        nullable=False,
        index=True,
    )
    identity_tenant_id = Column(String(64), nullable=False)
    identity_subject = Column(String(128), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "identity_tenant_id",
            "identity_subject",
            name="uq_workspace_membership_identity",
        ),
    )
