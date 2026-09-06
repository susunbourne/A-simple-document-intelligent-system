from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from src.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    document_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(128), nullable=False, default="default", index=True)
    ingestion_job_id = Column(String(36), nullable=True, unique=True, index=True)
    filename = Column(String, nullable=False)
    content_sha256 = Column(String, nullable=False, index=True)
    source_sha256 = Column(String(64), nullable=True, index=True)
    source_uri = Column(Text, nullable=True)
    pipeline_version = Column(String(64), nullable=True)
    router_model = Column(String(128), nullable=True)
    embedding_model = Column(String(128), nullable=True)
    extraction_model = Column(String(128), nullable=True)
    form_type = Column(String, nullable=False)
    router_confidence = Column(Float, nullable=True)
    processing_status = Column(String, nullable=False, default="processing")
    review_reason = Column(Text, nullable=True)
    review_version = Column(Integer, nullable=False, default=0)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_subject = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    job_id = Column(String(36), primary_key=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    request_id = Column(String(36), nullable=False, index=True)
    filename = Column(String, nullable=False)
    source_uri = Column(Text, nullable=False)
    source_sha256 = Column(String(64), nullable=False, index=True)
    source_size_bytes = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="queued", index=True)
    processing_stage = Column(String(32), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    lease_token = Column(String(36), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=True, index=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_ingestion_jobs_tenant_idempotency",
        ),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_pk = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=False, index=True)
    chunk_id = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_sha256 = Column(String, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    token_estimate = Column(Integer, nullable=False)
    section_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DocumentReviewDecision(Base):
    __tablename__ = "document_review_decisions"

    decision_id = Column(String(36), primary_key=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    actor_tenant_id = Column(String(64), nullable=False)
    actor_subject = Column(String(128), nullable=False, index=True)
    actor_role = Column(String(32), nullable=False)
    previous_status = Column(String(32), nullable=False)
    new_status = Column(String(32), nullable=False)
    corrections = Column(JSON, nullable=True)
    before_snapshot = Column(JSON, nullable=False)
    after_snapshot = Column(JSON, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
