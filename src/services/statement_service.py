from sqlalchemy.orm import Session
from src.models.statement import BankStatement
from src.schemas.bank_statement import StatementExtraction

class StatementService:
    def __init__(self, db: Session):
        self.db = db

    def transform_and_save(
        self,
        filename: str,
        extraction: StatementExtraction,
        *,
        document_id: int | None,
        processing_status: str,
        source_chunk_ids: str | None,
        review_reason: str | None,
        router_confidence: float | None,
    ) -> BankStatement:
        record = BankStatement(
            document_id=document_id,
            filename=filename,
            description=extraction.description,
            amount=extraction.amount,
            transaction_date=extraction.transaction_date,
            processing_status=processing_status,
            source_chunk_ids=source_chunk_ids,
            review_reason=review_reason,
            router_confidence=router_confidence,
        )
        self.db.add(record)
        self.db.flush()
        return record
    
    def get_by_id(self, statement_id: int) -> BankStatement | None:
        return self.db.query(BankStatement).filter(BankStatement.id == statement_id).first()
    
    
