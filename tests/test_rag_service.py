import asyncio
from types import SimpleNamespace

from src.services.rag_service import DocumentChunk, RAGService


class FakeEmbeddings:
    async def create(self, model, input):
        items = input if isinstance(input, list) else [input]
        return SimpleNamespace(
            data=[
                SimpleNamespace(embedding=[float(len(str(item))), 1.0])
                for item in items
            ]
        )


def test_retrieve_returns_context_with_source_chunk_ids():
    service = RAGService.__new__(RAGService)
    service.embedding_model = "fake-embedding-model"
    service.client = SimpleNamespace(embeddings=FakeEmbeddings())
    index = [
        DocumentChunk(chunk_id=0, text="short", embedding=[1.0, 0.0]),
        DocumentChunk(chunk_id=1, text="long matching contract value text", embedding=[100.0, 1.0]),
    ]

    result = asyncio.run(service.retrieve(index, "contract value", top_k=1))

    assert result.source_chunk_ids == [1]
    assert "chunk_id=1" in result.context
    assert "char_start=" in result.context
    assert "score=" in result.context
    assert "long matching contract value text" in result.context
