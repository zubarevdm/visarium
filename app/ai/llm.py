"""Обёртки LLM: NLU (извлечение фактов) и NLG (оформление ответа).

Два взаимозаменяемых клиента с одним интерфейсом:
- OpenAICompatibleLLMClient — Polza.AI и любой OpenAI-совместимый агрегатор (прод по умолчанию);
- AnthropicLLMClient — прямой Anthropic API.

Выбор — через LLM_PROVIDER в конфиге (см. create_llm_client).
"""

from typing import Protocol

import structlog

from app.ai.prompts import COMPOSE_RESPONSE_SYSTEM, EXTRACT_FACTS_SYSTEM
from app.ai.rag import KBBlock
from app.config import Settings
from app.domain.models import UserFacts

log = structlog.get_logger()

_RECORD_FACTS_DESCRIPTION = "Записать факты о миграционной ситуации, явно названные пользователем."


class LLMClient(Protocol):
    async def extract_facts(self, user_text: str) -> UserFacts: ...

    async def compose_response(self, question: str, blocks: list[KBBlock]) -> str: ...


def _kb_user_content(question: str, blocks: list[KBBlock]) -> str:
    kb_context = "\n\n---\n\n".join(
        f"[Блок {i + 1}, источник: {b.source_file}]\n{b.content}" for i, b in enumerate(blocks)
    )
    return (
        f"<knowledge_blocks>\n{kb_context}\n</knowledge_blocks>\n\n"
        f"<user_question>\n{question}\n</user_question>"
    )


class OpenAICompatibleLLMClient:
    """Polza.AI и другие OpenAI-совместимые API (chat/completions + function calling)."""

    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI  # ленивый импорт: не тянуть SDK при anthropic-провайдере

        self._client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        self._model = settings.llm_model

    async def extract_facts(self, user_text: str) -> UserFacts:
        """Принудительный function call + pydantic-валидация.

        При любой ошибке возвращает пустые факты — «ничего не понял» безопаснее догадки.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": EXTRACT_FACTS_SYSTEM},
                    {"role": "user", "content": user_text},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "record_facts",
                            "description": _RECORD_FACTS_DESCRIPTION,
                            "parameters": UserFacts.model_json_schema(),
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "record_facts"}},
            )
            for call in response.choices[0].message.tool_calls or []:
                if call.function.name == "record_facts":
                    return UserFacts.model_validate_json(call.function.arguments)
        except Exception:
            log.warning("extract_facts_failed", provider="openai_compatible", exc_info=True)
        return UserFacts()

    async def compose_response(self, question: str, blocks: list[KBBlock]) -> str:
        """Оформляет ответ строго из переданных блоков. Вызывать только при blocks != []."""
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": COMPOSE_RESPONSE_SYSTEM},
                {"role": "user", "content": _kb_user_content(question, blocks)},
            ],
        )
        return (response.choices[0].message.content or "").strip()


class AnthropicLLMClient:
    def __init__(self, settings: Settings) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def extract_facts(self, user_text: str) -> UserFacts:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=EXTRACT_FACTS_SYSTEM,
                tools=[
                    {
                        "name": "record_facts",
                        "description": _RECORD_FACTS_DESCRIPTION,
                        "input_schema": UserFacts.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": "record_facts"},
                messages=[{"role": "user", "content": user_text}],
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "record_facts":
                    return UserFacts.model_validate(block.input)
        except Exception:
            log.warning("extract_facts_failed", provider="anthropic", exc_info=True)
        return UserFacts()

    async def compose_response(self, question: str, blocks: list[KBBlock]) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1500,
            system=COMPOSE_RESPONSE_SYSTEM,
            messages=[{"role": "user", "content": _kb_user_content(question, blocks)}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()


def create_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicLLMClient(settings)
    return OpenAICompatibleLLMClient(settings)
