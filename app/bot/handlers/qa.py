"""Free-text вопросы: guardrail -> LangGraph (NLU -> rule engine -> RAG -> NLG).

Дисклеймер к юридическим ответам добавляется кодом, не моделью.
"""

from datetime import date

import structlog
from aiogram import F, Router
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.config import Settings
from app.db.models import User
from app.db.repositories import DialogStateRepo, utcnow
from app.payments.gating import features_for

log = structlog.get_logger()

router = Router(name="qa")

FREE_QUESTIONS_PER_DAY = 3


async def _free_quota_exceeded(redis: Redis, user_id: int) -> bool:
    key = f"qa_quota:{user_id}:{date.today().isoformat()}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    return count > FREE_QUESTIONS_PER_DAY


@router.message(F.text & ~F.text.startswith("/"))
async def handle_question(
    message: Message,
    session: AsyncSession,
    user: User,
    lang: str,
    graph,
    redis: Redis,
    settings: Settings,
) -> None:
    features = features_for(
        user.subscription_status, user.subscription_expires_at, utcnow(), settings.payments_enabled
    )
    if not features.unlimited_qa and await _free_quota_exceeded(redis, user.id):
        await message.answer(t("qa.free_limit", lang))
        return

    dialog_repo = DialogStateRepo(session)
    known_facts = await dialog_repo.get_facts(user.id)

    result = await graph.ainvoke({"user_text": message.text, "known_facts": known_facts})

    if result.get("refusal_key"):
        await message.answer(t(result["refusal_key"], lang))
        return

    # факты, которые LLM извлёк из сообщения, сохраняем для следующих вопросов
    if result.get("facts") is not None:
        await dialog_repo.save_facts(user.id, result["facts"].model_dump(mode="json"))

    if result.get("next_question"):
        # фактов не хватает — ведём в кнопочный intake, а не гадаем
        await message.answer(t("qa.need_intake", lang))
        return

    if result.get("no_content") or not result.get("response_text"):
        await message.answer(t("qa.no_content", lang) + t("disclaimer", lang))
        return

    log.info("qa_answered", user_id=user.id, stage=result["stage_result"].current_stage.value)
    await message.answer(result["response_text"] + t("disclaimer", lang))
