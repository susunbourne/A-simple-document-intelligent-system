from openai import AsyncOpenAI
from src.core.config import settings
from src.schemas.bank_statement import StatementExtraction


class ExtractionService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,

        )
    # async def extract_data_with_Gemini/Claude(self, text: str) -> StatementExtraction:
    async def extract_data(self, text: str) -> StatementExtraction:
        prompt = f"""
You are a financial data extraction assistant. Extract the following information from the provided text:
- description: The description of the transaction. Be loyal to the original text and do not modify it.
- amount: The amount of the transaction.Purely numeric value without currency symbols or commas.
- transaction_date: The date of the transaction in YYYY-MM-DD format.


Text: {text}
"""
        response = await self.client.responses.parse(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            text_format=StatementExtraction,
            max_output_tokens=1000
        )
        return response.output_parsed
    

