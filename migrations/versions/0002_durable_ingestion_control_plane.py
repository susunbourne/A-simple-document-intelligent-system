"""durable ingestion control plane

Revision ID: 0002_ingestion
Revises: 0001_initial
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_ingestion"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("tenant_id", sa.String(length=128), server_default="default", nullable=False),
    )
    op.add_column("documents", sa.Column("ingestion_job_id", sa.String(length=36), nullable=True))
    op.add_column("documents", sa.Column("source_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("source_uri", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("pipeline_version", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("router_model", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("extraction_model", sa.String(length=128), nullable=True))
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_ingestion_job_id", "documents", ["ingestion_job_id"], unique=True)
    op.create_index("ix_documents_source_sha256", "documents", ["source_sha256"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("processing_stage", sa.String(length=32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("lease_token", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_ingestion_jobs_tenant_idempotency",
        ),
    )
    op.create_index("ix_ingestion_jobs_tenant_id", "ingestion_jobs", ["tenant_id"])
    op.create_index("ix_ingestion_jobs_request_id", "ingestion_jobs", ["request_id"])
    op.create_index("ix_ingestion_jobs_source_sha256", "ingestion_jobs", ["source_sha256"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("ix_ingestion_jobs_lease_expires_at", "ingestion_jobs", ["lease_expires_at"])
    op.create_index("ix_ingestion_jobs_next_attempt_at", "ingestion_jobs", ["next_attempt_at"])
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_documents_source_sha256", table_name="documents")
    op.drop_index("ix_documents_ingestion_job_id", table_name="documents")
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    op.drop_column("documents", "source_uri")
    op.drop_column("documents", "extraction_model")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "router_model")
    op.drop_column("documents", "pipeline_version")
    op.drop_column("documents", "source_sha256")
    op.drop_column("documents", "ingestion_job_id")
    op.drop_column("documents", "tenant_id")
