from dataclasses import dataclass
import math
import re

from openai import AsyncOpenAI

from src.core.config import settings


@dataclass
class DocumentChunk:
    chunk_id: int
    text: str
    embedding: list[float]


class RAGService:
    """Small in-memory RAG layer for single-document retrieval."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = "text-embedding-3-small"

    def chunk_text(self, text: str, chunk_size: int = 1800, overlap: int = 250) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            if len(paragraph) > chunk_size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                for start in range(0, len(paragraph), chunk_size - overlap):
                    chunks.append(paragraph[start:start + chunk_size].strip())
                continue

            next_text = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(next_text) <= chunk_size:
                current = next_text
            else:
                chunks.append(current.strip())
                current = paragraph

        if current:
            chunks.append(current.strip())

        return chunks or [text[:chunk_size]]

    async def build_index(self, text: str) -> list[DocumentChunk]:
        chunks = self.chunk_text(text)
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=chunks,
        )
        return [
            DocumentChunk(chunk_id=i, text=chunk, embedding=item.embedding)
            for i, (chunk, item) in enumerate(zip(chunks, response.data))
        ]

    async def retrieve(self, index: list[DocumentChunk], query: str, top_k: int = 4) -> str:
        if not index:
            return ""

        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=query,
        )
        query_embedding = response.data[0].embedding
        ranked = sorted(
            index,
            key=lambda chunk: self._cosine_similarity(query_embedding, chunk.embedding),
            reverse=True,
        )
        selected = ranked[:top_k]
        return "\n\n--- Retrieved chunk ---\n\n".join(chunk.text for chunk in selected)

    def retrieval_query_for(self, form_type: str) -> str:
        if form_type == "bank_statement":
            return (
                "bank statement transactions, transaction descriptions, dates, "
                "debits, credits, withdrawals, deposits, and amounts"
            )
        if form_type == "athlete contract":
            return (
                "contract parties, contract title, effective date, expiration date, "
                "term, compensation, total contract value, and currency"
            )
        return "important fields and facts for structured document extraction"

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
