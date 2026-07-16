"""Кнопочный сбор фактов (intake). Кнопки минуют LLM полностью.

Порядок вопросов диктует domain: missing_facts() + patent_date при has_patent.
"""

from datetime import date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.planner import Planner
from app.bot.i18n import t
from app.bot.keyboards import age_kb, citizenship_kb, confirm_kb, goal_kb, grounds_kb, status_kb
from app.bot.rendering import render_result
from app.config import Settings
from app.db.models import User
from app.db.repositories import DeadlineRepo, DialogStateRepo, ProfileRepo, utcnow
from app.domain.classifier import classify, missing_facts
from app.domain.corridors import applicable_corridors, suggestions
from app.domain.deadlines import compute_deadlines
from app.domain.models import UserFacts
from app.payments.gating import features_for

router = Router(name="intake")


class IntakeStates(StatesGroup):
    entry_date = State()
    patent_date = State()


def _facts_from(data: dict) -> UserFacts:
    return UserFacts.model_validate(data.get("facts", {}))


async def _save_facts(state: FSMContext, facts: UserFacts) -> None:
    await state.update_data(facts=facts.model_dump(mode="json"))


def _status_level(facts: UserFacts) -> str:
    if facts.has_vnj:
        return "vnj"
    if facts.has_rvp:
        return "rvp"
    if facts.has_patent:
        return "patent"
    if facts.migration_registered:
        return "registered"
    return "none"


def _summary(facts: UserFacts, lang: str) -> str:
    rows = [
        (t("fact.citizenship", lang), t(f"btn.citizenship.{facts.citizenship.value}", lang)),
        (t("fact.entry_date", lang), facts.entry_date.strftime("%d.%m.%Y") if facts.entry_date else "—"),
        (t("fact.status", lang), t(f"btn.status.{_status_level(facts)}", lang)),
    ]
    if facts.patent_date:
        rows.append((t("fact.patent_date", lang), facts.patent_date.strftime("%d.%m.%Y")))
    if facts.goal:
        rows.append((t("fact.goal", lang), t(f"btn.goal.{facts.goal.value}", lang)))
    if facts.age_bracket:
        rows.append((t("fact.age", lang), t(f"btn.age.{facts.age_bracket.value}", lang)))
    if facts.grounds:
        picked = [g.value for g in facts.grounds if g.value != "none"]
        names = ", ".join(t(f"btn.ground.{v}", lang) for v in picked) if picked else t("val.grounds_none", lang)
        rows.append((t("fact.grounds", lang), names))
    return "\n".join(f"{name}: {value}" for name, value in rows)


async def ask_next(target: Message, state: FSMContext, lang: str) -> None:
    """Задаёт следующий вопрос по недостающим фактам или показывает подтверждение."""
    facts = _facts_from(await state.get_data())
    missing = missing_facts(facts)

    if missing:
        field = missing[0]
        if field == "citizenship":
            await target.answer(t("q.citizenship", lang), reply_markup=citizenship_kb(lang))
        elif field == "entry_date":
            await state.set_state(IntakeStates.entry_date)
            await target.answer(t("q.entry_date", lang))
        elif field == "goal":
            await target.answer(t("q.goal", lang), reply_markup=goal_kb(lang))
        else:  # статус (учёт/патент/РВП/ВНЖ) — один вопрос вместо четырёх «да/нет»
            await target.answer(t("q.status", lang), reply_markup=status_kb(lang))
        return

    if facts.has_patent and facts.patent_date is None:
        await state.set_state(IntakeStates.patent_date)
        await target.answer(t("q.patent_date", lang))
        return

    # Доп. факты для персонального плана и подсказок (не влияют на определение этапа).
    if facts.age_bracket is None:
        await target.answer(t("q.age", lang), reply_markup=age_kb(lang))
        return
    if not facts.grounds:  # пусто = ещё не спрашивали; после ответа минимум [none]
        await target.answer(t("q.grounds", lang), reply_markup=grounds_kb(set(), lang))
        return

    await state.set_state(None)
    await target.answer(t("intake.confirm", lang, summary=_summary(facts, lang)), reply_markup=confirm_kb(lang))


