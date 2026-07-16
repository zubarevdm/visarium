"""Детерминированные guardrails: инъекции и злоупотребления отсекаются до LLM.

Офтоп по смыслу дополнительно закрыт двумя слоями: RAG вернёт пустоту
(шаблонный отказ без LLM), а системный промпт compose_response запрещает
посторонние темы.
"""

import re
from dataclasses import dataclass

MAX_MESSAGE_LEN = 2000

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts)",
    r"disregard\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s*prompt",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(?!a\s+lawyer)",  # «act as ...» — смена роли
    r"jailbreak",
    r"игнорируй\s+(все\s+)?(предыдущие|прошлые)\s+(инструкции|правила)",
    r"забудь\s+(все\s+)?(инструкции|правила|ограничения)",
    r"системный\s+промпт",
    r"теперь\s+ты\s+",
    r"представь,?\s+что\s+ты\s+(не\s+)?(бот|ассистент|модель)",
    r"выведи\s+(свои\s+)?(инструкции|промпт)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


@dataclass(frozen=True)
class GuardrailVerdict:
    allowed: bool
    reason: str | None = None  # ключ i18n отказа


def check_message(text: str) -> GuardrailVerdict:
    if not text or not text.strip():
        return GuardrailVerdict(False, "guardrail.empty")
    if len(text) > MAX_MESSAGE_LEN:
        return GuardrailVerdict(False, "guardrail.too_long")
    if _INJECTION_RE.search(text):
        return GuardrailVerdict(False, "guardrail.injection")
    return GuardrailVerdict(True)
