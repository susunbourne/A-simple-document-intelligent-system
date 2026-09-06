from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.document import Document, IngestionJob
from src.services.object_store import StoredSource


class IngestionJobNotFoundError(LookupError):
    pass


class IngestionLeaseLostError(RuntimeError):
    pass


class IngestionRetryRejectedError(RuntimeError):
    pass


class IdempotencyConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueueSummary:
    counts: dict[str, int]
    oldest_queued_at: datetime | None


class IngestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        request_id: str,
        filename: str,
        source: StoredSource,
        max_attempts: int,
    ) -> tuple[IngestionJob, bool]:
        existing = self.get_by_idempotency_key(tenant_id, idempotency_key)
        if existing is not None:
            if existing.source_sha256 != source.sha256:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for different source content."
                )
            return existing, False

        job = IngestionJob(
            job_id=str(uuid4()),
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_id=request_id,
            filename=filename,
            source_uri=source.uri,
            source_sha256=source.sha256,
            source_size_bytes=source.size_bytes,
            status="queued",
            attempt_count=0,
            max_attempts=max_attempts,
        )
        self.db.add(job)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_idempotency_key(tenant_id, idempotency_key)
            if existing is None:
                raise
            if existing.source_sha256 != source.sha256:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for different source content."
                )
            return existing, False
        self.db.refresh(job)
        return job, True

    def get(self, tenant_id: str, job_id: str) -> IngestionJob | None:
        return (
            self.db.query(IngestionJob)
            .filter(
                IngestionJob.tenant_id == tenant_id,
                IngestionJob.job_id == job_id,
            )
            .first()
        )

    def get_by_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> IngestionJob | None:
        return (
            self.db.query(IngestionJob)
            .filter(
                IngestionJob.tenant_id == tenant_id,
                IngestionJob.idempotency_key == idempotency_key,
            )
            .first()
        )

    def claim_next(
        self,
        *,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> IngestionJob | None:
        now = now or datetime.now(timezone.utc)
        eligible = or_(
            IngestionJob.status == "queued",
            (
                (IngestionJob.status == "retry_wait")
                & or_(
                    IngestionJob.next_attempt_at.is_(None),
                    IngestionJob.next_attempt_at <= now,
                )
            ),
            (
                (IngestionJob.status == "processing")
                & (IngestionJob.lease_expires_at <= now)
            ),
        )
        job = (
            self.db.query(IngestionJob)
            .filter(eligible, IngestionJob.attempt_count < IngestionJob.max_attempts)
            .order_by(IngestionJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if job is None:
            self.db.rollback()
            return None

        job.status = "processing"
        job.processing_stage = "claimed"
        job.attempt_count += 1
        job.lease_token = str(uuid4())
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.next_attempt_at = None
        job.error_code = None
        job.error_message = None
        self.db.commit()
        self.db.refresh(job)
        return job

    def renew_lease(
        self,
        job_id: str,
        lease_token: str,
        *,
        stage: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(timezone.utc)
        job = self._leased_job(job_id, lease_token)
        job.processing_stage = stage[:32]
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        self.db.commit()

    def complete(self, job_id: str, lease_token: str, document_id: int) -> IngestionJob:
        job = self._leased_job(job_id, lease_token)
        job.status = "completed"
        job.processing_stage = "completed"
        job.document_id = document_id
        job.lease_token = None
        job.lease_expires_at = None
        job.next_attempt_at = None
        self.db.commit()
        self.db.refresh(job)
        return job

    def fail(
        self,
        job_id: str,
        lease_token: str,
        *,
        error_code: str,
        error_message: str,
        retryable: bool,
        retry_base_seconds: int,
        now: datetime | None = None,
    ) -> IngestionJob:
        now = now or datetime.now(timezone.utc)
        job = self._leased_job(job_id, lease_token)
        can_retry = retryable and job.attempt_count < job.max_attempts
        if can_retry:
            backoff_seconds = retry_base_seconds * (2 ** max(0, job.attempt_count - 1))
            job.status = "retry_wait"
            job.next_attempt_at = now + timedelta(seconds=backoff_seconds)
        else:
            job.status = "failed"
            job.next_attempt_at = None
        job.error_code = error_code[:80]
        job.processing_stage = "retry_wait" if can_retry else "failed"
        job.error_message = error_message[:500]
        job.lease_token = None
        job.lease_expires_at = None
        self.db.commit()
        self.db.refresh(job)
        return job

    def retry_failed(self, tenant_id: str, job_id: str) -> IngestionJob:
        job = self.get(tenant_id, job_id)
        if job is None:
            raise IngestionJobNotFoundError(job_id)
        if job.status != "failed":
            raise IngestionRetryRejectedError(
                f"Only failed jobs can be retried; current status is {job.status}."
            )
        job.status = "queued"
        job.processing_stage = None
        job.attempt_count = 0
        job.error_code = None
        job.error_message = None
        job.next_attempt_at = None
        self.db.commit()
        self.db.refresh(job)
        return job

    def find_completed_document(self, job_id: str) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.ingestion_job_id == job_id,
                Document.processing_status.in_(["completed", "needs_review"]),
            )
            .first()
        )

    def summary(self, tenant_id: str) -> QueueSummary:
        rows = (
            self.db.query(IngestionJob.status, IngestionJob.created_at)
            .filter(IngestionJob.tenant_id == tenant_id)
            .all()
        )
        counts = Counter(status for status, _created_at in rows)
        queued_times = [
            created_at
            for status, created_at in rows
            if status in {"queued", "retry_wait"}
        ]
        return QueueSummary(
            counts=dict(sorted(counts.items())),
            oldest_queued_at=min(queued_times) if queued_times else None,
        )

    def _leased_job(self, job_id: str, lease_token: str) -> IngestionJob:
        job = (
            self.db.query(IngestionJob)
            .filter(
                IngestionJob.job_id == job_id,
                IngestionJob.status == "processing",
                IngestionJob.lease_token == lease_token,
            )
            .first()
        )
        if job is None:
            self.db.rollback()
            raise IngestionLeaseLostError(job_id)
        return job