@router.callback_query(F.data == "intake:start")
async def intake_start(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    await _save_facts(state, UserFacts())
    await callback.answer()
    await ask_next(callback.message, state, lang)


@router.callback_query(F.data.startswith("cz:"))
async def intake_citizenship(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    facts = _facts_from(await state.get_data())
    facts = facts.model_copy(update={"citizenship": callback.data.split(":", 1)[1]})
    await _save_facts(state, UserFacts.model_validate(facts.model_dump()))
    await callback.answer()
    await ask_next(callback.message, state, lang)


def parse_ru_date(text: str) -> date | None:
    for fmt in ("%d.%m.%Y", "%d,%m,%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


@router.message(IntakeStates.entry_date, F.text)
async def intake_entry_date(message: Message, state: FSMContext, lang: str) -> None:
    parsed = parse_ru_date(message.text or "")
    if parsed is None:
        await message.answer(t("date.invalid", lang))
        return
    if parsed > date.today():
        await message.answer(t("date.future", lang))
        return
    facts = _facts_from(await state.get_data()).model_copy(update={"entry_date": parsed})
    await state.set_state(None)
    await _save_facts(state, facts)
    await ask_next(message, state, lang)


@router.message(IntakeStates.patent_date, F.text)
async def intake_patent_date(message: Message, state: FSMContext, lang: str) -> None:
    parsed = parse_ru_date(message.text or "")
    if parsed is None:
        await message.answer(t("date.invalid", lang))
        return
    facts = _facts_from(await state.get_data()).model_copy(update={"patent_date": parsed})
    await state.set_state(None)
    await _save_facts(state, facts)
    await ask_next(message, state, lang)


# Один ответ о статусе задаёт все четыре булевых факта разом (лестница статусов).
_STATUS_FACTS: dict[str, dict[str, bool]] = {
    "none": dict(migration_registered=False, has_patent=False, has_rvp=False, has_vnj=False),
    "registered": dict(migration_registered=True, has_patent=False, has_rvp=False, has_vnj=False),
    "patent": dict(migration_registered=True, has_patent=True, has_rvp=False, has_vnj=False),
    "rvp": dict(migration_registered=True, has_patent=False, has_rvp=True, has_vnj=False),
    "vnj": dict(migration_registered=True, has_patent=False, has_rvp=False, has_vnj=True),
}


@router.callback_query(F.data.startswith("st:"))
async def intake_status(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    updates = _STATUS_FACTS.get(callback.data.split(":", 1)[1])
    if updates is None:
        await callback.answer()
        return
    facts = _facts_from(await state.get_data()).model_copy(update=updates)
    await _save_facts(state, facts)
    await callback.answer()
    await ask_next(callback.message, state, lang)


@router.callback_query(F.data.startswith("goal:"))
async def intake_goal(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    facts = _facts_from(await state.get_data())
    facts = UserFacts.model_validate(
        facts.model_dump() | {"goal": callback.data.split(":", 1)[1]}
    )
    await _save_facts(state, facts)
    await callback.answer()
    await ask_next(callback.message, state, lang)


@router.callback_query(F.data.startswith("age:"))
async def intake_age(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    facts = _facts_from(await state.get_data())
    facts = UserFacts.model_validate(facts.model_dump() | {"age_bracket": callback.data.split(":", 1)[1]})
    await _save_facts(state, facts)
    await callback.answer()
    await ask_next(callback.message, state, lang)


def _selected_grounds(facts: UserFacts) -> set[str]:
    selected = {g.value for g in facts.grounds}
    selected.discard("none")
    return selected


@router.callback_query(F.data.startswith("gr:toggle:"))
async def intake_ground_toggle(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    value = callback.data.split(":", 2)[2]
    facts = _facts_from(await state.get_data())
    selected = _selected_grounds(facts)
    selected.discard(value) if value in selected else selected.add(value)
    facts = UserFacts.model_validate(facts.model_dump() | {"grounds": sorted(selected)})
    await _save_facts(state, facts)
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=grounds_kb(selected, lang))
    except Exception:
        pass  # Telegram отклоняет edit, если разметка не изменилась — не критично


@router.callback_query(F.data == "gr:done")
async def intake_grounds_done(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    facts = _facts_from(await state.get_data())
    grounds = sorted(_selected_grounds(facts)) or ["none"]
    facts = UserFacts.model_validate(facts.model_dump() | {"grounds": grounds})
    await _save_facts(state, facts)
    await callback.answer()
    await ask_next(callback.message, state, lang)


@router.callback_query(F.data == "intake:confirm")
async def intake_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    lang: str,
    settings: Settings,
    planner: Planner,
) -> None:
    facts = _facts_from(await state.get_data())
    stage_result = classify(facts)  # детерминированно
    corridors = applicable_corridors(facts)  # какие упрощёнки доступны — тоже код, не LLM
    plan_suggestions = suggestions(facts, corridors)
    today = date.today()
    # для показа — с просроченными критичными сроками; в БД (для напоминаний) — только будущие
    display_deadlines = compute_deadlines(facts, today=today, include_overdue=True)
    future_deadlines = [d for d in display_deadlines if not d.overdue]

    await ProfileRepo(session).upsert(
        user.id,
        citizenship=facts.citizenship.value if facts.citizenship else None,
        entry_date=facts.entry_date,
        migration_registered=facts.migration_registered,
        has_patent=facts.has_patent,
        patent_date=facts.patent_date,
        has_rvp=facts.has_rvp,
        has_vnj=facts.has_vnj,
        goal=facts.goal.value if facts.goal else None,
        current_stage=stage_result.current_stage.value,
    )
    await DialogStateRepo(session).save_facts(user.id, facts.model_dump(mode="json"))
    await DeadlineRepo(session).replace_for_user(
        user.id, [(d.kind.value, d.due_date) for d in future_deadlines]
    )

    features = features_for(
        user.subscription_status, user.subscription_expires_at, utcnow(), settings.payments_enabled
    )
    await state.clear()
    await callback.answer()

    # Подробный план генерируем из выверенных блоков БЗ (только для полного доступа).
    plan_text = None
    if features.full_roadmap:
        await callback.message.bot.send_chat_action(callback.message.chat.id, "typing")
        plan_text = await planner.build_plan(facts, stage_result, corridors, lang)

    await callback.message.answer(
        render_result(
            stage_result,
            display_deadlines,
            features,
            lang,
            corridors=corridors,
            suggestions=plan_suggestions,
            plan_text=plan_text,
        ),
        parse_mode="HTML",
    )
