"""RAG-ретривер: фильтр по метаданным этапа/гражданства + векторный поиск.

В kb_chunks лежат только approved-блоки (это гарантирует scripts/index_kb.py),
поэтому ретривер по построению не может вернуть невыверенный контент.
Пустая выдача — валидный результат: выше по стеку это честный отказ, не импровизация.
"""

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.core.embeddings import Embedder


@dataclass(frozen=True)
class KBBlock:
    content: str
    stage: str
    source_file: str


class ChunkSearcher(Protocol):
    """Порт к хранилищу чанков (реализация — app.db.repositories.KBRepo)."""

    async def search(
        self, embedding: list[float], stage: str | None, citizenship: str | None, limit: int = 4
    ) -> Sequence: ...


class Retriever:
    def __init__(self, searcher: ChunkSearcher, embedder: Embedder, limit: int = 4) -> None:
        self._searcher = searcher
        self._embedder = embedder
        self._limit = limit

    async def retrieve(
        self, question: str, stage: str | None = None, citizenship: str | None = None
    ) -> list[KBBlock]:
        embedding = await self._embedder.embed_query(question)
        rows = await self._searcher.search(embedding, stage=stage, citizenship=citizenship, limit=self._limit)
        return [KBBlock(content=r.content, stage=r.stage, source_file=r.source_file) for r in rows]
