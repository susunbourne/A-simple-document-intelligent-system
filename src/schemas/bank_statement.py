from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class StatementExtraction(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    transaction_date: Optional[str] = None

class StatementExtractionList(BaseModel):
    statements: list[StatementExtraction]


class StatementResponse(BaseModel):
    id: int
    document_id: Optional[int] = None
    filename: str
    description: Optional[str] = None
    amount: Optional[float] = None
    transaction_date: Optional[str] = None
    processing_status: str
    source_chunk_ids: Optional[str] = None
    review_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class StatementResponseList(BaseModel):
    statements: list[StatementResponse]

