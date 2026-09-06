import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.errors import AppError, ErrorCode
from src.core.logging import log_event
from src.db.database import SessionLocal
from src.repositories.ingestion_repository import IngestionRepository
from src.services.object_store import (
    DocumentSourceStore,
    SourceObjectNotFoundError,
    build_document_source_store,
)
from src.workflows.statement_workflow import StatementWorkflow


logger = logging.getLogger(__name__)


NON_RETRYABLE_ERRORS = {
    ErrorCode.DOCUMENT_PARSE_FAILED,
    ErrorCode.ROUTER_LOW_CONFIDENCE,
    ErrorCode.UNSUPPORTED_DOCUMENT_TYPE,
    ErrorCode.VALIDATION_FAILED,
}


class IngestionWorker:
    def __init__(
        self,
        db: Session,
        *,
        source_store: DocumentSourceStore | None = None,
        workflow_factory=StatementWorkflow,
    ):
        self.db = db
        self.repository = IngestionRepository(db)
        self.source_store = source_store or build_document_source_store()
        self.workflow_factory = workflow_factory

    async def run_once(self) -> bool:
        job = self.repository.claim_next(
            lease_seconds=settings.INGESTION_LEASE_SECONDS,
        )
        if job is None:
            return False

        lease_token = str(job.lease_token)
        request_id = job.request_id or str(uuid4())
        log_event(
            logger,
            "ingestion_job_started",
            request_id=request_id,
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            attempt=job.attempt_count,
        )

        completed_document = self.repository.find_completed_document(job.job_id)
        if completed_document is not None:
            self.repository.complete(
                job.job_id,
                lease_token,
                completed_document.document_id,
            )
            return True

        try:
            file_bytes = self.source_store.read(job.source_uri)
            records = await self.workflow_factory(self.db).run_analysis_flow(
                file_bytes=file_bytes,
                filename=job.filename,
                request_id=request_id,
                tenant_id=job.tenant_id,
                ingestion_job_id=job.job_id,
                source_sha256=job.source_sha256,
                source_uri=job.source_uri,
                progress_callback=lambda stage: self._heartbeat(
                    job.job_id,
                    lease_token,
                    stage,
                ),
            )
            document_id = next(
                (
                    int(record.document_id)
                    for record in records
                    if getattr(record, "document_id", None) is not None
                ),
                None,
            )
            if document_id is None:
                document = self.repository.find_completed_document(job.job_id)
                document_id = document.document_id if document is not None else None
            if document_id is None:
                raise RuntimeError("Workflow completed without a durable document record.")
            self.repository.complete(job.job_id, lease_token, int(document_id))
            log_event(
                logger,
                "ingestion_job_completed",
                request_id=request_id,
                job_id=job.job_id,
                document_id=document_id,
            )
        except AppError as exc:
            self.db.rollback()
            self.repository.fail(
                job.job_id,
                lease_token,
                error_code=exc.code.value,
                error_message=exc.message,
                retryable=exc.code not in NON_RETRYABLE_ERRORS,
                retry_base_seconds=settings.INGESTION_RETRY_BASE_SECONDS,
            )
            log_event(
                logger,
                "ingestion_job_failed",
                request_id=request_id,
                job_id=job.job_id,
                error_code=exc.code.value,
            )
        except SourceObjectNotFoundError:
            self.db.rollback()
            self.repository.fail(
                job.job_id,
                lease_token,
                error_code="source_object_missing",
                error_message="The durable source object is unavailable.",
                retryable=False,
                retry_base_seconds=settings.INGESTION_RETRY_BASE_SECONDS,
            )
        except Exception as exc:
            self.db.rollback()
            self.repository.fail(
                job.job_id,
                lease_token,
                error_code="unexpected_worker_failure",
                error_message=type(exc).__name__,
                retryable=True,
                retry_base_seconds=settings.INGESTION_RETRY_BASE_SECONDS,
            )
            log_event(
                logger,
                "ingestion_job_failed",
                request_id=request_id,
                job_id=job.job_id,
                error_code="unexpected_worker_failure",
            )
        return True

    @staticmethod
    def _heartbeat(job_id: str, lease_token: str, stage: str) -> None:
        try:
            with SessionLocal() as heartbeat_db:
                IngestionRepository(heartbeat_db).renew_lease(
                    job_id,
                    lease_token,
                    stage=stage,
                    lease_seconds=settings.INGESTION_LEASE_SECONDS,
                )
        except Exception as exc:
            log_event(
                logger,
                "ingestion_heartbeat_failed",
                job_id=job_id,
                stage=stage,
                error_type=type(exc).__name__,
            )
