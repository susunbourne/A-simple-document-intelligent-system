from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from src.db.database import Base

class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=True, index=True)
    filename = Column(String, unique=False, nullable=False)

    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=True)
    transaction_date = Column(String, nullable=True)
    processing_status = Column(String, nullable=False, default="completed")
    source_chunk_ids = Column(Text, nullable=True)
    review_reason = Column(Text, nullable=True)
    router_confidence = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


