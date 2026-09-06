from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from src.db.database import Base


class AthleteContract(Base):
    __tablename__ = "athlete_contracts"
    contract_id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=True, index=True)
    filename = Column(String, unique=False, nullable=False)
    contract_name = Column(String, unique=False, nullable=True)
    party_a = Column(String, nullable=True)
    party_b = Column(String, nullable=True)
    effective_date = Column(String, nullable=True)
    expiration_date = Column(String, nullable=True)
    contract_value = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    processing_status = Column(String, nullable=False, default="completed")
    source_chunk_ids = Column(Text, nullable=True)
    review_reason = Column(Text, nullable=True)
    router_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

