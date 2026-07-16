from datetime import date, datetime, timezone
from typing import Any, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Deadline, DialogState, KBChunk, Payment, User, UserProfile


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, telegram_id: int, language: str = "ru") -> User:
        user = await self.session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            user = User(telegram_id=telegram_id, language=language)
            self.session.add(user)
            await self.session.flush()
        return user

    async def activate_subscription(self, user: User, expires_at: datetime) -> None:
        user.subscription_status = "active"
        user.subscription_expires_at = expires_at
        await self.session.flush()

    async def delete_all_data(self, user: User) -> None:
        """Право на удаление (152-ФЗ): каскадно стирает профиль, диалог,
        дедлайны и платежи вместе с самим пользователем."""
        await self.session.delete(user)
        await self.session.flush()


class ProfileRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> UserProfile | None:
        return await self.session.get(UserProfile, user_id)

    async def upsert(self, user_id: int, **fields: Any) -> UserProfile:
        profile = await self.session.get(UserProfile, user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.session.add(profile)
        for key, value in fields.items():
            setattr(profile, key, value)
        await self.session.flush()
        return profile


class DialogStateRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_facts(self, user_id: int) -> dict[str, Any]:
        state = await self.session.get(DialogState, user_id)
        return dict(state.collected_facts) if state else {}

    async def save_facts(self, user_id: int, facts: dict[str, Any]) -> None:
        state = await self.session.get(DialogState, user_id)
        if state is None:
            state = DialogState(user_id=user_id, collected_facts=facts)
            self.session.add(state)
        else:
            state.collected_facts = facts
        await self.session.flush()


class DeadlineRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_user(self, user_id: int, deadlines: Sequence[tuple[str, date]]) -> None:
        """Пересоздаёт pending-дедлайны пользователя после обновления фактов."""
        await self.session.execute(
            delete(Deadline).where(Deadline.user_id == user_id, Deadline.status == "pending")
        )
        for kind, due in deadlines:
            self.session.add(Deadline(user_id=user_id, kind=kind, due_date=due))
        await self.session.flush()

    async def due_in_window(self, target_date: date, notified_flag: str) -> Sequence[Deadline]:
        flag_column = getattr(Deadline, notified_flag)
        result = await self.session.scalars(
            select(Deadline).where(
                Deadline.due_date == target_date,
                Deadline.status == "pending",
                flag_column.is_(False),
            )
        )
        return result.all()

    async def mark_notified(self, deadline_ids: Sequence[int], *flags: str) -> None:
        if not deadline_ids:
            return
        values = {flag: True for flag in flags}
        await self.session.execute(update(Deadline).where(Deadline.id.in_(deadline_ids)).values(**values))
        await self.session.flush()


class KBRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self, embedding: list[float], stage: str | None, citizenship: str | None, limit: int = 4
    ) -> Sequence[KBChunk]:
        query = select(KBChunk)
        if stage:
            query = query.where(KBChunk.stage == stage)
        if citizenship:
            query = query.where(KBChunk.applies_to.contains([citizenship]))
        query = query.order_by(KBChunk.embedding.cosine_distance(embedding)).limit(limit)
        result = await self.session.scalars(query)
        return result.all()


class PaymentRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, user_id: int, charge_id: str, stars_amount: int, period: str) -> Payment:
        payment = Payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id,
            stars_amount=stars_amount,
            period=period,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
