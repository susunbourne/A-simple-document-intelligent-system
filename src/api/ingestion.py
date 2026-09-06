import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.logging import log_event
from src.db.session import get_db
from src.repositories.ingestion_repository import (
    IngestionJobNotFoundError,
    IngestionRepository,
    IngestionRetryRejectedError,
    IdempotencyConflictError,
)
from src.schemas.ingestion import IngestionJobResponse, IngestionQueueSummary
from src.services.auth import AuthorizedWorkspace, require_workspace_permission
from src.services.object_store import SourceTooLargeError, build_document_source_store


router = APIRouter()
logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg"}


@router.post("", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_document(
    file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    access: AuthorizedWorkspace = Depends(require_workspace_permission("document.ingest")),
    db: Session = Depends(get_db),
):
    tenant_id = access.workspace_id
    request_id = str(uuid4())
    filename = file.filename or ""
    extension = os.path.splitext(filename.lower())[1]
    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unsupported_file_type",
                "allowed_types": sorted(ALLOWED_EXTENSIONS),
                "request_id": request_id,
            },
        )
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 128:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_idempotency_key", "request_id": request_id},
        )

    store = build_document_source_store()
    await file.seek(0)
    try:
        source = store.put_stream(
            tenant_id,
            file.file,
            max_bytes=settings.MAX_UPLOAD_BYTES,
        )
    except SourceTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail={"code": "file_too_large", "request_id": request_id},
        ) from exc

    try:
        job, created = IngestionRepository(db).enqueue(
            tenant_id=tenant_id,
            idempotency_key=normalized_key,
            request_id=request_id,
            filename=filename,
            source=source,
            max_attempts=settings.INGESTION_MAX_ATTEMPTS,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "idempotency_conflict", "request_id": request_id},
        ) from exc
    log_event(
        logger,
        "ingestion_job_accepted",
        request_id=request_id,
        job_id=job.job_id,
        tenant_id=tenant_id,
        created=created,
        source_size_bytes=source.size_bytes,
    )
    return IngestionJobResponse.model_validate(job)


@router.get("/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(
    job_id: str,
    access: AuthorizedWorkspace = Depends(require_workspace_permission("document.read")),
    db: Session = Depends(get_db),
):
    tenant_id = access.workspace_id
    job = IngestionRepository(db).get(tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "ingestion_job_not_found"})
    return IngestionJobResponse.model_validate(job)


@router.post("/{job_id}/retry", response_model=IngestionJobResponse)
def retry_ingestion_job(
    job_id: str,
    access: AuthorizedWorkspace = Depends(require_workspace_permission("ingestion.retry")),
    db: Session = Depends(get_db),
):
    tenant_id = access.workspace_id
    try:
        job = IngestionRepository(db).retry_failed(tenant_id, job_id)
    except IngestionJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "ingestion_job_not_found"}) from exc
    except IngestionRetryRejectedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "ingestion_retry_rejected", "message": str(exc)},
        ) from exc
    return IngestionJobResponse.model_validate(job)


@router.get("/operations/summary", response_model=IngestionQueueSummary)
def ingestion_queue_summary(
    access: AuthorizedWorkspace = Depends(require_workspace_permission("operations.read")),
    db: Session = Depends(get_db),
):
    tenant_id = access.workspace_id
    summary = IngestionRepository(db).summary(tenant_id)
    return IngestionQueueSummary(
        tenant_id=tenant_id,
        counts=summary.counts,
        oldest_queued_at=summary.oldest_queued_at,
    )
