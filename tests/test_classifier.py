"""Табличная матрица «факты -> ожидаемый этап»."""

from datetime import date

import pytest

from app.domain.classifier import classify, is_complete, missing_facts
from app.domain.models import Citizenship, Goal, Stage, UserFacts

ENTRY = date(2026, 6, 1)


def facts(**kwargs) -> UserFacts:
    base = dict(
        citizenship=Citizenship.TJ,
        entry_date=ENTRY,
        migration_registered=False,
        has_patent=False,
        has_rvp=False,
        has_vnj=False,
        goal=Goal.WORK,
    )
    base.update(kwargs)
    return UserFacts(**base)


MATRIX = [
    # (описание, факты, ожидаемый этап, ожидаемые next)
    ("въехал, не встал на учёт", facts(), Stage.ENTRY, [Stage.MIGRATION_REGISTRATION]),
    (
        "на учёте, цель работа (не ЕАЭС)",
        facts(migration_registered=True),
        Stage.MIGRATION_REGISTRATION,
        [Stage.PATENT],
    ),
    (
        "на учёте, гражданин КР (ЕАЭС), цель работа — патент не нужен",
        facts(citizenship=Citizenship.KG, migration_registered=True),
        Stage.MIGRATION_REGISTRATION,
        [],
    ),
    (
        "на учёте, гражданин КР, цель РВП",
        facts(citizenship=Citizenship.KG, migration_registered=True, goal=Goal.RVP),
        Stage.MIGRATION_REGISTRATION,
        [Stage.RVP],
    ),
    (
        "патент есть, цель работа — остаётся на патенте",
        facts(migration_registered=True, has_patent=True),
        Stage.PATENT,
        [],
    ),
    (
        "патент есть, цель ВНЖ — следующий шаг РВП",
        facts(migration_registered=True, has_patent=True, goal=Goal.VNJ),
        Stage.PATENT,
        [Stage.RVP],
    ),
    (
        "РВП есть, цель ВНЖ",
        facts(migration_registered=True, has_rvp=True, goal=Goal.VNJ),
        Stage.RVP,
        [Stage.VNJ],
    ),
    (
        "РВП есть, цель работа — дальше не идёт",
        facts(migration_registered=True, has_rvp=True, goal=Goal.WORK),
        Stage.RVP,
        [],
    ),
    (
        "ВНЖ есть, цель гражданство",
        facts(migration_registered=True, has_vnj=True, goal=Goal.CITIZENSHIP),
        Stage.VNJ,
        [Stage.CITIZENSHIP],
    ),
    (
        "ВНЖ есть, цель ВНЖ — конечная точка",
        facts(migration_registered=True, has_vnj=True, goal=Goal.VNJ),
        Stage.VNJ,
        [],
    ),
    (
        "ВНЖ перекрывает патент и РВП",
        facts(migration_registered=True, has_patent=True, has_rvp=True, has_vnj=True, goal=Goal.CITIZENSHIP),
        Stage.VNJ,
        [Stage.CITIZENSHIP],
    ),
    (
        "РВП перекрывает патент",
        facts(migration_registered=True, has_patent=True, has_rvp=True, goal=Goal.VNJ),
        Stage.RVP,
        [Stage.VNJ],
    ),
    (
        "не на учёте, но с патентом (аномалия) — этап патент",
        facts(migration_registered=False, has_patent=True),
        Stage.PATENT,
        [],
    ),
    (
        "узбекистанец, цель гражданство, только въехал",
        facts(citizenship=Citizenship.UZ, goal=Goal.CITIZENSHIP),
        Stage.ENTRY,
        [Stage.MIGRATION_REGISTRATION],
    ),
]


@pytest.mark.parametrize("label,user_facts,expected_stage,expected_next", MATRIX, ids=[m[0] for m in MATRIX])
def test_classify_matrix(label, user_facts, expected_stage, expected_next):
    result = classify(user_facts)
    assert result.current_stage == expected_stage
    assert result.next_stages == expected_next


def test_next_step_documents_present():
    result = classify(facts(migration_registered=True))
    assert result.next_stages == [Stage.PATENT]
    assert result.required_documents  # чек-лист следующего шага не пуст


def test_eaeu_note_present():
    result = classify(facts(citizenship=Citizenship.KG, migration_registered=True))
    assert "note.eaeu_no_patent" in result.notes


def test_missing_facts_order_and_completeness():
    empty = UserFacts()
    missing = missing_facts(empty)
    assert missing[0] == "citizenship"
    assert "goal" in missing
    assert not is_complete(empty)
    assert is_complete(facts())


def test_eaeu_skips_patent_question():
    partial = UserFacts(
        citizenship=Citizenship.KG,
        entry_date=ENTRY,
        migration_registered=True,
        has_rvp=False,
        has_vnj=False,
        goal=Goal.WORK,
    )
    assert is_complete(partial)  # has_patent не требуется для ЕАЭС


def test_merged_with():
    base = UserFacts(citizenship=Citizenship.TJ)
    update = UserFacts(entry_date=ENTRY, goal=Goal.WORK)
    merged = base.merged_with(update)
    assert merged.citizenship == Citizenship.TJ
    assert merged.entry_date == ENTRY
    assert merged.goal == Goal.WORK
