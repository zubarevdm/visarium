"""RAG: approved-only индексация, фильтры ретривера, пустая выдача."""

from dataclasses import dataclass
from pathlib import Path

from app.ai.rag import Retriever
from app.core.embeddings import FakeEmbedder
from scripts.index_kb import (
    KB_DIR,
    chunk_document,
    filter_indexable,
    load_documents,
    parse_document,
)

FIXTURES = Path(__file__).parent / "fixtures_kb"


def _write(path: Path, status: str, stage: str = "patent") -> None:
    path.write_text(
        f"---\nstage: {stage}\napplies_to: [tj, uz]\nstatus: {status}\n"
        "reviewed_by: null\nreviewed_at: null\n---\n\n"
        "# Заголовок\n\n## Раздел\n\nТекст блока.\n",
        encoding="utf-8",
    )


def test_only_approved_indexed(tmp_path):
    _write(tmp_path / "ok.md", "approved")
    _write(tmp_path / "wip.md", "draft")
    docs = load_documents(tmp_path)
    indexable = filter_indexable(docs)
    assert [d.source_file for d in indexable] == ["ok.md"]


def test_include_drafts_flag(tmp_path):
    _write(tmp_path / "ok.md", "approved")
    _write(tmp_path / "wip.md", "draft")
    indexable = filter_indexable(load_documents(tmp_path), include_drafts=True)
    assert {d.source_file for d in indexable} == {"ok.md", "wip.md"}


def test_real_kb_indexes_only_approved():
    """В прод-индекс попадают только approved; любые draft — исключаются."""
    docs = load_documents(KB_DIR)
    assert all(d.status in ("approved", "draft") for d in docs)
    indexable = {d.source_file for d in filter_indexable(docs)}
    assert "patent.md" in indexable
    drafts = {d.source_file for d in docs if d.status == "draft"}
    assert not (drafts & indexable)


def test_chunking_carries_metadata(tmp_path):
    _write(tmp_path / "ok.md", "approved", stage="rvp")
    doc = parse_document(tmp_path / "ok.md", tmp_path)
    chunks = chunk_document(doc)
    assert chunks
    assert all(c.stage == "rvp" for c in chunks)
    assert all(c.applies_to == ("tj", "uz") for c in chunks)
    assert all("Заголовок" in c.content for c in chunks)


def test_long_section_split(tmp_path):
    body = "\n\n".join(f"Абзац {i}. " + "х" * 300 for i in range(6))
    (tmp_path / "long.md").write_text(
        f"---\nstage: patent\napplies_to: [tj]\nstatus: approved\n---\n\n## Один раздел\n\n{body}\n",
        encoding="utf-8",
    )
    doc = parse_document(tmp_path / "long.md", tmp_path)
    chunks = chunk_document(doc, max_chars=900)
    assert len(chunks) > 1
    assert all(len(c.content) <= 1000 for c in chunks)


@dataclass
class _Row:
    content: str
    stage: str
    source_file: str
    applies_to: tuple[str, ...]


class FakeSearcher:
    """Повторяет фильтры KBRepo в памяти; косинусную сортировку не имитирует."""

    def __init__(self, rows: list[_Row]) -> None:
        self.rows = rows
        self.calls: list[dict] = []

    async def search(self, embedding, stage, citizenship, limit=4):
        self.calls.append({"stage": stage, "citizenship": citizenship})
        assert isinstance(embedding, list) and embedding  # ретривер обязан передать вектор
        result = self.rows
        if stage:
            result = [r for r in result if r.stage == stage]
        if citizenship:
            result = [r for r in result if citizenship in r.applies_to]
        return result[:limit]


ROWS = [
    _Row("Про патент", "patent", "patent.md", ("tj", "uz")),
    _Row("Про РВП", "rvp", "rvp.md", ("tj", "uz", "kg")),
    _Row("Про учёт", "migration_registration", "migration_registration.md", ("tj", "uz", "kg")),
]


async def test_retriever_filters_by_stage_and_citizenship():
    retriever = Retriever(FakeSearcher(ROWS), FakeEmbedder(dim=8))
    blocks = await retriever.retrieve("сколько платить за патент", stage="patent", citizenship="tj")
    assert [b.source_file for b in blocks] == ["patent.md"]


async def test_retriever_empty_result_is_empty_list():
    """Нет подходящих блоков -> [], выше по стеку это честный отказ."""
    retriever = Retriever(FakeSearcher(ROWS), FakeEmbedder(dim=8))
    blocks = await retriever.retrieve("вопрос", stage="patent", citizenship="kg")
    assert blocks == []


async def test_retriever_no_filters_returns_all():
    searcher = FakeSearcher(ROWS)
    retriever = Retriever(searcher, FakeEmbedder(dim=8))
    blocks = await retriever.retrieve("общий вопрос")
    assert len(blocks) == 3
    assert searcher.calls[0] == {"stage": None, "citizenship": None}
