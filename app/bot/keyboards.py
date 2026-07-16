from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.i18n import t
from app.domain.models import AgeBracket, Citizenship, Goal, Ground

# Основания, которые показываем в опросе (NONE — служебный маркер, в меню не нужен).
GROUND_OPTIONS = [g for g in Ground if g is not Ground.NONE]


def start_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("btn.start_intake", lang), callback_data="intake:start")]]
    )


def citizenship_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cz in Citizenship:
        builder.button(text=t(f"btn.citizenship.{cz.value}", lang), callback_data=f"cz:{cz.value}")
    builder.adjust(2)
    return builder.as_markup()


# Лестница статусов — один вопрос вместо четырёх «да/нет».
STATUS_LEVELS = ("none", "registered", "patent", "rvp", "vnj")


def status_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for level in STATUS_LEVELS:
        builder.button(text=t(f"btn.status.{level}", lang), callback_data=f"st:{level}")
    builder.adjust(1)
    return builder.as_markup()


def yes_no_kb(field: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn.yes", lang), callback_data=f"yn:{field}:1"),
                InlineKeyboardButton(text=t("btn.no", lang), callback_data=f"yn:{field}:0"),
            ]
        ]
    )


def goal_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for goal in Goal:
        builder.button(text=t(f"btn.goal.{goal.value}", lang), callback_data=f"goal:{goal.value}")
    builder.adjust(2)
    return builder.as_markup()


def age_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for age in AgeBracket:
        builder.button(text=t(f"btn.age.{age.value}", lang), callback_data=f"age:{age.value}")
    builder.adjust(2)
    return builder.as_markup()


def grounds_kb(selected: set[str], lang: str) -> InlineKeyboardMarkup:
    """Мультивыбор оснований: отмеченные — с галочкой; отдельная кнопка «Готово»."""
    builder = InlineKeyboardBuilder()
    for ground in GROUND_OPTIONS:
        mark = "✅ " if ground.value in selected else "▫️ "
        builder.button(
            text=mark + t(f"btn.ground.{ground.value}", lang),
            callback_data=f"gr:toggle:{ground.value}",
        )
    builder.button(text=t("btn.grounds.done", lang), callback_data="gr:done")
    builder.adjust(1)
    return builder.as_markup()


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn.confirm", lang), callback_data="intake:confirm"),
                InlineKeyboardButton(text=t("btn.restart", lang), callback_data="intake:start"),
            ]
        ]
    )


def delete_confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn.delete_yes", lang), callback_data="delete:yes"),
                InlineKeyboardButton(text=t("btn.cancel", lang), callback_data="delete:no"),
            ]
        ]
    )
