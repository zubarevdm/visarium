"""FastAPI + aiogram webhook. Всё асинхронное, секреты — только из env.

Для обкатки без домена/HTTPS есть polling-режим: python -m app.polling
"""

from contextlib import asynccontextmanager

import structlog
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from app.bootstrap import build_components
from app.config import get_settings
from app.core.logging import setup_logging, setup_sentry

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging()
    setup_sentry(settings.sentry_dsn)

    components = build_components(settings)
    components.scheduler.start()

    if settings.webhook_url:
        await components.bot.set_webhook(
            settings.webhook_url,
            secret_token=settings.webhook_secret,
            drop_pending_updates=False,
        )
        log.info("webhook_set")

    app.state.bot = components.bot
    app.state.dp = components.dp

    yield

    await components.shutdown()


app = FastAPI(title="Визарий", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="bad secret token")

    update = Update.model_validate(await request.json(), context={"bot": request.app.state.bot})
    await request.app.state.dp.feed_update(request.app.state.bot, update)
    return {"ok": True}
