from dataclasses import dataclass
from collections import Counter
import math
import re

from openai import AsyncOpenAI

from src.core.config import settings
from src.services.context_service import ContextAssembler


@dataclass
class DocumentChunk:
    chunk_id: int
    text: str
    embedding: list[float]
    char_start: int = 0
    char_end: int = 0
    token_estimate: int = 0
    section_index: int = 0


@dataclass
class RetrievalResult:
    context: str
    source_chunk_ids: list[int]
    source_chunks: list[DocumentChunk]
    retrieval_query: str
    scores: dict[int, float]


class RAGService:
    """Small in-memory RAG layer for single-document retrieval."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL

    def chunk_text(self, text: str, chunk_size: int = 1800, overlap: int = 250) -> list[str]:
        return [chunk.text for chunk in self.chunk_text_with_metadata(text, chunk_size, overlap)]

    def chunk_text_with_metadata(
        self,
        text: str,
        chunk_size: int = 1800,
        overlap: int = 250,
    ) -> list[DocumentChunk]:
        paragraphs = [
            (match.start(), match.end(), match.group().strip())
            for match in re.finditer(r"\S(?:.*?)(?=\n\s*\n|\Z)", text, flags=re.DOTALL)
            if match.group().strip()
        ]
        chunks: list[str] = []
        spans: list[tuple[int, int, int]] = []
        current = ""
        current_start: int | None = None
        current_end = 0
        section_index = 0

        for paragraph_start, paragraph_end, paragraph in paragraphs:
            if len(paragraph) > chunk_size:
                if current:
                    chunks.append(current.strip())
                    spans.append((current_start or 0, current_end, section_index))
                    current = ""
                    current_start = None
                for start in range(0, len(paragraph), chunk_size - overlap):
                    end = min(start + chunk_size, len(paragraph))
                    chunk = paragraph[start:end].strip()
                    if chunk:
                        chunks.append(chunk)
                        spans.append((paragraph_start + start, paragraph_start + end, section_index))
                        section_index += 1
                continue

            next_text = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(next_text) <= chunk_size:
                if current_start is None:
                    current_start = paragraph_start
                current = next_text
                current_end = paragraph_end
            else:
                chunks.append(current.strip())
                spans.append((current_start or 0, current_end, section_index))
                section_index += 1
                current = paragraph
                current_start = paragraph_start
                current_end = paragraph_end

        if current:
            chunks.append(current.strip())
            spans.append((current_start or 0, current_end, section_index))

        if not chunks:
            chunks = [text[:chunk_size]]
            spans = [(0, min(len(text), chunk_size), 0)]

        return [
            DocumentChunk(
                chunk_id=i,
                text=chunk,
                embedding=[],
                char_start=start,
                char_end=end,
                token_estimate=self._estimate_tokens(chunk),
                section_index=section,
            )
            for i, (chunk, (start, end, section)) in enumerate(zip(chunks, spans))
        ]

    async def build_index(self, text: str) -> list[DocumentChunk]:
        chunks = self.chunk_text_with_metadata(text)
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=[chunk.text for chunk in chunks],
        )
        for chunk, item in zip(chunks, response.data):
            chunk.embedding = item.embedding
        return chunks

    async def retrieve(self, index: list[DocumentChunk], query: str, top_k: int = 4) -> RetrievalResult:
        if not index:
            return RetrievalResult(
                context="",
                source_chunk_ids=[],
                source_chunks=[],
                retrieval_query=query,
                scores={},
            )

        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=query,
        )
        query_embedding = response.data[0].embedding
        scores = {
            chunk.chunk_id: self._cosine_similarity(query_embedding, chunk.embedding)
            for chunk in index
        }
        ranked = sorted(index, key=lambda chunk: scores[chunk.chunk_id], reverse=True)
        selected = ranked[:top_k]
        assembled = ContextAssembler().assemble(
            selected,
            scores={chunk.chunk_id: scores[chunk.chunk_id] for chunk in selected},
        )
        return RetrievalResult(
            context=assembled.text,
            source_chunk_ids=assembled.source_chunk_ids,
            source_chunks=selected,
            retrieval_query=query,
            scores={chunk.chunk_id: scores[chunk.chunk_id] for chunk in selected},
        )

    def retrieval_query_for(self, form_type: str) -> str:
        if form_type == "bank_statement":
            return (
                "bank statement transactions, transaction descriptions, dates, "
                "debits, credits, withdrawals, deposits, and amounts"
            )
        if form_type in {"athlete_contract", "athlete contract"}:
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

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Rough, model-agnostic estimate used for context budgeting and eval reporting.
        return max(1, math.ceil(len(text) / 4))


class LexicalRetriever:
    """Deterministic BM25 baseline for offline retrieval evaluation.

    This is not a replacement for the production embedding path. It gives the
    team a free, reproducible baseline and exposes cases where semantic
    retrieval must beat simple term matching.
    """

    TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
    STOPWORDS = {
        "a", "an", "and", "any", "are", "be", "by", "contract", "details",
        "document", "for", "from", "highlight", "if", "in", "is", "it", "of",
        "on", "or", "parts", "related", "should", "that", "the", "this", "to",
        "what", "when", "which", "who", "with",
    }

    @dataclass(frozen=True)
    class Index:
        chunks: list[DocumentChunk]
        term_counts: list[Counter]
        document_frequency: Counter
        average_length: float

    def build_index(self, chunks: list[DocumentChunk]) -> "LexicalRetriever.Index":
        tokenized = [self._terms(chunk.text) for chunk in chunks]
        return self.Index(
            chunks=chunks,
            term_counts=[Counter(terms) for terms in tokenized],
            document_frequency=Counter(
                term for terms in tokenized for term in set(terms)
            ),
            average_length=(
                sum(len(terms) for terms in tokenized) / len(tokenized)
                if tokenized
                else 0.0
            ),
        )

    def retrieve(
        self,
        chunks: list[DocumentChunk],
        query: str,
        *,
        top_k: int = 5,
    ) -> RetrievalResult:
        return self.retrieve_index(self.build_index(chunks), query, top_k=top_k)

    def retrieve_index(
        self,
        index: "LexicalRetriever.Index",
        query: str,
        *,
        top_k: int = 5,
    ) -> RetrievalResult:
        chunks = index.chunks
        if not chunks:
            return RetrievalResult("", [], [], query, {})
        query_terms = self._terms(query)
        scores = {
            chunk.chunk_id: self._bm25_score(
                query_terms,
                index.term_counts[chunk_index],
                sum(index.term_counts[chunk_index].values()),
                index.average_length,
                index.document_frequency,
                len(chunks),
            )
            for chunk_index, chunk in enumerate(chunks)
        }
        ranked = sorted(
            chunks,
            key=lambda chunk: (scores[chunk.chunk_id], -chunk.chunk_id),
            reverse=True,
        )
        selected = ranked[:top_k]
        assembled = ContextAssembler().assemble(
            selected,
            scores={chunk.chunk_id: scores[chunk.chunk_id] for chunk in selected},
        )
        return RetrievalResult(
            context=assembled.text,
            source_chunk_ids=assembled.source_chunk_ids,
            source_chunks=selected,
            retrieval_query=query,
            scores={chunk.chunk_id: scores[chunk.chunk_id] for chunk in selected},
        )

    def _terms(self, text: str) -> list[str]:
        return [
            term
            for term in self.TOKEN_PATTERN.findall(text.lower())
            if term not in self.STOPWORDS and len(term) > 1
        ]

    @staticmethod
    def _bm25_score(
        query_terms: list[str],
        term_counts: Counter,
        document_length: int,
        average_length: float,
        document_frequency: Counter,
        document_count: int,
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> float:
        score = 0.0
        for term in set(query_terms):
            frequency = term_counts[term]
            if not frequency:
                continue
            frequency_in_documents = document_frequency[term]
            inverse_document_frequency = math.log(
                1 + (document_count - frequency_in_documents + 0.5) / (frequency_in_documents + 0.5)
            )
            denominator = frequency + k1 * (
                1 - b + b * document_length / max(average_length, 1)
            )
            score += inverse_document_frequency * frequency * (k1 + 1) / denominator
        return score
