from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ReviewQueueItem(BaseModel):
    document_id: int
    filename: str
    form_type: str
    router_confidence: Optional[float] = None
    processing_status: str
    review_reason: Optional[str] = None
    review_version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewQueueResponse(BaseModel):
    documents: list[ReviewQueueItem]


class RecordCorrection(BaseModel):
    record_id: int
    fields: dict[str, Any]


class ReviewDecisionRequest(BaseModel):
    action: Literal["approve", "reject"]
    expected_review_version: int
    corrections: list[RecordCorrection] = Field(default_factory=list)
    note: Optional[str] = None


class ReviewDecisionResponse(BaseModel):
    decision_id: str
    document_id: int
    action: str
    previous_status: str
    new_status: str
    review_version: int
    actor_subject: str
    actor_role: str
    created_at: datetime


class ReviewHistoryItem(BaseModel):
    decision_id: str
    action: str
    actor_subject: str
    actor_role: str
    previous_status: str
    new_status: str
    corrections: Optional[list[dict[str, Any]]] = None
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewHistoryResponse(BaseModel):
    document_id: int
    review_version: int
    decisions: list[ReviewHistoryItem]
