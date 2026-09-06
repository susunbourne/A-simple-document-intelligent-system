import hashlib

from sqlalchemy.orm import Session

from src.models.document import Document, DocumentChunk
from src.services.rag_service import DocumentChunk as RetrievedDocumentChunk


class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    def create_document(
        self,
        *,
        filename: str,
        raw_text: str,
        form_type: str,
        router_confidence: float | None,
        tenant_id: str = "default",
        ingestion_job_id: str | None = None,
        source_sha256: str | None = None,
        source_uri: str | None = None,
        pipeline_version: str | None = None,
        router_model: str | None = None,
        embedding_model: str | None = None,
        extraction_model: str | None = None,
    ) -> Document:
        document = Document(
            tenant_id=tenant_id,
            ingestion_job_id=ingestion_job_id,
            filename=filename,
            content_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            source_sha256=source_sha256,
            source_uri=source_uri,
            pipeline_version=pipeline_version,
            router_model=router_model,
            embedding_model=embedding_model,
            extraction_model=extraction_model,
            form_type=form_type,
            router_confidence=router_confidence,
            processing_status="processing",
        )
        self.db.add(document)
        self.db.flush()
        return document

    def store_chunks(
        self,
        *,
        document_id: int,
        chunks: list[RetrievedDocumentChunk],
    ) -> None:
        for chunk in chunks:
            self.db.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    text_sha256=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    token_estimate=chunk.token_estimate,
                    section_index=chunk.section_index,
                )
            )
        self.db.flush()

    def mark_status(
        self,
        document: Document,
        *,
        processing_status: str,
        review_reason: str | None,
    ) -> None:
        document.processing_status = processing_status
        document.review_reason = review_reason
        self.db.flush()
