from typing import Literal

from pydantic import BaseModel

from app.forms.schema import VALIDATORS, FieldKind


class ConsentSpec(BaseModel):
    description: str
    required: bool


class FieldSpec(BaseModel):
    type: FieldKind
    title: str
    description: str
    required: bool
    validators: list[Literal[*VALIDATORS]]
    options: list[str]
    consents: list[ConsentSpec]
    show_when_page: str
    show_when_section: str
    show_when_field: str
    show_when_value: str


class SectionSpec(BaseModel):
    title: str
    repeating: bool
    fields: list[FieldSpec]


class PageSpec(BaseModel):
    title: str
    sections: list[SectionSpec]


class FormSpec(BaseModel):
    title: str
    pages: list[PageSpec]
