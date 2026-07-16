"""Middlewares: rate limit (Redis), резолв пользователя + сессия БД, язык."""

from typing import Any, Awaitable, Callable

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.i18n import t
from app.db.repositories import UserRepo

log = structlog.get_logger()


class RateLimitMiddleware(BaseMiddleware):
    """Скользящее окно в минуту на пользователя — защита от слива токенов."""

    def __init__(self, redis: Redis, limit_per_minute: int) -> None:
        self.redis = redis
        self.limit = limit_per_minute

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        key = f"rl:{user.id}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)
        if count > self.limit:
            log.info("rate_limited", telegram_id=user.id)
            if count == self.limit + 1:  # предупреждаем один раз за окно
                if isinstance(event, Message):
                    await event.answer(t("rate_limited"))
                else:
                    await event.answer(t("rate_limited"), show_alert=True)
            return None
        return await handler(event, data)


class UserSessionMiddleware(BaseMiddleware):
    """Открывает сессию БД, резолвит/создаёт пользователя, кладёт в data, коммитит."""

    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self.sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        async with self.sessionmaker() as session:
            user = await UserRepo(session).get_or_create(tg_user.id)
            data["session"] = session
            data["user"] = user
            data["lang"] = user.language
            result = await handler(event, data)
            await session.commit()
            return result
