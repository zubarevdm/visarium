"""Напоминания о дедлайнах — killer-фича.

Ежедневный джоб: дедлайны в окнах 7/3/1 день до срока.
Подписчикам — персональный текст; бесплатным — один тизер с предложением подписки.
"""

from datetime import date, timedelta

import structlog
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.i18n import t
from app.db.models import User
from app.db.repositories import DeadlineRepo, utcnow
from app.payments.gating import features_for

log = structlog.get_logger()

WINDOWS = ((7, "notified_7d"), (3, "notified_3d"), (1, "notified_1d"))


async def send_due_reminders(
    bot: Bot,
    sessionmaker: async_sessionmaker,
    payments_enabled: bool = True,
    today: date | None = None,
) -> int:
    """Разослать напоминания за 7/3/1 день. Возвращает число отправленных."""
    today = today or utcnow().date()
    sent = 0
    async with sessionmaker() as session:
        deadline_repo = DeadlineRepo(session)
        for days, flag in WINDOWS:
            for deadline in await deadline_repo.due_in_window(today + timedelta(days=days), flag):
                user = await session.get(User, deadline.user_id)
                if user is None:
                    continue
                now = utcnow()
                features = features_for(
                    user.subscription_status, user.subscription_expires_at, now, payments_enabled
                )
                try:
                    if features.reminders:
                        await bot.send_message(
                            user.telegram_id,
                            t(
                                "reminder.paid",
                                user.language,
                                days=days,
                                date=deadline.due_date.strftime("%d.%m.%Y"),
                                what=t(f"deadline.{deadline.kind}", user.language),
                            ),
                        )
                        await deadline_repo.mark_notified([deadline.id], flag)
                        sent += 1
                    elif user.teaser_sent_at is None:
                        # free: единственный тизер без деталей — что именно горит, скажет подписка
                        await bot.send_message(user.telegram_id, t("reminder.teaser", user.language))
                        user.teaser_sent_at = now
                        await deadline_repo.mark_notified([deadline.id], flag)
                        sent += 1
                except Exception:
                    # заблокировал бота и т.п. — не роняем рассылку
                    log.warning("reminder_send_failed", user_id=user.id, exc_info=True)
        await session.commit()
    log.info("reminders_sent", count=sent)
    return sent


def setup_scheduler(
    bot: Bot, sessionmaker: async_sessionmaker, hour_utc: int, payments_enabled: bool = True
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        send_due_reminders,
        CronTrigger(hour=hour_utc, minute=0),
        args=[bot, sessionmaker, payments_enabled],
        id="daily_reminders",
        replace_existing=True,
    )
    return scheduler
