from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Citizenship(str, Enum):
    TJ = "tj"
    UZ = "uz"
    KG = "kg"
    OTHER = "other"


# Киргизия — член ЕАЭС: работа без патента, срок постановки на учёт 30 дней.
EAEU_CITIZENSHIPS = frozenset({Citizenship.KG})


class Goal(str, Enum):
    WORK = "work"
    RVP = "rvp"
    VNJ = "vnj"
    CITIZENSHIP = "citizenship"


class Stage(str, Enum):
    ENTRY = "entry"
    MIGRATION_REGISTRATION = "migration_registration"
    PATENT = "patent"
    RVP = "rvp"
    VNJ = "vnj"
    CITIZENSHIP = "citizenship"


class DeadlineKind(str, Enum):
    REGISTRATION = "registration"
    PATENT_APPLICATION = "patent_application"
    PATENT_PAYMENT = "patent_payment"


class AgeBracket(str, Enum):
    UNDER_18 = "under_18"
    A18_24 = "a18_24"
    A25_59 = "a25_59"
    A60_PLUS = "a60_plus"


class Ground(str, Enum):
    """Льготные основания — открывают упрощённые коридоры (см. domain/corridors.py).

    Военный контракт сознательно не входит в перечень: сервис его не предлагает.
    """

    SPOUSE_RF = "spouse_rf"  # супруг(а) — гражданин РФ
    FAMILY_RF = "family_rf"  # ребёнок или родитель — гражданин РФ
    RF_DIPLOMA = "rf_diploma"  # диплом вуза РФ
    NATIVE_SPEAKER = "native_speaker"  # носитель русского языка
    BORN_USSR = "born_ussr"  # родился в РСФСР / бывший гражданин СССР
    RESETTLEMENT = "resettlement"  # участник госпрограммы переселения
    NONE = "none"  # «ничего из перечисленного» (маркер, что вопрос задан)


class Corridor(str, Enum):
    """Упрощённые пути, позволяющие пропустить ступени лестницы статусов."""

    VNJ_WITHOUT_RVP = "vnj_without_rvp"  # ВНЖ без РВП
    CITIZENSHIP_WITHOUT_5Y = "citizenship_without_5y"  # гражданство без 5 лет по ВНЖ
    CITIZENSHIP_DIRECT = "citizenship_direct"  # гражданство минуя РВП и ВНЖ


class UserFacts(BaseModel):
    """Структурированные факты о ситуации пользователя.

    Никаких ФИО/номеров документов — только то, что нужно классификатору.
    Неизвестное поле = None (ещё не спрашивали или пользователь не ответил).
    """

    citizenship: Citizenship | None = Field(None, description="Гражданство: tj, uz, kg или other")
    entry_date: date | None = Field(None, description="Дата въезда в РФ")
    migration_registered: bool | None = Field(None, description="Стоит ли на миграционном учёте")
    has_patent: bool | None = Field(None, description="Есть ли действующий патент на работу")
    patent_date: date | None = Field(None, description="Дата выдачи патента")
    has_rvp: bool | None = Field(None, description="Есть ли РВП")
    has_vnj: bool | None = Field(None, description="Есть ли ВНЖ")
    goal: Goal | None = Field(None, description="Цель: work, rvp, vnj, citizenship")
    age_bracket: AgeBracket | None = Field(None, description="Возрастная группа")
    grounds: list[Ground] = Field(
        default_factory=list, description="Льготные основания (супруг РФ, диплом РФ и т.д.)"
    )

    def merged_with(self, other: "UserFacts") -> "UserFacts":
        """Новые не-None факты поверх текущих (пустой список = не задано)."""
        updates = {k: v for k, v in other.model_dump().items() if v is not None and v != []}
        return self.model_copy(update=updates)


class PersonalDeadline(BaseModel):
    kind: DeadlineKind
    due_date: date
    description_key: str  # ключ i18n
    overdue: bool = False  # срок уже прошёл (для предупреждения в роадмапе)


class StageResult(BaseModel):
    current_stage: Stage
    next_stages: list[Stage]
    required_documents: list[str]  # ключи i18n чек-листа документов следующего шага
    notes: list[str] = []  # ключи i18n примечаний (например, ЕАЭС)
