"""Общая сборка компонентов приложения — для вебхука (main.py) и polling (polling.py)."""

from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.ai.graph import build_graph
from app.ai.llm import create_llm_client
from app.ai.planner import Planner
from app.ai.rag import Retriever
from app.bot.handlers import register_all
from app.bot.middlewares import RateLimitMiddleware, UserSessionMiddleware
from app.config import Settings
from app.core.embeddings import get_embedder
from app.db.session import create_engine_and_sessionmaker
from app.scheduler.reminders import setup_scheduler


class SessionKBSearcher:
    """Адаптер KBRepo к ретриверу: своя короткая сессия на каждый поиск."""

    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def search(self, embedding, stage, citizenship, limit=4):
        from app.db.repositories import KBRepo

        async with self._sessionmaker() as session:
            return await KBRepo(session).search(embedding, stage, citizenship, limit)


@dataclass
class AppComponents:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    redis: Redis
    bot: Bot
    dp: Dispatcher
    scheduler: AsyncIOScheduler

    async def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
        await self.bot.session.close()
        await self.redis.aclose()
        await self.engine.dispose()


def build_components(settings: Settings) -> AppComponents:
    engine, sessionmaker = create_engine_and_sessionmaker()
    redis = Redis.from_url(settings.redis_url)

    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=RedisStorage(redis))

    rate_limit = RateLimitMiddleware(redis, settings.rate_limit_per_minute)
    user_session = UserSessionMiddleware(sessionmaker)
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(rate_limit)
        observer.outer_middleware(user_session)
    register_all(dp)

    llm = create_llm_client(settings)
    retriever = Retriever(SessionKBSearcher(sessionmaker), get_embedder(settings))
    # зависимости, которые aiogram прокидывает в хендлеры по имени аргумента
    dp["graph"] = build_graph(llm, retriever)
    dp["planner"] = Planner(retriever, llm)
    dp["settings"] = settings
    dp["redis"] = redis

    scheduler = setup_scheduler(
        bot, sessionmaker, settings.reminder_hour_utc, settings.payments_enabled
    )
    return AppComponents(engine, sessionmaker, redis, bot, dp, scheduler)
