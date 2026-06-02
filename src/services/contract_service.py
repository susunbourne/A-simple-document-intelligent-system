from sqlalchemy.orm import Session
from src.models.athlete_contract import AthleteContract
from src.schemas.athlete_contract import AthleteContractExtraction


class ContractService:
    def __init__(self, db: Session):
        self.db = db

    def transform_and_save(self, filename: str, raw_text: str,extraction: AthleteContractExtraction) -> AthleteContract:
        record = AthleteContract(
            filename=filename,
            raw_text=raw_text,
            contract_name=extraction.contract_name,
            party_a=extraction.party_a,
            party_b=extraction.party_b,
            effective_date=extraction.effective_date,
            expiration_date=extraction.expiration_date,
            contract_value=extraction.contract_value,
            currency=extraction.currency
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    def get_by_id(self, contract_id: str) -> AthleteContract | None:
        return self.db.query(AthleteContract).filter(AthleteContract.contract_id == contract_id).first()