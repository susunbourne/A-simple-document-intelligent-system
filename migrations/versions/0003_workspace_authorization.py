"""workspace authorization

Revision ID: 0003_authz
Revises: 0002_ingestion
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_authz"
down_revision: Union[str, None] = "0002_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_workspaces",
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_index("ix_data_workspaces_status", "data_workspaces", ["status"])
    op.create_table(
        "workspace_memberships",
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("identity_tenant_id", sa.String(length=64), nullable=False),
        sa.Column("identity_subject", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["data_workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "identity_tenant_id",
            "identity_subject",
            name="uq_workspace_membership_identity",
        ),
    )
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"])
    op.create_index("ix_workspace_memberships_identity_subject", "workspace_memberships", ["identity_subject"])


def downgrade() -> None:
    op.drop_table("workspace_memberships")
    op.drop_table("data_workspaces")
