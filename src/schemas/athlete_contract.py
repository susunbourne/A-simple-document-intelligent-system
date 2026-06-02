from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AthleteContractExtraction(BaseModel):
    contract_name: Optional[str] = None
    party_a: str
    party_b: str
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    contract_value: Optional[float] = None
    currency: Optional[str] = None

class AthleteContractExtractionList(BaseModel):
    contracts: list[AthleteContractExtraction]

class AthleteContractResponse(BaseModel):
    contract_id: int
    filename: str
    raw_text: str
    contract_name: Optional[str] = None
    party_a: str
    party_b: str
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    contract_value: Optional[float] = None
    currency: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class AthleteContractResponseList(BaseModel):
    contracts: list[AthleteContractResponse]

