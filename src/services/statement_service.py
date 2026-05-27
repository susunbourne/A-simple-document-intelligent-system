from sqlalchemy.orm import Session
from src.models.statement import BankStatement
from src.schemas.bank_statement import StatementExtraction

class StatementService:
    def __init__(self, db: Session):
        self.db = db

    def transform_and_save(self, filename: str, raw_text: str, extraction: StatementExtraction) -> BankStatement:
        record = BankStatement(
            filename=filename,
            raw_text=raw_text,
            description=extraction.description,
            amount=extraction.amount,
            transaction_date=extraction.transaction_date
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_by_id(self, statement_id: int) -> BankStatement | None:
        return self.db.query(BankStatement).filter(BankStatement.id == statement_id).first()
    
    
