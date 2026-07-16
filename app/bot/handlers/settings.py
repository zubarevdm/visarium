"""/delete_my_data — право на удаление (152-ФЗ): полное стирание профиля."""

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.bot.keyboards import delete_confirm_kb
from app.db.models import User
from app.db.repositories import UserRepo

log = structlog.get_logger()

router = Router(name="settings")


@router.message(Command("delete_my_data"))
async def cmd_delete_my_data(message: Message, lang: str) -> None:
    await message.answer(t("delete.confirm", lang), reply_markup=delete_confirm_kb(lang))


@router.callback_query(F.data == "delete:yes")
async def delete_yes(
    callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext, lang: str
) -> None:
    await state.clear()  # FSM в Redis тоже чистим
    await UserRepo(session).delete_all_data(user)
    log.info("user_data_deleted")  # без telegram_id: пользователь удалён — не логируем его
    await callback.answer()
    await callback.message.answer(t("delete.done", lang))


@router.callback_query(F.data == "delete:no")
async def delete_no(callback: CallbackQuery, lang: str) -> None:
    await callback.answer()
    await callback.message.answer(t("delete.cancelled", lang))
