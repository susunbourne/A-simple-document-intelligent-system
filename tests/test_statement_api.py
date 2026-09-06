import asyncio
from tempfile import SpooledTemporaryFile
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.statement import list_review_documents, upload_statement
from src.db.database import Base
from src.models.document import Document


def make_upload(filename: str, content: bytes) -> UploadFile:
    file = SpooledTemporaryFile()
    file.write(content)
    file.seek(0)
    return UploadFile(file=file, filename=filename)


def test_unsupported_upload_extension_returns_stable_error():
    upload = make_upload("notes.txt", b"hello")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            upload_statement(
                file=upload,
                access=SimpleNamespace(workspace_id="finance"),
                db=None,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "unsupported_file_type"
    assert "request_id" in exc_info.value.detail


def test_review_queue_returns_only_requested_status():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            Document(
                tenant_id="finance",
                filename="needs-review.pdf",
                content_sha256="a",
                form_type="athlete_contract",
                router_confidence=0.91,
                processing_status="needs_review",
                review_reason="Missing required fields: party_b",
            ),
            Document(
                tenant_id="finance",
                filename="completed.pdf",
                content_sha256="b",
                form_type="bank_statement",
                router_confidence=0.99,
                processing_status="completed",
            ),
            Document(
                tenant_id="legal",
                filename="other-tenant.pdf",
                content_sha256="c",
                form_type="athlete_contract",
                router_confidence=0.91,
                processing_status="needs_review",
            ),
        ]
    )
    session.commit()

    response = list_review_documents(
        status_filter="needs_review",
        access=SimpleNamespace(workspace_id="finance"),
        db=session,
    )

    assert len(response.documents) == 1
    assert response.documents[0].filename == "needs-review.pdf"
