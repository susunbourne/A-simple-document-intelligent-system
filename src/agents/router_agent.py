from openai import AsyncOpenAI
from src.core.config import settings
from src.schemas.router import RouterDeterminationResult

class RouterAgent:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
        )
    async def determine_form_type(self, text: str) -> str:
        prompt = f"""
You are a form type classification assistant. Based on the provided text, determine the type of financial document it represents. The possible types are:{settings.Valid_FORM_TYPES}, and if the text does not match any of these types, respond with "unknown". Be concise and only respond with the form type without any additional explanation.

provided text: {text}
"""
        response = await self.client.responses.parse(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            text_format=RouterDeterminationResult,
            max_output_tokens=100
        )
        return response.output_parsed