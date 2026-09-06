"""initial document intelligence schema

Revision ID: 0001_initial
Revises: None
Create Date: 2026-09-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("content_sha256", sa.String(), nullable=False),
        sa.Column("form_type", sa.String(), nullable=False),
        sa.Column("router_confidence", sa.Float(), nullable=True),
        sa.Column("processing_status", sa.String(), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(op.f("ix_documents_content_sha256"), "documents", ["content_sha256"])
    op.create_index(op.f("ix_documents_document_id"), "documents", ["document_id"])

    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=True),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("user_email"),
        sa.UniqueConstraint("user_name"),
    )
    op.create_index(op.f("ix_users_user_id"), "users", ["user_id"])

    op.create_table(
        "document_chunks",
        sa.Column("chunk_pk", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("section_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("chunk_pk"),
    )
    op.create_index(op.f("ix_document_chunks_chunk_pk"), "document_chunks", ["chunk_pk"])
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"])

    op.create_table(
        "athlete_contracts",
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("contract_name", sa.String(), nullable=True),
        sa.Column("party_a", sa.String(), nullable=True),
        sa.Column("party_b", sa.String(), nullable=True),
        sa.Column("effective_date", sa.String(), nullable=True),
        sa.Column("expiration_date", sa.String(), nullable=True),
        sa.Column("contract_value", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("processing_status", sa.String(), nullable=False),
        sa.Column("source_chunk_ids", sa.Text(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("router_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("contract_id"),
    )
    op.create_index(op.f("ix_athlete_contracts_contract_id"), "athlete_contracts", ["contract_id"])
    op.create_index(op.f("ix_athlete_contracts_document_id"), "athlete_contracts", ["document_id"])

    op.create_table(
        "bank_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("transaction_date", sa.String(), nullable=True),
        sa.Column("processing_status", sa.String(), nullable=False),
        sa.Column("source_chunk_ids", sa.Text(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("router_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bank_statements_document_id"), "bank_statements", ["document_id"])
    op.create_index(op.f("ix_bank_statements_id"), "bank_statements", ["id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_bank_statements_id"), table_name="bank_statements")
    op.drop_index(op.f("ix_bank_statements_document_id"), table_name="bank_statements")
    op.drop_table("bank_statements")
    op.drop_index(op.f("ix_athlete_contracts_document_id"), table_name="athlete_contracts")
    op.drop_index(op.f("ix_athlete_contracts_contract_id"), table_name="athlete_contracts")
    op.drop_table("athlete_contracts")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_chunk_pk"), table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index(op.f("ix_users_user_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_documents_document_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_content_sha256"), table_name="documents")
    op.drop_table("documents")
