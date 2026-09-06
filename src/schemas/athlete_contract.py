from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AthleteContractExtraction(BaseModel):
    contract_name: Optional[str] = None
    party_a: Optional[str] = None
    party_b: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    contract_value: Optional[float] = None
    currency: Optional[str] = None

class AthleteContractExtractionList(BaseModel):
    contracts: list[AthleteContractExtraction]

class AthleteContractResponse(BaseModel):
    contract_id: int
    document_id: Optional[int] = None
    filename: str
    contract_name: Optional[str] = None
    party_a: Optional[str] = None
    party_b: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    contract_value: Optional[float] = None
    currency: Optional[str] = None
    processing_status: str
    source_chunk_ids: Optional[str] = None
    review_reason: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class AthleteContractResponseList(BaseModel):
    contracts: list[AthleteContractResponse]

