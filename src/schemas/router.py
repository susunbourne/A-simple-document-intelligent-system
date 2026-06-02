from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RouterDeterminationResult(BaseModel):
    form_type: Optional[str] = None
    confidence: Optional[float] = None
    