"""structlog + фильтр PII.

Аудитория — уязвимая группа (152-ФЗ): свободный текст пользователя и любые
поля, похожие на персональные данные, не должны попадать ни в логи, ни в Sentry.
"""

import logging
from typing import Any

import structlog

# Ключи, значения которых никогда не логируем.
PII_KEYS = frozenset(
    {
        "text",
        "user_text",
        "message_text",
        "question",
        "answer",
        "full_name",
        "first_name",
        "last_name",
        "username",
        "phone",
        "phone_number",
        "passport",
        "document_number",
        "email",
        "collected_facts",
    }
)

REDACTED = "[redacted]"


def scrub_pii(mapping: dict[str, Any]) -> dict[str, Any]:
    """Рекурсивно заменяет значения PII-ключей на заглушку."""
    clean: dict[str, Any] = {}
    for key, value in mapping.items():
        if key.lower() in PII_KEYS:
            clean[key] = REDACTED
        elif isinstance(value, dict):
            clean[key] = scrub_pii(value)
        else:
            clean[key] = value
    return clean


def _pii_processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return scrub_pii(event_dict)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _pii_processor,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


def sentry_before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """before_send для Sentry: вычищает PII из extra/contexts/request."""
    for section in ("extra", "contexts", "request", "user"):
        if isinstance(event.get(section), dict):
            event[section] = scrub_pii(event[section])
    return event


def setup_sentry(dsn: str) -> None:
    if not dsn:
        return
    import sentry_sdk

    sentry_sdk.init(dsn=dsn, before_send=sentry_before_send, send_default_pii=False)
