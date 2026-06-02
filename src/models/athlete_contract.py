from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from src.db.database import Base


class AthleteContract(Base):
    __tablename__ = "athlete_contracts"
    contract_id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, nullable=False)
    raw_text = Column(Text, nullable=False)
    contract_name = Column(String, unique=False)
    party_a = Column(String, nullable=False)
    party_b = Column(String, nullable=False)
    effective_date = Column(String, nullable=False)
    expiration_date = Column(String, nullable=False)
    contract_value = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

