from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.models.athlete_contract import AthleteContract
from src.models.document import Document, DocumentReviewDecision
from src.models.statement import BankStatement
from src.schemas.athlete_contract import AthleteContractExtraction
from src.schemas.bank_statement import StatementExtraction
from src.schemas.review import ReviewDecisionRequest
from src.services.auth import AuthorizedWorkspace


class ReviewDocumentNotFoundError(LookupError):
    pass


class ReviewConflictError(RuntimeError):
    pass


class ReviewValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewResult:
    decision: DocumentReviewDecision
    review_version: int


class ReviewService:
    _BANK_FIELDS = {"description", "amount", "transaction_date"}
    _BANK_REQUIRED = _BANK_FIELDS
    _CONTRACT_FIELDS = {
        "contract_name",
        "party_a",
        "party_b",
        "effective_date",
        "expiration_date",
        "contract_value",
        "currency",
    }
    _CONTRACT_REQUIRED = _CONTRACT_FIELDS - {"contract_name"}

    def __init__(self, db: Session):
        self.db = db

    def decide(
        self,
        *,
        workspace: AuthorizedWorkspace,
        document_id: int,
        request: ReviewDecisionRequest,
    ) -> ReviewResult:
        document = (
            self.db.query(Document)
            .filter(
                Document.document_id == document_id,
                Document.tenant_id == workspace.workspace_id,
            )
            .with_for_update()
            .first()
        )
        if document is None:
            raise ReviewDocumentNotFoundError(document_id)
        if document.processing_status != "needs_review":
            raise ReviewConflictError(
                f"Document is {document.processing_status}, not needs_review."
            )
        if document.review_version != request.expected_review_version:
            raise ReviewConflictError(
                f"Review version changed from {request.expected_review_version} "
                f"to {document.review_version}."
            )
        if request.action == "reject" and request.corrections:
            raise ReviewValidationError("Rejected documents cannot include corrections.")

        records, id_field, allowed_fields, required_fields, validator = self._records_for(document)
        before = self._snapshot(records, id_field, allowed_fields)
        if request.action == "approve":
            self._apply_corrections(records, id_field, allowed_fields, validator, request)
            self._require_complete(records, id_field, required_fields)
            new_status = "completed"
            for record in records:
                record.processing_status = new_status
                record.review_reason = None
            document.review_reason = None
        else:
            new_status = "rejected"
            for record in records:
                record.processing_status = new_status
                record.review_reason = request.note or "Rejected during human review."
            document.review_reason = request.note or "Rejected during human review."

        previous_status = document.processing_status
        document.processing_status = new_status
        document.review_version += 1
        document.reviewed_at = datetime.now(timezone.utc)
        document.reviewed_by_subject = workspace.identity.subject
        after = self._snapshot(records, id_field, allowed_fields)
        decision = DocumentReviewDecision(
            decision_id=str(uuid4()),
            tenant_id=workspace.workspace_id,
            document_id=document.document_id,
            action=request.action,
            actor_tenant_id=workspace.identity.identity_tenant_id,
            actor_subject=workspace.identity.subject,
            actor_role=workspace.role,
            previous_status=previous_status,
            new_status=new_status,
            corrections=[item.model_dump() for item in request.corrections] or None,
            before_snapshot=before,
            after_snapshot=after,
            note=request.note,
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return ReviewResult(decision=decision, review_version=document.review_version)

    def history(self, workspace_id: str, document_id: int) -> tuple[Document, list[DocumentReviewDecision]]:
        document = (
            self.db.query(Document)
            .filter(
                Document.document_id == document_id,
                Document.tenant_id == workspace_id,
            )
            .first()
        )
        if document is None:
            raise ReviewDocumentNotFoundError(document_id)
        decisions = (
            self.db.query(DocumentReviewDecision)
            .filter(
                DocumentReviewDecision.document_id == document_id,
                DocumentReviewDecision.tenant_id == workspace_id,
            )
            .order_by(DocumentReviewDecision.created_at.asc())
            .all()
        )
        return document, decisions

    def _records_for(self, document: Document):
        if document.form_type == "bank_statement":
            records = (
                self.db.query(BankStatement)
                .filter(BankStatement.document_id == document.document_id)
                .order_by(BankStatement.id.asc())
                .all()
            )
            return records, "id", self._BANK_FIELDS, self._BANK_REQUIRED, StatementExtraction
        if document.form_type == "athlete_contract":
            records = (
                self.db.query(AthleteContract)
                .filter(AthleteContract.document_id == document.document_id)
                .order_by(AthleteContract.contract_id.asc())
                .all()
            )
            return records, "contract_id", self._CONTRACT_FIELDS, self._CONTRACT_REQUIRED, AthleteContractExtraction
        raise ReviewValidationError(f"Unsupported review form type: {document.form_type}")

    @staticmethod
    def _snapshot(records, id_field: str, fields: set[str]) -> list[dict]:
        return [
            {
                "record_id": getattr(record, id_field),
                **{field: getattr(record, field) for field in sorted(fields)},
            }
            for record in records
        ]

    @staticmethod
    def _apply_corrections(records, id_field, allowed_fields, validator, request) -> None:
        records_by_id = {getattr(record, id_field): record for record in records}
        seen_ids: set[int] = set()
        for correction in request.corrections:
            if correction.record_id in seen_ids:
                raise ReviewValidationError(
                    f"Record {correction.record_id} appears more than once."
                )
            seen_ids.add(correction.record_id)
            record = records_by_id.get(correction.record_id)
            if record is None:
                raise ReviewValidationError(
                    f"Record {correction.record_id} does not belong to this document."
                )
            unknown = set(correction.fields) - allowed_fields
            if unknown:
                raise ReviewValidationError(
                    f"Fields are not editable: {', '.join(sorted(unknown))}."
                )
            try:
                validated = validator(**correction.fields)
            except ValidationError as exc:
                raise ReviewValidationError(str(exc)) from exc
            for field in correction.fields:
                setattr(record, field, getattr(validated, field))

    @staticmethod
    def _require_complete(records, id_field: str, required_fields: set[str]) -> None:
        if not records:
            raise ReviewValidationError("Document has no extracted records to approve.")
        missing = {
            getattr(record, id_field): sorted(
                field
                for field in required_fields
                if getattr(record, field) in (None, "")
            )
            for record in records
        }
        missing = {record_id: fields for record_id, fields in missing.items() if fields}
        if missing:
            raise ReviewValidationError(f"Required fields are still missing: {missing}")
