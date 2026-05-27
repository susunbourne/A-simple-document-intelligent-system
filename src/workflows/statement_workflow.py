from sqlalchemy.orm import Session
from src.services.docling_service import DoclingService
from src.services.extraction_service import ExtractionService
from src.services.statement_service import StatementService


class StatementWorkflow:
    def __init__(self, db: Session):
        self.docling = DoclingService()
        self.extraction = ExtractionService()
        self.statement = StatementService(db)

    async def run_analysis_flow(self, file_bytes: bytes, filename: str):
        raw_text = self.docling.convert_document(file_bytes, filename)
        if not raw_text:
            raise ValueError("Failed to extract text from the document.")
        
        extraction = await self.extraction.extract_data(raw_text)
        # Gemini/Claude_extraction = await self.extraction.extract_with_Gemini/Claude(raw_text)
        # final_result = self._consensus([openai_result, gemini_result, deepseek_result])


    #     def _consensus(self, results: list[StatementExtraction]) -> StatementExtraction:
    # # 三个模型各提取了一次，results长这样：
    # # [
    # #     StatementExtraction(description="购物", amount=100.0, date="2024-01-01"),
    # #     StatementExtraction(description="购物", amount=100.0, date="2024-01-02"),
    # #     StatementExtraction(description="消费", amount=100.0, date="2024-01-01"),
    # # ]
    
    # # 每个字段单独投票，选出现最多的值
    # descriptions = [r.description for r in results if r.description]
    # amounts = [r.amount for r in results if r.amount]
    # dates = [r.transaction_date for r in results if r.transaction_date]

    # return StatementExtraction(
    #     description=max(set(descriptions), key=descriptions.count),
    #     amount=max(set(amounts), key=amounts.count),
    #     transaction_date=max(set(dates), key=dates.count)
    # )

        record = self.statement.transform_and_save(filename, raw_text, extraction)
        if not record:
            raise ValueError("Failed to save the extracted data to the database.")
        return record
    
    def get_statement_result(self, statement_id: int):
        return self.statement.get_by_id(statement_id)

