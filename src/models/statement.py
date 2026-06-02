from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from src.db.database import Base

class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=False, nullable=False)
    raw_text = Column(Text, nullable=False)


    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=True)
    transaction_date = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


