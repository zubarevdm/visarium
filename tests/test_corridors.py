"""Табличные тесты упрощённых коридоров и проактивных подсказок."""

from datetime import date

import pytest

from app.domain.corridors import applicable_corridors, suggestions
from app.domain.models import AgeBracket, Citizenship, Corridor, Goal, Ground, UserFacts

ENTRY = date(2026, 6, 1)


def facts(**kwargs) -> UserFacts:
    base = dict(
        citizenship=Citizenship.TJ,
        entry_date=ENTRY,
        migration_registered=True,
        has_patent=False,
        has_rvp=False,
        has_vnj=False,
        goal=Goal.CITIZENSHIP,
        age_bracket=AgeBracket.A25_59,
        grounds=[],
    )
    base.update(kwargs)
    return UserFacts(**base)


CORRIDOR_MATRIX = [
    ("нет оснований — нет коридоров", [], []),
    ("ничего выбрано (NONE) — нет коридоров", [Ground.NONE], []),
    (
        "супруг РФ — гражданство без 5 лет",
        [Ground.SPOUSE_RF],
        [Corridor.CITIZENSHIP_WITHOUT_5Y],
    ),
    (
        "диплом РФ — гражданство без 5 лет",
        [Ground.RF_DIPLOMA],
        [Corridor.CITIZENSHIP_WITHOUT_5Y],
    ),
    (
        "ребёнок/родитель РФ — ВНЖ без РВП",
        [Ground.FAMILY_RF],
        [Corridor.VNJ_WITHOUT_RVP],
    ),
    (
        "родился в СССР — оба коридора (ВНЖ без РВП и гражданство без 5 лет)",
        [Ground.BORN_USSR],
        [Corridor.VNJ_WITHOUT_RVP, Corridor.CITIZENSHIP_WITHOUT_5Y],
    ),
    (
        "госпрограмма — ВНЖ без РВП и гражданство напрямую",
        [Ground.RESETTLEMENT],
        [Corridor.VNJ_WITHOUT_RVP, Corridor.CITIZENSHIP_DIRECT],
    ),
    (
        "носитель языка — гражданство без 5 лет",
        [Ground.NATIVE_SPEAKER],
        [Corridor.CITIZENSHIP_WITHOUT_5Y],
    ),
]


@pytest.mark.parametrize(
    "label,grounds,expected", CORRIDOR_MATRIX, ids=[m[0] for m in CORRIDOR_MATRIX]
)
def test_applicable_corridors(label, grounds, expected):
    assert applicable_corridors(facts(grounds=grounds)) == expected


def test_grounds_stored_as_strings_are_coerced():
    """Из FSM основания приходят строками — коридоры всё равно определяются."""
    f = facts(grounds=["spouse_rf"])
    assert applicable_corridors(f) == [Corridor.CITIZENSHIP_WITHOUT_5Y]


def test_suggest_university_for_young_without_diploma():
    f = facts(age_bracket=AgeBracket.A18_24, grounds=[])
    assert "suggest.university" in suggestions(f, applicable_corridors(f))


def test_no_university_suggest_if_already_has_diploma():
    f = facts(age_bracket=AgeBracket.A18_24, grounds=[Ground.RF_DIPLOMA])
    assert "suggest.university" not in suggestions(f, applicable_corridors(f))


def test_no_university_suggest_for_older_age():
    f = facts(age_bracket=AgeBracket.A25_59, grounds=[])
    assert "suggest.university" not in suggestions(f, applicable_corridors(f))


def test_suggest_spouse_child():
    f = facts(grounds=[Ground.SPOUSE_RF])
    assert "suggest.spouse_child" in suggestions(f, applicable_corridors(f))


def test_suggest_eaeu_for_kg():
    f = facts(citizenship=Citizenship.KG)
    assert "suggest.eaeu" in suggestions(f, applicable_corridors(f))


def test_ground_specific_suggestion():
    """Подсказка адресная: под конкретное основание — свой текст."""
    f = facts(grounds=[Ground.FAMILY_RF])
    keys = suggestions(f, applicable_corridors(f))
    assert "suggest.ground_family_rf" in keys
    assert "suggest.use_corridor" not in keys  # общей подсказки больше нет


def test_diploma_ground_suggestion():
    f = facts(age_bracket=AgeBracket.A25_59, grounds=[Ground.RF_DIPLOMA])
    assert "suggest.ground_rf_diploma" in suggestions(f, applicable_corridors(f))


def test_no_suggestions_for_plain_older_migrant():
    f = facts(citizenship=Citizenship.UZ, age_bracket=AgeBracket.A25_59, grounds=[])
    assert suggestions(f, applicable_corridors(f)) == []
