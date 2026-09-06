import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.config import settings
from src.api.ingestion import router as ingestion_router
from src.db.database import Base
from src.db.session import get_db
from src.models.document import Document
from src.models.security import DataWorkspace, WorkspaceMembership
from src.repositories.ingestion_repository import (
    IdempotencyConflictError,
    IngestionLeaseLostError,
    IngestionRepository,
)
from src.services.ingestion_service import IngestionWorker
from src.services.object_store import LocalDocumentSourceStore, SourceTooLargeError
from src.services.object_store import AzureBlobDocumentSourceStore


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def enqueue(repository, source, *, tenant="finance", key="upload-1", attempts=3):
    return repository.enqueue(
        tenant_id=tenant,
        idempotency_key=key,
        request_id="request-1",
        filename="statement.pdf",
        source=source,
        max_attempts=attempts,
    )


def test_source_store_streams_content_addressed_objects_and_enforces_limit(tmp_path):
    store = LocalDocumentSourceStore(tmp_path)
    first = store.put_stream("tenant-a", BytesIO(b"same bytes"), max_bytes=100)
    second = store.put_stream("tenant-a", BytesIO(b"same bytes"), max_bytes=100)

    assert first == second
    assert store.read(first.uri) == b"same bytes"
    assert len(list(tmp_path.rglob(first.sha256))) == 1

    with pytest.raises(SourceTooLargeError):
        store.put_stream("tenant-a", BytesIO(b"too large"), max_bytes=3)


class FakeDownload:
    def __init__(self, payload):
        self.payload = payload

    def readall(self):
        return self.payload


class FakeBlobClient:
    def __init__(self, objects, key):
        self.objects = objects
        self.key = key

    def upload_blob(self, stream, overwrite=False):
        if self.key in self.objects and not overwrite:
            class ResourceExistsError(Exception):
                pass

            raise ResourceExistsError()
        self.objects[self.key] = stream.read()


class FakeContainerClient:
    def __init__(self):
        self.objects = {}

    def get_blob_client(self, key):
        return FakeBlobClient(self.objects, key)

    def download_blob(self, key):
        return FakeDownload(self.objects[key])

    def delete_blob(self, key, delete_snapshots=None):
        self.objects.pop(key, None)


class FakeBlobServiceClient:
    def __init__(self):
        self.container = FakeContainerClient()

    def get_container_client(self, _container):
        return self.container


def test_azure_store_uses_tenant_scoped_content_addressed_blob_keys():
    client = FakeBlobServiceClient()
    store = AzureBlobDocumentSourceStore(
        "https://example.blob.core.windows.net",
        "sources",
        service_client=client,
    )

    first = store.put_stream("tenant-a", BytesIO(b"same bytes"), max_bytes=100)
    repeated = store.put_stream("tenant-a", BytesIO(b"same bytes"), max_bytes=100)
    other = store.put_stream("tenant-b", BytesIO(b"same bytes"), max_bytes=100)

    assert first == repeated
    assert first.uri != other.uri
    assert store.read(first.uri) == b"same bytes"
    assert len(client.container.objects) == 2


def test_enqueue_is_idempotent_within_tenant_but_isolated_between_tenants(db, tmp_path):
    source = LocalDocumentSourceStore(tmp_path).put_stream(
        "finance", BytesIO(b"document"), max_bytes=100
    )
    repository = IngestionRepository(db)

    first, first_created = enqueue(repository, source)
    repeated, repeated_created = enqueue(repository, source)
    other_tenant, other_created = enqueue(repository, source, tenant="legal")

    assert first_created is True
    assert repeated_created is False
    assert repeated.job_id == first.job_id
    assert other_created is True
    assert other_tenant.job_id != first.job_id
    assert repository.get("legal", first.job_id) is None


def test_idempotency_key_rejects_different_source_content(db, tmp_path):
    store = LocalDocumentSourceStore(tmp_path)
    first_source = store.put_stream("finance", BytesIO(b"first"), max_bytes=100)
    second_source = store.put_stream("finance", BytesIO(b"second"), max_bytes=100)
    repository = IngestionRepository(db)
    enqueue(repository, first_source)

    with pytest.raises(IdempotencyConflictError):
        enqueue(repository, second_source)


def test_expired_worker_lease_is_recovered_and_stale_worker_cannot_publish(db, tmp_path):
    source = LocalDocumentSourceStore(tmp_path).put_stream(
        "finance", BytesIO(b"document"), max_bytes=100
    )
    repository = IngestionRepository(db)
    job, _created = enqueue(repository, source)
    started = datetime.now(timezone.utc)

    first_claim = repository.claim_next(lease_seconds=1, now=started)
    stale_token = first_claim.lease_token
    recovered = repository.claim_next(
        lease_seconds=30,
        now=started + timedelta(seconds=2),
    )

    assert recovered.job_id == job.job_id
    assert recovered.attempt_count == 2
    assert recovered.lease_token != stale_token
    with pytest.raises(IngestionLeaseLostError):
        repository.complete(job.job_id, stale_token, document_id=123)


