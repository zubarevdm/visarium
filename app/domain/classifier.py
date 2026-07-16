"""Детерминированная классификация этапа. Никакого LLM.

classify() — чистая функция: структурированные факты -> этап + пути дальше.
Порядок проверок фиксирован: документы старшего этапа перекрывают младшие.
"""

from app.domain.models import (
    EAEU_CITIZENSHIPS,
    Goal,
    Stage,
    StageResult,
    UserFacts,
)
from app.domain.stages import STAGES

# Факты, без которых классификация ненадёжна, в порядке приоритета вопросов.
REQUIRED_FACTS: tuple[str, ...] = (
    "citizenship",
    "entry_date",
    "migration_registered",
    "has_vnj",
    "has_rvp",
    "has_patent",
    "goal",
)

# Для граждан ЕАЭС патент не нужен — вопрос о нём пропускаем.
_EAEU_SKIPPED_FACTS = frozenset({"has_patent"})


def missing_facts(facts: UserFacts) -> list[str]:
    """Каких обязательных фактов ещё нет (в порядке, в котором их спрашивать)."""
    is_eaeu = facts.citizenship in EAEU_CITIZENSHIPS
    missing = []
    for name in REQUIRED_FACTS:
        if is_eaeu and name in _EAEU_SKIPPED_FACTS:
            continue
        if getattr(facts, name) is None:
            missing.append(name)
    return missing


def is_complete(facts: UserFacts) -> bool:
    return not missing_facts(facts)


def _goal_rank(goal: Goal | None) -> int:
    order = {Goal.WORK: 1, Goal.RVP: 2, Goal.VNJ: 3, Goal.CITIZENSHIP: 4}
    return order.get(goal, 1)


def classify(facts: UserFacts) -> StageResult:
    """Определяет текущий этап по фактам. Требует полных фактов (is_complete)."""
    is_eaeu = facts.citizenship in EAEU_CITIZENSHIPS
    notes: list[str] = ["note.eaeu_no_patent"] if is_eaeu else []
    goal_rank = _goal_rank(facts.goal)

    if facts.has_vnj:
        current = Stage.VNJ
        next_stages = [Stage.CITIZENSHIP] if goal_rank >= 4 else []
    elif facts.has_rvp:
        current = Stage.RVP
        next_stages = [Stage.VNJ] if goal_rank >= 3 else []
    elif facts.has_patent and not is_eaeu:
        current = Stage.PATENT
        next_stages = [Stage.RVP] if goal_rank >= 2 else []
    elif facts.migration_registered:
        current = Stage.MIGRATION_REGISTRATION
        if is_eaeu:
            # ЕАЭС: работа доступна без патента, дальше — сразу РВП при желании
            next_stages = [Stage.RVP] if goal_rank >= 2 else []
        else:
            next_stages = [Stage.PATENT] if goal_rank >= 1 else []
    else:
        current = Stage.ENTRY
        next_stages = [Stage.MIGRATION_REGISTRATION]

    # Чек-лист документов — для ближайшего следующего шага
    required_documents: list[str] = []
    if next_stages:
        required_documents = list(STAGES[next_stages[0]].documents)

    return StageResult(
        current_stage=current,
        next_stages=next_stages,
        required_documents=required_documents,
        notes=notes,
    )
