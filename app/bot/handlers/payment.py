from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.config import Settings
from app.db.models import User
from app.db.repositories import utcnow
from app.payments import stars
from app.payments.gating import is_subscribed

router = Router(name="payment")


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, user: User, settings: Settings, lang: str) -> None:
    if not settings.payments_enabled:
        await message.answer(t("subscribe.disabled", lang))
        return
    if is_subscribed(user.subscription_status, user.subscription_expires_at, utcnow()):
        await message.answer(
            t("subscribe.already", lang, until=user.subscription_expires_at.strftime("%d.%m.%Y"))
        )
        return
    await stars.send_subscription_invoice(message.bot, message.chat.id, settings, lang)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await stars.handle_pre_checkout(query)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message, session: AsyncSession, user: User, settings: Settings, lang: str
) -> None:
    await stars.handle_successful_payment(message, session, user, settings, lang)
