from dataclasses import dataclass
from typing import Protocol


class ContextChunk(Protocol):
    chunk_id: int
    text: str
    char_start: int
    char_end: int
    token_estimate: int


@dataclass
class AssembledContext:
    text: str
    source_chunk_ids: list[int]
    total_token_estimate: int
    dropped_chunk_ids: list[int]


class ContextAssembler:
    """Builds model context from retrieved chunks under a concrete token budget."""

    def __init__(self, max_context_tokens: int = 1800):
        self.max_context_tokens = max_context_tokens

    def assemble(self, chunks: list[ContextChunk], scores: dict[int, float] | None = None) -> AssembledContext:
        selected: list[ContextChunk] = []
        dropped: list[int] = []
        total_tokens = 0

        for chunk in chunks:
            if total_tokens + chunk.token_estimate > self.max_context_tokens:
                dropped.append(chunk.chunk_id)
                continue
            selected.append(chunk)
            total_tokens += chunk.token_estimate

        score_map = scores or {}
        text = "\n\n--- Retrieved chunk ---\n\n".join(
            (
                f"[chunk_id={chunk.chunk_id} "
                f"char_start={chunk.char_start} char_end={chunk.char_end} "
                f"token_estimate={chunk.token_estimate} "
                f"score={score_map.get(chunk.chunk_id, 0):.4f}]\n"
                f"{chunk.text}"
            )
            for chunk in selected
        )
        return AssembledContext(
            text=text,
            source_chunk_ids=[chunk.chunk_id for chunk in selected],
            total_token_estimate=total_tokens,
            dropped_chunk_ids=dropped,
        )
