from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StatementExtraction(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    transaction_date: Optional[str] = None

class StatementResponse(BaseModel):
    id: int
    filename: str
    extraction: StatementExtraction
    created_at: datetime

    class Config:
        from_attributes = True

        