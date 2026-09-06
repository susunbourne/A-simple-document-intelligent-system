from datetime import datetime

from pydantic import BaseModel


class IngestionJobResponse(BaseModel):
    job_id: str
    tenant_id: str
    idempotency_key: str
    filename: str
    source_sha256: str
    source_size_bytes: int
    status: str
    processing_stage: str | None = None
    attempt_count: int
    max_attempts: int
    document_id: int | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IngestionQueueSummary(BaseModel):
    tenant_id: str
    counts: dict[str, int]
    oldest_queued_at: datetime | None = None
