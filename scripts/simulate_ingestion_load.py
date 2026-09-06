import argparse
from datetime import datetime, timezone
import json
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.repositories.ingestion_repository import IngestionRepository
from src.services.object_store import StoredSource


def run_simulation(job_count: int) -> dict[str, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    source = StoredSource(
        uri="benchmark://synthetic-source",
        sha256="0" * 64,
        size_bytes=4096,
    )

    started = time.perf_counter()
    with session_factory() as db:
        repository = IngestionRepository(db)
        for index in range(job_count):
            repository.enqueue(
                tenant_id=f"tenant-{index % 10}",
                idempotency_key=f"synthetic-{index}",
                request_id=f"request-{index}",
                filename=f"document-{index}.pdf",
                source=source,
                max_attempts=1,
            )
    enqueue_seconds = time.perf_counter() - started

    started = time.perf_counter()
    claimed = 0
    with session_factory() as db:
        repository = IngestionRepository(db)
        while True:
            job = repository.claim_next(lease_seconds=30)
            if job is None:
                break
            repository.fail(
                job.job_id,
                job.lease_token,
                error_code="synthetic_terminal",
                error_message="Synthetic control-plane benchmark; no document content processed.",
                retryable=False,
                retry_base_seconds=0,
            )
            claimed += 1
    claim_seconds = time.perf_counter() - started

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": "sqlite_in_memory",
        "synthetic": True,
        "includes_file_parsing": False,
        "includes_model_calls": False,
        "job_count": job_count,
        "enqueued": job_count,
        "claimed": claimed,
        "enqueue_seconds": round(enqueue_seconds, 4),
        "enqueue_jobs_per_second": round(job_count / enqueue_seconds, 2),
        "claim_terminal_seconds": round(claim_seconds, 4),
        "claim_terminal_jobs_per_second": round(claimed / claim_seconds, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise the real ingestion state machine without parsing or paid model calls."
    )
    parser.add_argument("--jobs", type=int, default=1000)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    print(json.dumps(run_simulation(args.jobs), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
