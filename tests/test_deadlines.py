from datetime import date

import pytest

from app.domain.deadlines import (
    add_months,
    compute_deadlines,
    patent_application_deadline,
    patent_payment_schedule,
    registration_deadline,
)
from app.domain.models import Citizenship, DeadlineKind, Goal, UserFacts


@pytest.mark.parametrize(
    "citizenship,days",
    [
        (Citizenship.TJ, 15),
        (Citizenship.UZ, 15),
        (Citizenship.KG, 30),
        (Citizenship.OTHER, 7),
    ],
)
def test_registration_deadline_per_citizenship(citizenship, days):
    entry = date(2026, 6, 1)
    deadline = registration_deadline(entry, citizenship)
    assert deadline.kind == DeadlineKind.REGISTRATION
    assert (deadline.due_date - entry).days == days


def test_patent_application_30_days():
    deadline = patent_application_deadline(date(2026, 6, 1))
    assert deadline.due_date == date(2026, 7, 1)


@pytest.mark.parametrize(
    "base,months,expected",
    [
        (date(2026, 1, 15), 1, date(2026, 2, 15)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),  # обрезка по концу месяца
        (date(2024, 1, 31), 1, date(2024, 2, 29)),  # високосный год
        (date(2026, 11, 30), 3, date(2027, 2, 28)),  # переход через год
        (date(2026, 12, 31), 12, date(2027, 12, 31)),
    ],
)
def test_add_months_edges(base, months, expected):
    assert add_months(base, months) == expected


def test_patent_payment_schedule():
    schedule = patent_payment_schedule(date(2026, 1, 31), months=12)
    assert len(schedule) == 11  # платежи за 2-й..12-й месяцы
    assert schedule[0].due_date == date(2026, 2, 28)
    assert schedule[-1].due_date == date(2026, 12, 31)
    assert all(d.kind == DeadlineKind.PATENT_PAYMENT for d in schedule)


def test_compute_deadlines_not_registered():
    facts = UserFacts(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 6, 1),
        migration_registered=False,
        goal=Goal.WORK,
    )
    deadlines = compute_deadlines(facts, today=date(2026, 6, 2))
    kinds = {d.kind for d in deadlines}
    assert DeadlineKind.REGISTRATION in kinds
    assert DeadlineKind.PATENT_APPLICATION not in kinds  # патент — после учёта


def test_compute_deadlines_registered_needs_patent():
    facts = UserFacts(
        citizenship=Citizenship.UZ,
        entry_date=date(2026, 6, 1),
        migration_registered=True,
        has_patent=False,
        has_rvp=False,
        has_vnj=False,
        goal=Goal.WORK,
    )
    deadlines = compute_deadlines(facts, today=date(2026, 6, 10))
    kinds = {d.kind for d in deadlines}
    assert kinds == {DeadlineKind.PATENT_APPLICATION}


def test_compute_deadlines_eaeu_no_patent_deadlines():
    facts = UserFacts(
        citizenship=Citizenship.KG,
        entry_date=date(2026, 6, 1),
        migration_registered=True,
        has_rvp=False,
        has_vnj=False,
        goal=Goal.WORK,
    )
    assert compute_deadlines(facts, today=date(2026, 6, 10)) == []


def test_compute_deadlines_patent_payments():
    facts = UserFacts(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 1, 10),
        migration_registered=True,
        has_patent=True,
        patent_date=date(2026, 2, 1),
        has_rvp=False,
        has_vnj=False,
        goal=Goal.WORK,
    )
    deadlines = compute_deadlines(facts, today=date(2026, 6, 15))
    assert all(d.kind == DeadlineKind.PATENT_PAYMENT for d in deadlines)
    # прошедшие платежи отфильтрованы
    assert all(d.due_date >= date(2026, 6, 15) for d in deadlines)
    assert deadlines[0].due_date == date(2026, 7, 1)


def test_compute_deadlines_past_filtered():
    facts = UserFacts(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 1, 1),
        migration_registered=False,
        goal=Goal.WORK,
    )
    # дедлайн регистрации (16 янв) давно прошёл — по умолчанию не показываем
    assert compute_deadlines(facts, today=date(2026, 6, 1)) == []


def test_overdue_registration_shown_when_included():
    """include_overdue=True показывает просроченный учёт с пометкой overdue."""
    facts = UserFacts(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 1, 1),
        migration_registered=False,
        goal=Goal.WORK,
    )
    result = compute_deadlines(facts, today=date(2026, 6, 1), include_overdue=True)
    assert len(result) == 1
    assert result[0].kind == DeadlineKind.REGISTRATION
    assert result[0].overdue is True


def test_overdue_patent_payments_not_shown_even_when_included():
    """Прошедшие ежемесячные платежи не сыплем даже с include_overdue."""
    facts = UserFacts(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 1, 10),
        migration_registered=True,
        has_patent=True,
        patent_date=date(2026, 2, 1),
        has_rvp=False,
        has_vnj=False,
        goal=Goal.WORK,
    )
    result = compute_deadlines(facts, today=date(2026, 6, 15), include_overdue=True)
    assert all(not d.overdue for d in result)
    assert all(d.kind == DeadlineKind.PATENT_PAYMENT for d in result)


def test_vnj_holder_has_no_patent_deadlines():
    facts = UserFacts(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 5, 1),
        migration_registered=True,
        has_patent=False,
        has_rvp=False,
        has_vnj=True,
        goal=Goal.CITIZENSHIP,
    )
    assert compute_deadlines(facts, today=date(2026, 5, 10)) == []
