"""Расчёт персональных дедлайнов. Чистые функции от дат.

Сроки — заглушки уровня MVP по открытым источникам.
# TODO: выверить с юристом каждый срок (регистрация по гражданствам,
# правила оплаты патента авансом, число месяцев действия патента).
"""

from datetime import date, timedelta

from app.domain.models import (
    Citizenship,
    DeadlineKind,
    EAEU_CITIZENSHIPS,
    PersonalDeadline,
    UserFacts,
)

# Срок постановки на миграционный учёт со дня въезда, календарные дни.
# TODO: выверить с юристом (рабочие vs календарные дни, актуальные соглашения)
REGISTRATION_DAYS: dict[Citizenship, int] = {
    Citizenship.TJ: 15,
    Citizenship.UZ: 15,
    Citizenship.KG: 30,  # ЕАЭС
    Citizenship.OTHER: 7,
}

PATENT_APPLICATION_DAYS = 30  # со дня въезда
PATENT_MONTHS = 12  # патент действует до 12 месяцев при оплате


def add_months(base: date, months: int) -> date:
    """base + months с обрезкой по концу месяца (31 янв + 1 мес = 28/29 фев)."""
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    last_day = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(base.day, last_day))


def registration_deadline(entry_date: date, citizenship: Citizenship) -> PersonalDeadline:
    days = REGISTRATION_DAYS.get(citizenship, REGISTRATION_DAYS[Citizenship.OTHER])
    return PersonalDeadline(
        kind=DeadlineKind.REGISTRATION,
        due_date=entry_date + timedelta(days=days),
        description_key="deadline.registration",
    )


def patent_application_deadline(entry_date: date) -> PersonalDeadline:
    return PersonalDeadline(
        kind=DeadlineKind.PATENT_APPLICATION,
        due_date=entry_date + timedelta(days=PATENT_APPLICATION_DAYS),
        description_key="deadline.patent_application",
    )


def patent_payment_schedule(patent_date: date, months: int = PATENT_MONTHS) -> list[PersonalDeadline]:
    """Ежемесячные авансовые платежи: оплатить ДО начала очередного месяца действия.

    Платёж за месяц N (N=1..months-1) должен пройти до patent_date + N месяцев.
    """
    return [
        PersonalDeadline(
            kind=DeadlineKind.PATENT_PAYMENT,
            due_date=add_months(patent_date, n),
            description_key="deadline.patent_payment",
        )
        for n in range(1, months)
    ]


# Просроченные дедлайны показываем только для одноразовых критичных сроков
# (пропущенный учёт/патент — важно знать). Прошедшие ежемесячные платежи не сыплем.
_OVERDUE_DISPLAY_KINDS = frozenset({DeadlineKind.REGISTRATION, DeadlineKind.PATENT_APPLICATION})


def compute_deadlines(
    facts: UserFacts, today: date, include_overdue: bool = False
) -> list[PersonalDeadline]:
    """Актуальные дедлайны по фактам, отсортированные по дате.

    include_overdue=True дополнительно оставляет просроченные критичные сроки
    (учёт, подача на патент) с пометкой overdue — для предупреждения в роадмапе.
    Планировщик напоминаний использует режим по умолчанию (только будущее).
    """
    deadlines: list[PersonalDeadline] = []
    is_eaeu = facts.citizenship in EAEU_CITIZENSHIPS

    if facts.entry_date and facts.citizenship and not facts.migration_registered:
        deadlines.append(registration_deadline(facts.entry_date, facts.citizenship))

    needs_patent = (
        not is_eaeu
        and facts.migration_registered
        and not facts.has_patent
        and not facts.has_rvp
        and not facts.has_vnj
    )
    if facts.entry_date and needs_patent:
        deadlines.append(patent_application_deadline(facts.entry_date))

    if facts.has_patent and facts.patent_date and not is_eaeu:
        deadlines.extend(patent_payment_schedule(facts.patent_date))

    result: list[PersonalDeadline] = []
    for d in deadlines:
        d.overdue = d.due_date < today
        if not d.overdue:
            result.append(d)
        elif include_overdue and d.kind in _OVERDUE_DISPLAY_KINDS:
            result.append(d)
    result.sort(key=lambda d: d.due_date)
    return result