def test_worker_heartbeat_extends_lease_and_records_stage(db, tmp_path):
    source = LocalDocumentSourceStore(tmp_path).put_stream(
        "finance", BytesIO(b"document"), max_bytes=100
    )
    repository = IngestionRepository(db)
    job, _created = enqueue(repository, source)
    started = datetime.now(timezone.utc)
    claimed = repository.claim_next(lease_seconds=1, now=started)

    repository.renew_lease(
        claimed.job_id,
        claimed.lease_token,
        stage="extracting",
        lease_seconds=60,
        now=started,
    )
    renewed = repository.get("finance", job.job_id)

    assert renewed.processing_stage == "extracting"
    assert renewed.lease_expires_at.replace(tzinfo=timezone.utc) >= started + timedelta(seconds=60)


class SuccessfulWorkflow:
    def __init__(self, db):
        self.db = db

    async def run_analysis_flow(self, **kwargs):
        document = Document(
            tenant_id=kwargs["tenant_id"],
            ingestion_job_id=kwargs["ingestion_job_id"],
            filename=kwargs["filename"],
            content_sha256="parsed-hash",
            source_sha256=kwargs["source_sha256"],
            source_uri=kwargs["source_uri"],
            form_type="bank_statement",
            processing_status="completed",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return [SimpleNamespace(document_id=document.document_id)]


def test_worker_completes_job_and_links_durable_document(db, tmp_path):
    store = LocalDocumentSourceStore(tmp_path)
    source = store.put_stream("finance", BytesIO(b"document"), max_bytes=100)
    repository = IngestionRepository(db)
    job, _created = enqueue(repository, source)

    processed = asyncio.run(
        IngestionWorker(
            db,
            source_store=store,
            workflow_factory=SuccessfulWorkflow,
        ).run_once()
    )
    completed = repository.get("finance", job.job_id)

    assert processed is True
    assert completed.status == "completed"
    assert completed.document_id is not None
    assert completed.lease_token is None


def test_recovered_worker_reuses_already_committed_document(db, tmp_path):
    store = LocalDocumentSourceStore(tmp_path)
    source = store.put_stream("finance", BytesIO(b"document"), max_bytes=100)
    repository = IngestionRepository(db)
    job, _created = enqueue(repository, source)
    started = datetime.now(timezone.utc)
    abandoned = repository.claim_next(lease_seconds=1, now=started)
    document = Document(
        tenant_id="finance",
        ingestion_job_id=job.job_id,
        filename=job.filename,
        content_sha256="parsed-hash",
        source_sha256=source.sha256,
        source_uri=source.uri,
        form_type="bank_statement",
        processing_status="completed",
    )
    db.add(document)
    abandoned.lease_expires_at = started - timedelta(seconds=1)
    db.commit()

    class MustNotRunWorkflow:
        def __init__(self, _db):
            raise AssertionError("Completed workflow must not run twice.")

    processed = asyncio.run(
        IngestionWorker(
            db,
            source_store=store,
            workflow_factory=MustNotRunWorkflow,
        ).run_once()
    )

    assert processed is True
    recovered = repository.get("finance", job.job_id)
    assert recovered.status == "completed"
    assert recovered.document_id == document.document_id


class FailingWorkflow:
    def __init__(self, _db):
        pass

    async def run_analysis_flow(self, **_kwargs):
        raise TimeoutError("provider timed out with private content")


def test_worker_retries_transient_failure_without_persisting_sensitive_message(
    db,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "INGESTION_RETRY_BASE_SECONDS", 0)
    store = LocalDocumentSourceStore(tmp_path)
    source = store.put_stream("finance", BytesIO(b"document"), max_bytes=100)
    repository = IngestionRepository(db)
    job, _created = enqueue(repository, source, attempts=2)
    worker = IngestionWorker(db, source_store=store, workflow_factory=FailingWorkflow)

    asyncio.run(worker.run_once())
    retrying = repository.get("finance", job.job_id)
    assert retrying.status == "retry_wait"
    assert retrying.error_code == "unexpected_worker_failure"
    assert retrying.error_message == "TimeoutError"

    asyncio.run(worker.run_once())
    failed = repository.get("finance", job.job_id)
    assert failed.status == "failed"
    assert failed.attempt_count == 2


def test_authenticated_ingestion_api_returns_202_and_tenant_scoped_job(
    db,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "AUTH_MODE", "development")
    monkeypatch.setattr(settings, "DOCUMENT_SOURCE_BACKEND", "local")
    monkeypatch.setattr(settings, "DOCUMENT_SOURCE_ROOT", str(tmp_path))
    db.add(DataWorkspace(workspace_id="finance", display_name="Finance"))
    db.add(
        WorkspaceMembership(
            workspace_id="finance",
            identity_tenant_id="local",
            identity_subject="local-owner",
            role="owner",
            status="active",
        )
    )
    db.commit()

    app = FastAPI()
    app.include_router(ingestion_router, prefix="/ingestions")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    headers = {
        "X-Tenant-ID": "finance",
        "X-User-ID": "local-owner",
        "Idempotency-Key": "source-42-v1",
    }

    accepted = client.post(
        "/ingestions",
        headers=headers,
        files={"file": ("statement.pdf", b"source bytes", "application/pdf")},
    )
    assert accepted.status_code == 202
    payload = accepted.json()
    assert payload["status"] == "queued"
    assert payload["tenant_id"] == "finance"

    fetched = client.get(
        f"/ingestions/{payload['job_id']}",
        headers={"X-Tenant-ID": "finance", "X-User-ID": "local-owner"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["job_id"] == payload["job_id"]
