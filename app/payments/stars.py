"""Оплата подписки Telegram Stars (XTR): инвойс -> pre_checkout -> successful_payment."""

from datetime import timedelta

import structlog
from aiogram import Bot
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from app.bot.i18n import t
from app.config import Settings
from app.db.models import User
from app.db.repositories import PaymentRepo, UserRepo, utcnow
from app.payments.gating import is_subscribed
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger()

SUBSCRIPTION_PAYLOAD = "subscription_1m"


async def send_subscription_invoice(bot: Bot, chat_id: int, settings: Settings, lang: str) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t("subscribe.title", lang),
        description=t("subscribe.description", lang, days=settings.subscription_period_days),
        payload=SUBSCRIPTION_PAYLOAD,
        currency="XTR",  # Telegram Stars: provider_token не нужен
        prices=[LabeledPrice(label=t("subscribe.title", lang), amount=settings.subscription_price_stars)],
    )


async def handle_pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=query.invoice_payload == SUBSCRIPTION_PAYLOAD)


async def handle_successful_payment(
    message: Message, session: AsyncSession, user: User, settings: Settings, lang: str
) -> None:
    payment = message.successful_payment
    await PaymentRepo(session).record(
        user_id=user.id,
        charge_id=payment.telegram_payment_charge_id,
        stars_amount=payment.total_amount,
        period="1m",
    )
    now = utcnow()
    # продление: от текущего конца подписки, если она ещё активна
    base = user.subscription_expires_at if is_subscribed(user.subscription_status, user.subscription_expires_at, now) else now
    expires_at = base + timedelta(days=settings.subscription_period_days)
    await UserRepo(session).activate_subscription(user, expires_at)
    log.info("subscription_activated", user_id=user.id, expires_at=expires_at.isoformat())
    await message.answer(t("subscribe.success", lang, until=expires_at.strftime("%d.%m.%Y")))
