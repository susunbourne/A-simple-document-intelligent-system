"""auditable human review decisions

Revision ID: 0004_review
Revises: 0003_authz
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_review"
down_revision: Union[str, None] = "0003_authz"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("review_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("documents", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("reviewed_by_subject", sa.String(length=128), nullable=True))
    op.create_table(
        "document_review_decisions",
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_tenant_id", sa.String(length=64), nullable=False),
        sa.Column("actor_subject", sa.String(length=128), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=False),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("corrections", sa.JSON(), nullable=True),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index(
        "ix_document_review_decisions_tenant_id",
        "document_review_decisions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_document_review_decisions_document_id",
        "document_review_decisions",
        ["document_id"],
    )
    op.create_index(
        "ix_document_review_decisions_actor_subject",
        "document_review_decisions",
        ["actor_subject"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_review_decisions_actor_subject",
        table_name="document_review_decisions",
    )
    op.drop_index(
        "ix_document_review_decisions_document_id",
        table_name="document_review_decisions",
    )
    op.drop_index(
        "ix_document_review_decisions_tenant_id",
        table_name="document_review_decisions",
    )
    op.drop_table("document_review_decisions")
    op.drop_column("documents", "reviewed_by_subject")
    op.drop_column("documents", "reviewed_at")
    op.drop_column("documents", "review_version")
