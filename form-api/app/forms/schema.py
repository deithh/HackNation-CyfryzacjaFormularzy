"""Validate a generated COI form before it is returned."""

from collections import Counter
from itertools import pairwise
from typing import Annotated, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr, ValidationError

FieldKind = Literal[
    "TEXT_FIELD",
    "TEXTAREA",
    "NUMBER",
    "CHECKBOX",
    "RADIO",
    "SELECT",
    "DATEPICKER",
    "FILE_UPLOADER",
    "CONSENT_SECTION",
    "TEXT_BLOCK",
]
DefinitionFieldKind = FieldKind | Literal["SECTION", "REPEATING_SECTION", "INFO_SECTION"]
FIELD_TYPES = frozenset(get_args(FieldKind))
SECTION_TYPES = {"SECTION", "REPEATING_SECTION"}
STATIC_TYPES = {"INFO_SECTION", "TEXT_BLOCK"}
VALIDATORS = [
    "EMAIL",
    "PESEL",
    "NIP",
    "REGON",
    "ZIP_CODE",
    "EPUAP",
    "ADE",
    "SERIAL_NUMBER_ID_CARD",
]


Name = Annotated[StrictStr, Field(min_length=1)]


class Consent(BaseModel):
    description: StrictStr
    required: StrictBool


class ConsentConfig(BaseModel):
    consents: list[Consent]
    required: StrictBool | None = None
    files: list[StrictStr] = []


class Option(BaseModel):
    id: Name
    name: StrictStr
    techName: Name


class State(BaseModel):
    type: Literal["SHOW", "READ_ONLY"]
    query: Name


class FormField(BaseModel):
    id: UUID
    type: DefinitionFieldKind
    techName: Name
    title: StrictStr
    description: StrictStr
    options: list[Option]
    validation: list[Literal["REQUIRED", *VALIDATORS]]
    dictionaryName: StrictStr | None = None
    readOnly: StrictBool
    repeatingSectionGrid: list[GridItem]
    defaultValue: StrictStr | list[StrictStr] | None = None
    defaultValueType: Literal["", "EXTERNAL_SYSTEM"] | None = None
    consentSectionConfig: ConsentConfig | None = None
    states: list[State] = []
    questionOrder: StrictInt
    tooltipMessage: StrictStr


class GridItem(BaseModel):
    x: StrictInt = Field(ge=0)
    y: StrictInt = Field(ge=0)
    rows: StrictInt = Field(gt=0)
    cols: StrictInt = Field(gt=0)
    field: FormField


class Tab(BaseModel):
    id: UUID
    type: Literal["MAIN", "FINISH"]
    title: Name
    questions: list[GridItem] = Field(min_length=1)


class Link(BaseModel):
    id: UUID
    source: UUID
    target: UUID


class Flow(BaseModel):
    links: list[Link]


class FormDefinition(BaseModel):
    title: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    tabs: list[Tab] = Field(min_length=1)
    flow: Flow


def validate_definition(form: dict) -> None:
    try:
        definition = FormDefinition.model_validate(form)
    except ValidationError as exc:
        raise ValueError("The generated form has an invalid structure.") from exc

    _validate_tabs(definition.tabs)
    _validate_fields(definition.tabs)
    _validate_unique_ids(definition)
    _validate_navigation(definition.tabs, definition.flow.links)


def _validate_unique_ids(definition: FormDefinition) -> None:
    ids = Counter(tab.id for tab in definition.tabs)
    ids.update(link.id for link in definition.flow.links)
    for tab in definition.tabs:
        for section in tab.questions:
            ids[section.field.id] += 1
            ids.update(item.field.id for item in section.field.repeatingSectionGrid)
    if any(count > 1 for count in ids.values()):
        raise ValueError("The generated form reuses an id.")


def _validate_tabs(tabs: list[Tab]) -> None:
    *main_tabs, finish = tabs
    if finish.type != "FINISH" or any(tab.type != "MAIN" for tab in main_tabs):
        raise ValueError("The generated form must end with exactly one final page.")
    titles = [tab.title.strip().casefold() for tab in tabs]
    if len(set(titles)) != len(titles):
        raise ValueError("The generated form has two pages with the same title.")


def _validate_fields(tabs: list[Tab]) -> None:
    has_input = False
    for tab in tabs:
        for section in tab.questions:
            if section.field.type not in SECTION_TYPES:
                raise ValueError("A generated field is outside a section.")
            if section.field.consentSectionConfig is not None:
                raise ValueError("Only a consent section may have a consent configuration.")
            if not section.field.title.strip():
                raise ValueError("A generated section has no title.")
            if not section.field.repeatingSectionGrid:
                raise ValueError("A generated section has no fields.")
            for item in section.field.repeatingSectionGrid:
                if _validate_field(item.field, tab.type):
                    has_input = True
    if not has_input:
        raise ValueError("The generated form contains no applicant input fields.")


def _validate_field(field: FormField, tab_type: Literal["MAIN", "FINISH"]) -> bool:
    """Check a field and return whether it collects applicant input."""
    if field.type in SECTION_TYPES:
        raise ValueError("The generated form has a nested section.")
    if field.type == "CONSENT_SECTION":
        _validate_consents(field)
    elif field.consentSectionConfig is not None:
        raise ValueError("Only a consent section may have a consent configuration.")
    if field.type == "INFO_SECTION" and not field.description.strip():
        raise ValueError("A generated information section has no description.")
    if field.type in {"SELECT", "RADIO"} and not (field.options or field.dictionaryName):
        raise ValueError("A generated choice field has no options.")
    if field.type in STATIC_TYPES:
        return False
    if tab_type == "FINISH":
        raise ValueError("The final page contains an input field.")
    return True


def _validate_consents(field: FormField) -> None:
    config = field.consentSectionConfig
    if config is None or not config.consents:
        raise ValueError("A consent section has no consent wording.")
    if any(not consent.description.strip() for consent in config.consents):
        raise ValueError("A consent has empty wording.")
    if config.required is not None and config.required != any(c.required for c in config.consents):
        raise ValueError("A consent section's requiredness contradicts its consents.")


def _validate_navigation(tabs: list[Tab], links: list[Link]) -> None:
    expected = [(source.id, target.id) for source, target in pairwise(tabs)]
    actual = [(link.source, link.target) for link in links]
    if actual != expected:
        raise ValueError("The generated form has invalid navigation links.")
