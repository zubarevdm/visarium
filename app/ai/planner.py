"""Генерация персонального плана действий из выверенных блоков базы знаний.

Правило проекта: план строится ТОЛЬКО из блоков БЗ. Нейросеть оформляет по шагам,
но не добавляет фактов, сроков и сумм, которых нет в блоках. Нет блоков — плана нет
(тогда бот показывает статический результат без сгенерированного плана).
"""

import structlog

from app.ai.llm import LLMClient
from app.ai.rag import Retriever
from app.bot.i18n import t
from app.domain.models import Corridor, EAEU_CITIZENSHIPS, StageResult, UserFacts

log = structlog.get_logger()


class Planner:
    def __init__(self, retriever: Retriever, llm: LLMClient) -> None:
        self._retriever = retriever
        self._llm = llm

    async def build_plan(
        self,
        facts: UserFacts,
        stage_result: StageResult,
        corridors: list[Corridor],
        lang: str,
    ) -> str | None:
        stage = stage_result.current_stage.value
        citizenship = facts.citizenship.value if facts.citizenship else None

        blocks = await self._retriever.retrieve(
            question="пошаговый план действий на этом этапе", stage=stage, citizenship=citizenship
        )
        if corridors:
            blocks = blocks + await self._retriever.retrieve(
                question="упрощённый порядок и льготные основания",
                stage="simplified",
                citizenship=citizenship,
            )
        if not blocks:
            return None

        stage_ru = t(f"stage.{stage}", lang)
        goal_key = f"btn.goal.{facts.goal.value}" if facts.goal else "btn.goal.citizenship"
        goal_ru = t(goal_key, lang)

        # Конкретика человека — чтобы план был адресным, а не общим пересказом блока.
        is_eaeu = facts.citizenship in EAEU_CITIZENSHIPS
        cz_name = t(f"btn.citizenship.{citizenship}", lang) if citizenship else "—"
        person = [
            f"Гражданство: {cz_name}" + (" (страна ЕАЭС)" if is_eaeu else " (не входит в ЕАЭС)"),
            f"Текущий статус: {stage_ru}",
            f"Цель: {goal_ru}",
        ]
        ground_names = [
            t(f"btn.ground.{g.value}", lang) for g in facts.grounds if g.value != "none"
        ]
        if ground_names:
            person.append("Льготные основания: " + ", ".join(ground_names))
        context = "\n".join(f"- {line}" for line in person)

        question = (
            f"Ситуация человека:\n{context}\n\n"
            "Составь пошаговый план действий именно для него. Требования:\n"
            "— используй только информацию из блоков базы знаний, ничего не придумывай;\n"
            "— убери варианты, которые к нему не относятся (например, не упоминай патент или "
            "путь для граждан ЕАЭС, если это не его случай);\n"
            "— если у него есть льготное основание, включи соответствующий упрощённый путь;\n"
            "— не добавляй сроков, сумм и условий, которых нет в блоках;\n"
            "— по пунктам, простым языком."
        )
        try:
            text = await self._llm.compose_response(question, blocks)
        except Exception:
            log.warning("plan_compose_failed", exc_info=True)
            return None
        return text.strip() or None
