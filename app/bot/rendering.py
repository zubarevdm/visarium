"""Сборка итогового сообщения об этапе. Дисклеймер добавляется здесь, кодом.

Коридоры и подсказки — детерминированные (из domain/corridors.py). Подробный план —
сгенерирован нейросетью из блоков БЗ (planner), передаётся готовым текстом.
"""

from app.bot.i18n import t
from app.domain.models import Corridor, PersonalDeadline, StageResult
from app.payments.gating import FeatureSet


def render_result(
    stage_result: StageResult,
    deadlines: list[PersonalDeadline],
    features: FeatureSet,
    lang: str,
    corridors: list[Corridor] | None = None,
    suggestions: list[str] | None = None,
    plan_text: str | None = None,
) -> str:
    corridors = corridors or []
    suggestions = suggestions or []

    lines = [t("result.header", lang, stage=t(f"stage.{stage_result.current_stage.value}", lang))]

    for note_key in stage_result.notes:
        lines.append(t(note_key, lang))

    if stage_result.next_stages:
        lines.append(t("result.next_step", lang, next_stage=t(f"stage.{stage_result.next_stages[0].value}", lang)))
    else:
        lines.append(t("result.final_stage", lang))

    if features.full_roadmap:
        if corridors:
            lines.append("")
            lines.append(t("result.corridors_header", lang))
            lines.extend(f"• {t(f'corridor.{c.value}', lang)}" for c in corridors)

        if stage_result.required_documents:
            lines.append("")
            lines.append(t("result.documents_header", lang))
            lines.extend(f"• {t(doc_key, lang)}" for doc_key in stage_result.required_documents)

        lines.append("")
        lines.append(t("result.deadlines_header", lang))
        if deadlines:
            for d in deadlines[:6]:
                key = "result.deadline_line_overdue" if d.overdue else "result.deadline_line"
                lines.append(
                    t(key, lang, date=d.due_date.strftime("%d.%m.%Y"), what=t(d.description_key, lang))
                )
        else:
            lines.append(t("result.no_deadlines", lang))

        if plan_text:
            lines.append("")
            lines.append(t("result.plan_header", lang))
            lines.append(plan_text)

        if suggestions:
            lines.append("")
            lines.append(t("result.suggestions_header", lang))
            lines.extend(f"• {t(key, lang)}" for key in suggestions)
    else:
        lines.append("")
        lines.append(t("result.free_teaser", lang))

    return "\n".join(lines) + t("disclaimer", lang)
