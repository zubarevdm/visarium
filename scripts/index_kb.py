"""Индексация базы знаний: knowledge_base/**.md -> kb_chunks (pgvector).

В прод-индекс попадают только блоки со status: approved.
Для локальной разработки: --include-drafts.

Запуск:
    uv run python -m scripts.index_kb [--include-drafts] [--kb-version v1]
"""

import argparse
import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

import frontmatter
from sqlalchemy import delete

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
MAX_CHUNK_CHARS = 900


@dataclass(frozen=True)
class KBDocument:
    source_file: str
    stage: str
    applies_to: tuple[str, ...]
    status: str
    body: str


@dataclass(frozen=True)
class Chunk:
    source_file: str
    stage: str
    applies_to: tuple[str, ...]
    content: str


def parse_document(path: Path, kb_root: Path) -> KBDocument:
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata
    return KBDocument(
        source_file=path.relative_to(kb_root).as_posix(),
        stage=str(meta.get("stage", "")),
        applies_to=tuple(meta.get("applies_to", []) or []),
        status=str(meta.get("status", "draft")),
        body=post.content,
    )


def load_documents(kb_root: Path) -> list[KBDocument]:
    return [parse_document(p, kb_root) for p in sorted(kb_root.rglob("*.md"))]


def filter_indexable(docs: list[KBDocument], include_drafts: bool = False) -> list[KBDocument]:
    """Прод-правило: только approved. Драфты — лишь по явному флагу разработчика."""
    if include_drafts:
        return [d for d in docs if d.status in ("approved", "draft")]
    return [d for d in docs if d.status == "approved"]


def chunk_document(doc: KBDocument, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """Чанкует по разделам `## ...`; слишком длинные разделы режет по абзацам."""
    sections: list[str] = []
    current: list[str] = []
    title = ""
    for line in doc.body.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            if current:
                sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())

    chunks: list[Chunk] = []
    for section in sections:
        if not section:
            continue
        pieces = [section]
        if len(section) > max_chars:
            pieces, buf = [], ""
            for para in section.split("\n\n"):
                if buf and len(buf) + len(para) + 2 > max_chars:
                    pieces.append(buf)
                    buf = para
                else:
                    buf = f"{buf}\n\n{para}" if buf else para
            if buf:
                pieces.append(buf)
        for piece in pieces:
            content = f"{title}\n\n{piece}".strip() if title else piece
            chunks.append(
                Chunk(
                    source_file=doc.source_file,
                    stage=doc.stage,
                    applies_to=doc.applies_to,
                    content=content,
                )
            )
    return chunks


def kb_version_hash(docs: list[KBDocument]) -> str:
    digest = hashlib.sha256()
    for doc in docs:
        digest.update(doc.source_file.encode())
        digest.update(doc.body.encode())
    return digest.hexdigest()[:12]


async def index_kb(include_drafts: bool, kb_version: str | None) -> int:
    from app.config import get_settings
    from app.core.embeddings import get_embedder
    from app.db.models import KBChunk
    from app.db.session import create_engine_and_sessionmaker

    settings = get_settings()
    embedder = get_embedder(settings)

    docs = filter_indexable(load_documents(KB_DIR), include_drafts=include_drafts)
    version = kb_version or kb_version_hash(docs)
    chunks = [chunk for doc in docs for chunk in chunk_document(doc)]
    if not chunks:
        print("Нет approved-блоков для индексации.")
        return 0

    embeddings = await embedder.embed_passages([c.content for c in chunks])

    engine, sessionmaker = create_engine_and_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(delete(KBChunk))  # полная переиндексация
        for chunk, embedding in zip(chunks, embeddings):
            session.add(
                KBChunk(
                    stage=chunk.stage,
                    applies_to=list(chunk.applies_to),
                    content=chunk.content,
                    embedding=embedding,
                    source_file=chunk.source_file,
                    kb_version=version,
                )
            )
        await session.commit()
    await engine.dispose()
    print(f"Проиндексировано чанков: {len(chunks)} (kb_version={version})")
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Индексация базы знаний в pgvector")
    parser.add_argument("--include-drafts", action="store_true", help="включать draft (только dev)")
    parser.add_argument("--kb-version", default=None)
    args = parser.parse_args()
    asyncio.run(index_kb(args.include_drafts, args.kb_version))


if __name__ == "__main__":
    main()
