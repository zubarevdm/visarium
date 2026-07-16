"""Freemium-гейтинг: чистые функции, тестируются без БД и Telegram."""

from dataclasses import dataclass
from datetime import datetime


def is_subscribed(subscription_status: str, expires_at: datetime | None, now: datetime) -> bool:
    return subscription_status == "active" and expires_at is not None and expires_at > now


@dataclass(frozen=True)
class FeatureSet:
    full_roadmap: bool  # полная роадмапа + чек-листы документов
    reminders: bool  # персональные напоминания 7/3/1
    unlimited_qa: bool  # вопросы по своей ситуации


FREE = FeatureSet(full_roadmap=False, reminders=False, unlimited_qa=False)
PAID = FeatureSet(full_roadmap=True, reminders=True, unlimited_qa=True)


def features_for(
    subscription_status: str,
    expires_at: datetime | None,
    now: datetime,
    payments_enabled: bool = True,
) -> FeatureSet:
    # Платежи выключены (PAYMENTS_ENABLED=false) — все функции бесплатны для всех.
    if not payments_enabled:
        return PAID
    return PAID if is_subscribed(subscription_status, expires_at, now) else FREE
