"""Граф этапов легализации как данные.

Юридическое содержание (документы, условия) — заглушки уровня MVP.
# TODO: выверить с юристом каждый список документов и условий.
"""

from dataclasses import dataclass, field

from app.domain.models import DeadlineKind, Stage


@dataclass(frozen=True)
class StageDef:
    id: Stage
    title_key: str  # ключ i18n названия этапа
    next: tuple[Stage, ...]  # возможные следующие этапы
    documents: tuple[str, ...]  # ключи i18n чек-листа документов ЭТОГО этапа
    deadline_kinds: tuple[DeadlineKind, ...] = field(default=())


STAGES: dict[Stage, StageDef] = {
    Stage.ENTRY: StageDef(
        id=Stage.ENTRY,
        title_key="stage.entry",
        next=(Stage.MIGRATION_REGISTRATION,),
        documents=("doc.migration_card", "doc.passport_foreign"),
        deadline_kinds=(DeadlineKind.REGISTRATION,),
    ),
    Stage.MIGRATION_REGISTRATION: StageDef(
        id=Stage.MIGRATION_REGISTRATION,
        title_key="stage.migration_registration",
        next=(Stage.PATENT, Stage.RVP),
        # TODO: выверить с юристом: перечень для уведомления о прибытии
        documents=("doc.arrival_notice", "doc.host_confirmation"),
        deadline_kinds=(DeadlineKind.PATENT_APPLICATION,),
    ),
    Stage.PATENT: StageDef(
        id=Stage.PATENT,
        title_key="stage.patent",
        next=(Stage.RVP,),
        # TODO: выверить с юристом: полный перечень для патента
        documents=("doc.patent_application", "doc.medical_certificate", "doc.russian_exam", "doc.dms_policy"),
        deadline_kinds=(DeadlineKind.PATENT_PAYMENT,),
    ),
    Stage.RVP: StageDef(
        id=Stage.RVP,
        title_key="stage.rvp",
        next=(Stage.VNJ,),
        # TODO: выверить с юристом: перечень для РВП (квота/без квоты)
        documents=("doc.rvp_application", "doc.medical_certificate", "doc.russian_exam"),
    ),
    Stage.VNJ: StageDef(
        id=Stage.VNJ,
        title_key="stage.vnj",
        next=(Stage.CITIZENSHIP,),
        # TODO: выверить с юристом: перечень для ВНЖ
        documents=("doc.vnj_application", "doc.income_proof"),
    ),
    Stage.CITIZENSHIP: StageDef(
        id=Stage.CITIZENSHIP,
        title_key="stage.citizenship",
        next=(),
        # TODO: выверить с юристом: перечень для гражданства
        documents=("doc.citizenship_application", "doc.language_exam"),
    ),
}
