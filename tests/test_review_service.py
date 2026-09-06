import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.database import Base
from src.models.document import Document, DocumentReviewDecision
from src.models.statement import BankStatement
from src.schemas.review import RecordCorrection, ReviewDecisionRequest
from src.services.auth import AuthorizedWorkspace, RequestIdentity
from src.services.review_service import (
    ReviewConflictError,
    ReviewDocumentNotFoundError,
    ReviewService,
    ReviewValidationError,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _workspace(workspace_id: str = "finance") -> AuthorizedWorkspace:
    return AuthorizedWorkspace(
        workspace_id=workspace_id,
        identity=RequestIdentity("entra-tenant", "reviewer-oid", "entra"),
        role="reviewer",
    )


def _reviewable_statement(db):
    document = Document(
        tenant_id="finance",
        filename="statement.pdf",
        content_sha256="hash",
        form_type="bank_statement",
        processing_status="needs_review",
        review_reason="Missing required fields: amount",
    )
    db.add(document)
    db.flush()
    statement = BankStatement(
        document_id=document.document_id,
        filename=document.filename,
        description="Bookstore",
        amount=None,
        transaction_date="2026-09-01",
        processing_status="needs_review",
        review_reason=document.review_reason,
    )
    db.add(statement)
    db.commit()
    return document, statement


def test_reviewer_can_correct_and_approve_with_audit_snapshot(db):
    document, statement = _reviewable_statement(db)

    result = ReviewService(db).decide(
        workspace=_workspace(),
        document_id=document.document_id,
        request=ReviewDecisionRequest(
            action="approve",
            expected_review_version=0,
            corrections=[RecordCorrection(record_id=statement.id, fields={"amount": 42.5})],
            note="Matched the amount to the source page.",
        ),
    )

    db.refresh(document)
    db.refresh(statement)
    assert document.processing_status == "completed"
    assert document.review_version == 1
    assert document.reviewed_by_subject == "reviewer-oid"
    assert statement.amount == 42.5
    assert statement.processing_status == "completed"
    assert result.decision.before_snapshot[0]["amount"] is None
    assert result.decision.after_snapshot[0]["amount"] == 42.5
    assert db.query(DocumentReviewDecision).count() == 1


def test_approval_rejects_missing_required_fields(db):
    document, _statement = _reviewable_statement(db)

    with pytest.raises(ReviewValidationError):
        ReviewService(db).decide(
            workspace=_workspace(),
            document_id=document.document_id,
            request=ReviewDecisionRequest(action="approve", expected_review_version=0),
        )

    db.rollback()
    db.refresh(document)
    assert document.processing_status == "needs_review"
    assert db.query(DocumentReviewDecision).count() == 0


def test_review_uses_optimistic_version_to_prevent_stale_decision(db):
    document, _statement = _reviewable_statement(db)
    document.review_version = 2
    db.commit()

    with pytest.raises(ReviewConflictError):
        ReviewService(db).decide(
            workspace=_workspace(),
            document_id=document.document_id,
            request=ReviewDecisionRequest(action="reject", expected_review_version=1),
        )


def test_review_does_not_reveal_cross_workspace_document(db):
    document, _statement = _reviewable_statement(db)

    with pytest.raises(ReviewDocumentNotFoundError):
        ReviewService(db).decide(
            workspace=_workspace("legal"),
            document_id=document.document_id,
            request=ReviewDecisionRequest(action="reject", expected_review_version=0),
        )
