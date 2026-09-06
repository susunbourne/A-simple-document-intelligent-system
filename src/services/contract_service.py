from sqlalchemy.orm import Session
from src.models.athlete_contract import AthleteContract
from src.schemas.athlete_contract import AthleteContractExtraction


class ContractService:
    def __init__(self, db: Session):
        self.db = db

    def transform_and_save(
        self,
        filename: str,
        extraction: AthleteContractExtraction,
        *,
        document_id: int | None,
        processing_status: str,
        source_chunk_ids: str | None,
        review_reason: str | None,
        router_confidence: float | None,
    ) -> AthleteContract:
        record = AthleteContract(
            document_id=document_id,
            filename=filename,
            contract_name=extraction.contract_name,
            party_a=extraction.party_a,
            party_b=extraction.party_b,
            effective_date=extraction.effective_date,
            expiration_date=extraction.expiration_date,
            contract_value=extraction.contract_value,
            currency=extraction.currency,
            processing_status=processing_status,
            source_chunk_ids=source_chunk_ids,
            review_reason=review_reason,
            router_confidence=router_confidence,
        )
        self.db.add(record)
        self.db.flush()
        return record
    def get_by_id(self, contract_id: str) -> AthleteContract | None:
        return self.db.query(AthleteContract).filter(AthleteContract.contract_id == contract_id).first()
