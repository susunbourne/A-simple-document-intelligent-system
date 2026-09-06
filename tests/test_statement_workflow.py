import asyncio
from types import SimpleNamespace

import pytest

from src.core.errors import AppError, ErrorCode
from src.schemas.athlete_contract import AthleteContractExtraction, AthleteContractExtractionList
from src.schemas.router import RouterDeterminationResult
from src.workflows.statement_workflow import StatementWorkflow


class FakeDocling:
    def __init__(self, text="parsed text"):
        self.text = text

    def convert_document(self, file_bytes, filename, request_id=None):
        return self.text


class FakeRouter:
    def __init__(self, form_type, confidence):
        self.result = RouterDeterminationResult(
            form_type=form_type,
            confidence=confidence,
        )

    async def determine_form_type(self, raw_text):
        return self.result


class FakeRag:
    async def build_index(self, raw_text):
        return [SimpleNamespace(chunk_id=7, text=raw_text)]

    def retrieval_query_for(self, form_type):
        return "query"

    async def retrieve(self, index, query):
        return SimpleNamespace(context="[chunk_id=7]\nparsed text", source_chunk_ids=[7])


class FakeDb:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, record):
        self.refreshed.append(record)


class FakeStatementService:
    def __init__(self, db):
        self.db = db


class FakeContractAgent:
    async def extract_data(self, text, retrieved_context=None):
        return AthleteContractExtractionList(
            contracts=[
                AthleteContractExtraction(
                    contract_name="NIL Agreement",
                    party_a="Brand LLC",
                    party_b=None,
                    effective_date="2026-02-01",
                    expiration_date="2026-08-01",
                    contract_value=None,
                    currency="USD",
                )
            ]
        )


class FakeContractService:
    def __init__(self, db):
        self.db = db
        self.saved = []

    def transform_and_save(self, filename, extraction, **metadata):
        record = SimpleNamespace(
            filename=filename,
            **extraction.model_dump(),
            **metadata,
        )
        self.saved.append(record)
        return record


class FakeDocumentService:
    def __init__(self):
        self.created = []
        self.stored_chunks = []
        self.status_updates = []

    def create_document(self, *, filename, raw_text, form_type, router_confidence, **metadata):
        document = SimpleNamespace(
            document_id=99,
            filename=filename,
            raw_text=raw_text,
            form_type=form_type,
            router_confidence=router_confidence,
            **metadata,
        )
        self.created.append(document)
        return document

    def store_chunks(self, *, document_id, chunks):
        self.stored_chunks.append((document_id, chunks))

    def mark_status(self, document, *, processing_status, review_reason):
        document.processing_status = processing_status
        document.review_reason = review_reason
        self.status_updates.append((processing_status, review_reason))


def build_workflow(router):
    db = FakeDb()
    workflow = StatementWorkflow.__new__(StatementWorkflow)
    workflow.docling = FakeDocling()
    workflow.router = router
    workflow.rag = FakeRag()
    workflow.extraction = None
    workflow.contract = FakeContractAgent()
    workflow.document_service = FakeDocumentService()
    workflow.statement_service = FakeStatementService(db)
    workflow.contract_service = FakeContractService(db)
    return workflow, db


def test_low_confidence_router_rejects_before_persistence():
    workflow, db = build_workflow(FakeRouter("athlete_contract", 0.2))

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            workflow.run_analysis_flow(
                b"fake",
                "contract.pdf",
                request_id="req-1",
            )
        )

    assert exc_info.value.code == ErrorCode.ROUTER_LOW_CONFIDENCE
    assert db.commits == 0
    assert db.rollbacks == 0


def test_missing_contract_fields_persist_as_needs_review():
    workflow, db = build_workflow(FakeRouter("athlete_contract", 0.95))

    records = asyncio.run(
        workflow.run_analysis_flow(
            b"fake",
            "contract.pdf",
            request_id="req-2",
        )
    )

    assert db.commits == 1
    assert db.rollbacks == 0
    assert len(records) == 1
    assert records[0].document_id == 99
    assert records[0].processing_status == "needs_review"
    assert records[0].source_chunk_ids == "[7]"
    assert "party_b" in records[0].review_reason
    assert "contract_value" in records[0].review_reason
    assert workflow.document_service.status_updates == [
        ("needs_review", "Missing required fields: party_b, contract_value")
    ]
