"""Эмбеддинги: локальная multilingual-e5 или детерминированная заглушка для dev/тестов."""

import hashlib
import math
from typing import Protocol

from app.config import Settings


class Embedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...


class LocalE5Embedder:
    """intfloat/multilingual-e5-*: требует префиксы query:/passage:."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # ленивый импорт тяжёлой зависимости

        self._model = SentenceTransformer(model_name)

    async def embed_query(self, text: str) -> list[float]:
        return self._model.encode([f"query: {text}"], normalize_embeddings=True)[0].tolist()

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            [f"passage: {t}" for t in texts], normalize_embeddings=True
        )
        return [v.tolist() for v in vectors]


class FakeEmbedder:
    """Детерминированный hash-вектор. Только dev/тесты — семантики нет."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        values = [seed[i % len(seed)] / 255.0 - 0.5 for i in range(self.dim)]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


def get_embedder(settings: Settings) -> Embedder:
    if settings.embedding_backend == "fake":
        return FakeEmbedder(settings.embedding_dim)
    return LocalE5Embedder(settings.embedding_model)
