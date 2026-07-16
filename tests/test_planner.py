"""Планировщик: план строится только из блоков БЗ; коридор подтягивает упрощёнку."""

from datetime import date

from app.ai.planner import Planner
from app.ai.rag import KBBlock
from app.domain.models import Citizenship, Corridor, Goal, Stage, StageResult, UserFacts

PATENT_BLOCK = KBBlock(content="Про патент", stage="patent", source_file="patent.md")
SIMPLIFIED_BLOCK = KBBlock(content="Про упрощёнку", stage="simplified", source_file="simplified.md")


class FakeRetriever:
    def __init__(self, by_stage: dict[str, list[KBBlock]]) -> None:
        self.by_stage = by_stage
        self.stages_queried: list[str | None] = []

    async def retrieve(self, question, stage=None, citizenship=None):
        self.stages_queried.append(stage)
        return list(self.by_stage.get(stage, []))


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[KBBlock]]] = []

    async def compose_response(self, question, blocks):
        self.calls.append((question, blocks))
        return "Пошаговый план."

    async def extract_facts(self, user_text):  # часть протокола, здесь не нужна
        return UserFacts()


def _facts(**kw) -> UserFacts:
    base = dict(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 6, 1),
        migration_registered=True,
        has_patent=True,
        has_rvp=False,
        has_vnj=False,
        goal=Goal.CITIZENSHIP,
    )
    base.update(kw)
    return UserFacts(**base)


def _stage(stage: Stage) -> StageResult:
    return StageResult(current_stage=stage, next_stages=[], required_documents=[])


async def test_plan_from_stage_blocks():
    llm = FakeLLM()
    planner = Planner(FakeRetriever({"patent": [PATENT_BLOCK]}), llm)
    text = await planner.build_plan(_facts(), _stage(Stage.PATENT), corridors=[], lang="ru")
    assert text == "Пошаговый план."
    assert llm.calls[0][1] == [PATENT_BLOCK]


async def test_corridor_pulls_simplified_blocks():
    llm = FakeLLM()
    retriever = FakeRetriever({"patent": [PATENT_BLOCK], "simplified": [SIMPLIFIED_BLOCK]})
    planner = Planner(retriever, llm)
    await planner.build_plan(
        _facts(), _stage(Stage.PATENT), corridors=[Corridor.CITIZENSHIP_WITHOUT_5Y], lang="ru"
    )
    assert "simplified" in retriever.stages_queried
    assert SIMPLIFIED_BLOCK in llm.calls[0][1]


async def test_no_blocks_means_no_plan_and_no_llm_call():
    llm = FakeLLM()
    planner = Planner(FakeRetriever({}), llm)
    text = await planner.build_plan(_facts(), _stage(Stage.PATENT), corridors=[], lang="ru")
    assert text is None
    assert llm.calls == []
