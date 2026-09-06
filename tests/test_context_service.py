from src.services.context_service import ContextAssembler
from src.services.rag_service import DocumentChunk


def test_context_assembler_enforces_token_budget_and_keeps_metadata():
    chunks = [
        DocumentChunk(
            chunk_id=1,
            text="contract party and value",
            embedding=[],
            char_start=10,
            char_end=34,
            token_estimate=6,
            section_index=0,
        ),
        DocumentChunk(
            chunk_id=2,
            text="extra unrelated appendix",
            embedding=[],
            char_start=100,
            char_end=124,
            token_estimate=8,
            section_index=1,
        ),
    ]

    assembled = ContextAssembler(max_context_tokens=6).assemble(chunks, scores={1: 0.9, 2: 0.1})

    assert assembled.source_chunk_ids == [1]
    assert assembled.dropped_chunk_ids == [2]
    assert assembled.total_token_estimate == 6
    assert "chunk_id=1" in assembled.text
    assert "char_start=10" in assembled.text
    assert "extra unrelated appendix" not in assembled.text
