from sqlalchemy.orm import Session
from src.services.docling_service import DoclingService
from src.services.extraction_service import ExtractionService
from src.services.statement_service import StatementService
from src.agents.router_agent import RouterAgent
from src.agents.contract_agent import ExtractionService as ContractExtractionService
from src.services.contract_service import ContractService
import logging

class StatementWorkflow:
    def __init__(self, db: Session):
        self.docling = DoclingService()
        self.router = RouterAgent()
        self.extraction = ExtractionService()
        self.statement_service = StatementService(db)
        self.contract = ContractExtractionService()
        self.contract_service = ContractService(db)

    async def run_analysis_flow(self, file_bytes: bytes, filename: str):
        raw_text = self.docling.convert_document(file_bytes, filename)
        if not raw_text:
            raise ValueError("Failed to extract text from the document.")
        # router tells the forms
        try:
            decision = await self.router.determine_form_type(raw_text)
        except Exception:
            # Router failed — safer to stop processing than to continue blindly
            raise ValueError("Form router failed to determine document type.")

        form_type = (decision.form_type or "").strip().lower() if decision is not None else "unknown"
        form_confidence = decision.confidence
        print(f"Router decision: {decision}")
        # check None first to avoid TypeError when comparing
        if form_confidence is None or form_confidence < 0.5:
            raise ValueError("Form router is not confident enough to determine document type.")
        #Ask for human check
        if form_type == "unknown":
            raise ValueError("Form type is unknown. Human review required.")
        #call for agents for different extraction tasks:
        if form_type == "bank_statement":
            records = []
            extraction = await self.extraction.extract_data(raw_text)
            # extraction may be a wrapper model (StatementExtractionList) with .statements
            extraction_list = getattr(extraction, "statements", extraction)
            for extraction_item in extraction_list:
                rec = self.statement_service.transform_and_save(filename, raw_text, extraction_item)
                records.append(rec)
            return records
        elif form_type == "athlete contract":
            extraction = await self.contract.extract_data(raw_text)
            # contract extractor may return AthleteContractExtractionList with .contracts
            extraction_list = getattr(extraction, "contracts", extraction)
            records = []
            for extraction_item in extraction_list:
                rec = self.contract_service.transform_and_save(filename, raw_text, extraction_item)
                records.append(rec)
            return records
        else:
            raise ValueError(f"Unsupported form type: {form_type}")

    

    def get_result(self, id: int):
        return self.statement_service.get_by_id(id)

