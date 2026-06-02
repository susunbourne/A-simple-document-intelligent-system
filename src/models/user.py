from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from src.db.database import Base


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, unique=True)
    user_email = Column(String, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
