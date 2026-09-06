import json
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.errors import AppError, ErrorCode
from src.core.logging import log_event

if TYPE_CHECKING:
    from src.agents.contract_agent import ExtractionService as ContractExtractionService
    from src.agents.router_agent import RouterAgent
    from src.services.contract_service import ContractService
    from src.services.docling_service import DoclingService
    from src.services.document_service import DocumentService
    from src.services.extraction_service import ExtractionService
    from src.services.rag_service import RAGService
    from src.services.statement_service import StatementService


logger = logging.getLogger(__name__)


def _normalize_form_type(form_type: str) -> str:
    normalized = form_type.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized == "athlete_contract":
        return "athlete_contract"
    if normalized == "bank_statement":
        return "bank_statement"
    return normalized


def _missing_fields(extraction_item: object, required_fields: list[str]) -> list[str]:
    return [
        field
        for field in required_fields
        if getattr(extraction_item, field, None) in (None, "")
    ]


class StatementWorkflow:
    def __init__(
        self,
        db: Session,
        *,
        docling: "DoclingService | None" = None,
        router: "RouterAgent | None" = None,
        rag: "RAGService | None" = None,
        extraction: "ExtractionService | None" = None,
        contract: "ContractExtractionService | None" = None,
        document_service: "DocumentService | None" = None,
        statement_service: "StatementService | None" = None,
        contract_service: "ContractService | None" = None,
    ):
        from src.agents.contract_agent import ExtractionService as ContractExtractionService
        from src.agents.router_agent import RouterAgent
        from src.services.contract_service import ContractService
        from src.services.docling_service import DoclingService
        from src.services.document_service import DocumentService
        from src.services.extraction_service import ExtractionService
        from src.services.rag_service import RAGService
        from src.services.statement_service import StatementService

        self.docling = docling or DoclingService()
        self.router = router or RouterAgent()
        self.rag = rag or RAGService()
        self.extraction = extraction or ExtractionService()
        self.document_service = document_service or DocumentService(db)
        self.statement_service = statement_service or StatementService(db)
        self.contract = contract or ContractExtractionService()
        self.contract_service = contract_service or ContractService(db)

    async def run_analysis_flow(
        self,
        file_bytes: bytes,
        filename: str,
        request_id: str | None = None,
        tenant_id: str = "default",
        ingestion_job_id: str | None = None,
        source_sha256: str | None = None,
        source_uri: str | None = None,
        progress_callback=None,
    ):
        started = time.perf_counter()
        self._report_progress(progress_callback, "parsing")
        raw_text = self._parse_document(file_bytes, filename, request_id)
        self._report_progress(progress_callback, "routing")
        decision = await self._route_document(raw_text, request_id)

        form_type = _normalize_form_type(decision.form_type or "")
        form_confidence = decision.confidence
        if form_confidence is None or form_confidence < settings.ROUTER_CONFIDENCE_THRESHOLD:
            raise AppError(
                ErrorCode.ROUTER_LOW_CONFIDENCE,
                "The router is not confident enough to process this document automatically.",
                status_code=422,
                details={"form_type": form_type, "confidence": form_confidence},
            )
        if form_type == "unknown":
            raise AppError(
                ErrorCode.UNSUPPORTED_DOCUMENT_TYPE,
                "The document type is unknown. Human review is required.",
                status_code=422,
            )

        document = self.document_service.create_document(
            filename=filename,
            raw_text=raw_text,
            form_type=form_type,
            router_confidence=form_confidence,
            tenant_id=tenant_id,
            ingestion_job_id=ingestion_job_id,
            source_sha256=source_sha256,
            source_uri=source_uri,
            pipeline_version=settings.PIPELINE_VERSION,
            router_model=settings.ROUTER_MODEL,
            embedding_model=settings.EMBEDDING_MODEL,
            extraction_model=settings.EXTRACTION_MODEL,
        )

        self._report_progress(progress_callback, "indexing")
        retrieved_context, source_chunk_ids = await self._retrieve_context(
            raw_text,
            form_type,
            request_id,
            document.document_id,
        )

        try:
            self._report_progress(progress_callback, "extracting")
            if form_type == "bank_statement":
                records = await self._extract_bank_statement(
                    filename,
                    raw_text,
                    retrieved_context,
                    source_chunk_ids,
                    form_confidence,
                    document.document_id,
                )
            elif form_type == "athlete_contract":
                records = await self._extract_athlete_contract(
                    filename,
                    raw_text,
                    retrieved_context,
                    source_chunk_ids,
                    form_confidence,
                    document.document_id,
                )
            else:
                raise AppError(
                    ErrorCode.UNSUPPORTED_DOCUMENT_TYPE,
                    f"Unsupported form type: {form_type}",
                    status_code=422,
                )

            self._report_progress(progress_callback, "persisting")
            review_reasons = [
                record.review_reason for record in records if record.review_reason
            ]
            self.document_service.mark_status(
                document,
                processing_status="needs_review" if review_reasons else "completed",
                review_reason="; ".join(review_reasons) if review_reasons else None,
            )
            self.statement_service.db.commit()
            for record in records:
                self.statement_service.db.refresh(record)
            self.statement_service.db.refresh(document)
            log_event(
                logger,
                "workflow_completed",
                request_id=request_id,
                form_type=form_type,
                record_count=len(records),
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return records
        except AppError:
            self.statement_service.db.rollback()
            raise
        except Exception as exc:
            self.statement_service.db.rollback()
            raise AppError(
                ErrorCode.EXTRACTION_FAILED,
                "Document extraction or persistence failed.",
                status_code=502,
            ) from exc

    @staticmethod
    def _report_progress(callback, stage: str) -> None:
        if callback is not None:
            callback(stage)

    def _parse_document(self, file_bytes: bytes, filename: str, request_id: str | None) -> str:
        try:
            raw_text = self.docling.convert_document(file_bytes, filename, request_id=request_id)
        except Exception as exc:
            raise AppError(
                ErrorCode.DOCUMENT_PARSE_FAILED,
                "The document could not be parsed into text.",
                status_code=422,
            ) from exc
        if not raw_text:
            raise AppError(
                ErrorCode.DOCUMENT_PARSE_FAILED,
                "The document parser returned no text.",
                status_code=422,
            )
        return raw_text

    async def _route_document(self, raw_text: str, request_id: str | None):
        try:
            decision = await self.router.determine_form_type(raw_text)
        except Exception as exc:
            raise AppError(
                ErrorCode.ROUTER_FAILED,
                "The document router failed to determine document type.",
                status_code=502,
            ) from exc
        log_event(
            logger,
            "router_completed",
            request_id=request_id,
            form_type=_normalize_form_type(decision.form_type or ""),
            confidence=decision.confidence,
        )
        return decision

    async def _retrieve_context(
        self,
        raw_text: str,
        form_type: str,
        request_id: str | None,
        document_id: int,
    ) -> tuple[str, str | None]:
        try:
            rag_index = await self.rag.build_index(raw_text)
            retrieval = await self.rag.retrieve(
                rag_index,
                self.rag.retrieval_query_for(form_type),
            )
            self.document_service.store_chunks(
                document_id=document_id,
                chunks=rag_index,
            )
            source_chunk_ids = json.dumps(retrieval.source_chunk_ids)
            log_event(
                logger,
                "rag_completed",
                request_id=request_id,
                chunk_count=len(rag_index),
                selected_chunk_ids=source_chunk_ids,
            )
            return retrieval.context, source_chunk_ids
        except Exception as exc:
            log_event(
                logger,
                "rag_failed_fallback_to_full_text",
                request_id=request_id,
                error_type=type(exc).__name__,
            )
            return raw_text, None

    async def _extract_bank_statement(
        self,
        filename: str,
        raw_text: str,
        retrieved_context: str,
        source_chunk_ids: str | None,
        router_confidence: float | None,
        document_id: int | None,
    ):
        extraction = await self.extraction.extract_data(
            raw_text,
            retrieved_context=retrieved_context,
        )
        extraction_list = getattr(extraction, "statements", extraction)
        records = []
        for extraction_item in extraction_list:
            missing = _missing_fields(
                extraction_item,
                ["description", "amount", "transaction_date"],
            )
            status = "needs_review" if missing else "completed"
            review_reason = f"Missing required fields: {', '.join(missing)}" if missing else None
            records.append(
                self.statement_service.transform_and_save(
                    filename,
                    extraction_item,
                    document_id=document_id,
                    processing_status=status,
                    source_chunk_ids=source_chunk_ids,
                    review_reason=review_reason,
                    router_confidence=router_confidence,
                )
            )
        return records

    async def _extract_athlete_contract(
        self,
        filename: str,
        raw_text: str,
        retrieved_context: str,
        source_chunk_ids: str | None,
        router_confidence: float | None,
        document_id: int | None,
    ):
        extraction = await self.contract.extract_data(
            raw_text,
            retrieved_context=retrieved_context,
        )
        extraction_list = getattr(extraction, "contracts", extraction)
        records = []
        for extraction_item in extraction_list:
            missing = _missing_fields(
                extraction_item,
                [
                    "party_a",
                    "party_b",
                    "effective_date",
                    "expiration_date",
                    "contract_value",
                    "currency",
                ],
            )
            status = "needs_review" if missing else "completed"
            review_reason = f"Missing required fields: {', '.join(missing)}" if missing else None
            records.append(
                self.contract_service.transform_and_save(
                    filename,
                    extraction_item,
                    document_id=document_id,
                    processing_status=status,
                    source_chunk_ids=source_chunk_ids,
                    review_reason=review_reason,
                    router_confidence=router_confidence,
                )
            )
        return records

    def get_result(self, id: int):
        return self.statement_service.get_by_id(id)
