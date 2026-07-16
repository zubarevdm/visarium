"""Упрощённые коридоры и проактивные подсказки. Никакого LLM — чистые функции.

Правило проекта: какие варианты вообще существуют для человека, решает этот код
по выверенным данным. Нейросеть потом только оформляет и объясняет — не выдумывает.
"""

from app.domain.models import (
    AgeBracket,
    Corridor,
    EAEU_CITIZENSHIPS,
    Ground,
    UserFacts,
)

# Основания -> какой коридор открывают (по гайду 2026, ветка Д).
_VNJ_WITHOUT_RVP_GROUNDS = frozenset(
    {Ground.FAMILY_RF, Ground.BORN_USSR, Ground.RESETTLEMENT}
)
_CITIZENSHIP_WITHOUT_5Y_GROUNDS = frozenset(
    {Ground.SPOUSE_RF, Ground.RF_DIPLOMA, Ground.NATIVE_SPEAKER, Ground.BORN_USSR}
)

# Адресная подсказка под конкретное основание (стабильный порядок вывода).
_GROUND_SUGGESTIONS: tuple[tuple[Ground, str], ...] = (
    (Ground.RF_DIPLOMA, "suggest.ground_rf_diploma"),
    (Ground.FAMILY_RF, "suggest.ground_family_rf"),
    (Ground.BORN_USSR, "suggest.ground_born_ussr"),
    (Ground.RESETTLEMENT, "suggest.ground_resettlement"),
    (Ground.NATIVE_SPEAKER, "suggest.ground_native_speaker"),
)


def _grounds_set(facts: UserFacts) -> set[Ground]:
    result: set[Ground] = set()
    for raw in facts.grounds or []:
        try:
            result.add(Ground(raw))
        except ValueError:
            continue
    result.discard(Ground.NONE)
    return result


def applicable_corridors(facts: UserFacts) -> list[Corridor]:
    """Какие упрощённые пути доступны человеку по его основаниям."""
    grounds = _grounds_set(facts)
    corridors: list[Corridor] = []
    if grounds & _VNJ_WITHOUT_RVP_GROUNDS:
        corridors.append(Corridor.VNJ_WITHOUT_RVP)
    if grounds & _CITIZENSHIP_WITHOUT_5Y_GROUNDS:
        corridors.append(Corridor.CITIZENSHIP_WITHOUT_5Y)
    if Ground.RESETTLEMENT in grounds:
        corridors.append(Corridor.CITIZENSHIP_DIRECT)
    return corridors


def suggestions(facts: UserFacts, corridors: list[Corridor]) -> list[str]:
    """Проактивные адресные подсказки (ключи i18n). Только на основе выверенных коридоров."""
    grounds = _grounds_set(facts)
    out: list[str] = []

    young = facts.age_bracket in (AgeBracket.UNDER_18, AgeBracket.A18_24)
    if (
        young
        and Ground.RF_DIPLOMA not in grounds
        and Corridor.CITIZENSHIP_WITHOUT_5Y not in corridors
    ):
        # диплом вуза РФ + год работы по специальности -> упрощённое гражданство
        out.append("suggest.university")

    if Ground.SPOUSE_RF in grounds:
        out.append("suggest.spouse_child")

    # адресные подсказки под каждое указанное основание
    for ground, key in _GROUND_SUGGESTIONS:
        if ground in grounds:
            out.append(key)

    if facts.citizenship in EAEU_CITIZENSHIPS:
        out.append("suggest.eaeu")

    return out
