from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    DOCUMENT_PARSE_FAILED = "document_parse_failed"
    ROUTER_FAILED = "router_failed"
    ROUTER_LOW_CONFIDENCE = "router_low_confidence"
    UNSUPPORTED_DOCUMENT_TYPE = "unsupported_document_type"
    RAG_FAILED = "rag_failed"
    EXTRACTION_FAILED = "extraction_failed"
    VALIDATION_FAILED = "validation_failed"
    PERSISTENCE_FAILED = "persistence_failed"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
