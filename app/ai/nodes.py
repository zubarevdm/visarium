"""Узлы LangGraph-графа. Все юридические решения — в domain, LLM только на краях."""

from typing import Any, TypedDict

from app.ai.guardrails import check_message
from app.ai.llm import LLMClient
from app.ai.rag import KBBlock, Retriever
from app.domain.classifier import classify, is_complete, missing_facts
from app.domain.models import StageResult, UserFacts


class GraphState(TypedDict, total=False):
    user_text: str
    known_facts: dict[str, Any]  # UserFacts.model_dump(mode="json") из dialog_state
    facts: UserFacts
    refusal_key: str | None  # ключ i18n отказа guardrail
    next_question: str | None  # имя недостающего факта -> кнопочный вопрос
    stage_result: StageResult | None
    blocks: list[KBBlock]
    response_text: str | None
    no_content: bool  # RAG пуст -> шаблонный честный отказ без LLM


def make_nodes(llm: LLMClient, retriever: Retriever) -> dict[str, Any]:
    async def guardrail(state: GraphState) -> GraphState:
        verdict = check_message(state.get("user_text", ""))
        return {"refusal_key": None if verdict.allowed else verdict.reason}

    async def extract_facts(state: GraphState) -> GraphState:
        """LLM-NLU только для free-text; кнопочные ответы в граф не попадают."""
        known = UserFacts.model_validate(state.get("known_facts") or {})
        extracted = await llm.extract_facts(state["user_text"])
        return {"facts": known.merged_with(extracted)}

    async def check_completeness(state: GraphState) -> GraphState:
        facts = state["facts"]
        if is_complete(facts):
            return {"next_question": None}
        return {"next_question": missing_facts(facts)[0]}

    async def ask_clarification(state: GraphState) -> GraphState:
        # Сам вопрос-кнопки формирует бот по имени факта; узел лишь фиксирует решение.
        return {"response_text": None}

    async def classify_stage(state: GraphState) -> GraphState:
        return {"stage_result": classify(state["facts"])}  # детерминированно, НЕ LLM

    async def retrieve_content(state: GraphState) -> GraphState:
        stage_result = state["stage_result"]
        facts = state["facts"]
        blocks = await retriever.retrieve(
            question=state["user_text"],
            stage=stage_result.current_stage.value if stage_result else None,
            citizenship=facts.citizenship.value if facts.citizenship else None,
        )
        return {"blocks": blocks, "no_content": not blocks}

    async def compose_response(state: GraphState) -> GraphState:
        if state.get("no_content"):
            return {"response_text": None}  # честный отказ — шаблоном в боте, без LLM
        text = await llm.compose_response(state["user_text"], state["blocks"])
        return {"response_text": text}

    return {
        "guardrail": guardrail,
        "extract_facts": extract_facts,
        "check_completeness": check_completeness,
        "ask_clarification": ask_clarification,
        "classify_stage": classify_stage,
        "retrieve_content": retrieve_content,
        "compose_response": compose_response,
    }
