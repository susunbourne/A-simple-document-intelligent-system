from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class User(BaseModel):
    user_id: int
    user_name: str
    user_email: str
    created_at: datetime