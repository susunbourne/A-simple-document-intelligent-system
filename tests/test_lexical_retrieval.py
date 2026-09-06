from src.services.rag_service import DocumentChunk, LexicalRetriever


def test_lexical_retriever_returns_clause_with_query_terms():
    chunks = [
        DocumentChunk(0, "General background and recitals.", [], 0, 32, 8, 0),
        DocumentChunk(
            1,
            "This agreement expires on December 31, 2028 unless renewed.",
            [],
            33,
            95,
            16,
            1,
        ),
        DocumentChunk(2, "The parties provide routine notices.", [], 96, 132, 9, 2),
    ]

    result = LexicalRetriever().retrieve(
        chunks,
        "expires renewed",
        top_k=1,
    )

    assert result.source_chunk_ids == [1]
    assert "expires" in result.context
