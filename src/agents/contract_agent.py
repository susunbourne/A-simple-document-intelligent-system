from openai import AsyncOpenAI
from src.core.config import settings
from src.schemas.athlete_contract import AthleteContractExtraction, AthleteContractExtractionList


class ExtractionService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,

        )
    # async def extract_data_with_Gemini/Claude(self, text: str) -> StatementExtraction:
    async def extract_data(self, text: str) -> AthleteContractExtractionList:
        prompt = f"""
You are a contract data extraction assistant. Extract the following information from the provided text:
- contract_name: The name of the contract. Be loyal to the original text and do not modify it.
- party_a: The first party involved in the contract. Be loyal to the original text and do not modify it.
- party_b: The second party involved in the contract. Be loyal to the original text and do not modify it.
- effective_date: The date when the contract becomes effective. It should be in YYYY-MM-DD format. 
- expiration_date: The date when the contract expires. It should be in YYYY-MM-DD format.
- contract_value: The total value of the contract. It should be a purely numeric value without currency symbols or commas.
- currency: The currency of the contract value. It should be a standard three-letter currency code (e.g., USD, EUR, GBP).   

The format is a List, so it should return List, each List contains the above information. If there is no information, please return null for that field. Be loyal to the original text and do not modify it.

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
            text_format=AthleteContractExtractionList,
            max_output_tokens=1000
        )
        return response.output_parsed