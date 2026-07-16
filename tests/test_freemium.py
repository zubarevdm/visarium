"""Freemium: гейтинг фич и содержимое ответов free vs paid."""

from datetime import date, datetime, timedelta, timezone

from app.bot.rendering import render_result
from app.domain.classifier import classify
from app.domain.models import Citizenship, DeadlineKind, Goal, PersonalDeadline, UserFacts
from app.payments.gating import FREE, PAID, features_for, is_subscribed

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def test_free_user_not_subscribed():
    assert not is_subscribed("free", None, NOW)
    assert features_for("free", None, NOW) == FREE


def test_active_subscription():
    expires = NOW + timedelta(days=10)
    assert is_subscribed("active", expires, NOW)
    assert features_for("active", expires, NOW) == PAID


def test_expired_subscription_downgrades_to_free():
    expires = NOW - timedelta(days=1)
    assert not is_subscribed("active", expires, NOW)
    assert features_for("active", expires, NOW) == FREE


def test_active_status_without_date_is_free():
    """Аномалия данных не должна дарить подписку."""
    assert features_for("active", None, NOW) == FREE


def test_payments_disabled_everyone_gets_paid():
    """PAYMENTS_ENABLED=false — все функции бесплатны, даже без подписки."""
    assert features_for("free", None, NOW, payments_enabled=False) == PAID
    assert features_for("active", None, NOW, payments_enabled=False) == PAID


def _result_and_deadlines():
    facts = UserFacts(
        citizenship=Citizenship.TJ,
        entry_date=date(2026, 6, 20),
        migration_registered=True,
        has_patent=False,
        has_rvp=False,
        has_vnj=False,
        goal=Goal.WORK,
    )
    stage_result = classify(facts)
    deadlines = [
        PersonalDeadline(
            kind=DeadlineKind.PATENT_APPLICATION,
            due_date=date(2026, 7, 20),
            description_key="deadline.patent_application",
        )
    ]
    return stage_result, deadlines


def test_free_message_is_teaser_without_details():
    stage_result, deadlines = _result_and_deadlines()
    text = render_result(stage_result, deadlines, FREE, lang="ru")
    assert "Ваш этап" in text  # этап бесплатный
    assert "Следующий шаг" in text  # краткий следующий шаг бесплатный
    assert "/subscribe" in text  # тизер подписки
    assert "20.07.2026" not in text  # даты дедлайнов скрыты
    assert "Документы для следующего шага" not in text  # чек-лист скрыт


def test_paid_message_has_full_roadmap():
    stage_result, deadlines = _result_and_deadlines()
    text = render_result(stage_result, deadlines, PAID, lang="ru")
    assert "Документы для следующего шага" in text
    assert "20.07.2026" in text
    assert "/subscribe" not in text


def test_disclaimer_always_appended_by_code():
    stage_result, deadlines = _result_and_deadlines()
    for features in (FREE, PAID):
        text = render_result(stage_result, deadlines, features, lang="ru")
        assert "не юридическая консультация" in text
