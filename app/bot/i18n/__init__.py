"""i18n: вся текстовая обвязка бота — через ключи.

Добавление таджикского/узбекского = новый словарь, не рефакторинг.
"""

from app.bot.i18n import ru, tj, uz

_LOCALES: dict[str, dict[str, str]] = {"ru": ru.STRINGS, "tj": tj.STRINGS, "uz": uz.STRINGS}
DEFAULT_LANG = "ru"


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: object) -> str:
    locale = _LOCALES.get(lang, _LOCALES[DEFAULT_LANG])
    template = locale.get(key) or _LOCALES[DEFAULT_LANG].get(key) or key
    return template.format(**kwargs) if kwargs else template
