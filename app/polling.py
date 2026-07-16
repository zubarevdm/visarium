"""Обкатка без домена и HTTPS: long polling вместо вебхука.

Запуск:  uv run python -m app.polling
Нужны только Postgres, Redis, токен бота и ключ LLM. WEBHOOK_URL не требуется.
"""

import asyncio

import structlog

from app.bootstrap import build_components
from app.config import get_settings
from app.core.logging import setup_logging, setup_sentry

log = structlog.get_logger()


async def main() -> None:
    settings = get_settings()
    setup_logging()
    setup_sentry(settings.sentry_dsn)

    components = build_components(settings)
    components.scheduler.start()

    # polling и вебхук несовместимы — снимаем вебхук, если стоял
    await components.bot.delete_webhook(drop_pending_updates=False)
    log.info("polling_started")
    try:
        await components.dp.start_polling(components.bot)
    finally:
        await components.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
