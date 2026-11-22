import json
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.forms.schema import validate_definition

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def fields(form: dict):
    for tab in form["tabs"]:
        for section in tab["questions"]:
            for item in section["field"]["repeatingSectionGrid"]:
                yield item["field"]


def conforming(name: str) -> dict:
    form = load(name)
    for link in form["flow"]["links"]:
        link["id"] = str(uuid.uuid4()) if len(link["id"]) != 36 else link["id"]
    for field in fields(form):
        if field["validation"] == {}:
            field["validation"] = []
        for option in field["options"]:
            option.setdefault("techName", option["name"].lower())
    return form


def failing_paths(form: dict) -> set[tuple]:
    with pytest.raises(ValueError) as error:
        validate_definition(form)
    cause = error.value.__cause__
    assert isinstance(cause, ValidationError)
    return {tuple(part for part in e["loc"] if not isinstance(part, int)) for e in cause.errors()}


GRID_FIELD = ("tabs", "questions", "field", "repeatingSectionGrid", "field")


@pytest.mark.parametrize("name", ["reference_property_number", "reference_tax_overpayment"])
def test_reference_has_blank_field_titles_and_per_item_consents(name):
    form = load(name)
    blank = [field["type"] for field in fields(form) if not field["title"]]
    assert sorted(blank) == ["CONSENT_SECTION", "TEXT_BLOCK", "TEXT_BLOCK", "TEXT_BLOCK"]
    (consent,) = (field for field in fields(form) if field["type"] == "CONSENT_SECTION")
    assert set(consent["consentSectionConfig"]) == {"consents", "files"}
    assert all(set(item) == {"description", "required"} for item in consent["consentSectionConfig"]["consents"])


def test_property_number_reference_deviates_only_by_object_validation():
    assert failing_paths(load("reference_property_number")) == {GRID_FIELD + ("validation",)}


def test_tax_reference_deviates_only_by_short_link_ids_and_missing_option_tech_name():
    assert failing_paths(load("reference_tax_overpayment")) == {
        ("flow", "links", "id"),
        GRID_FIELD + ("options", "techName"),
    }


@pytest.mark.parametrize("name", ["reference_property_number", "reference_tax_overpayment"])
def test_reference_is_valid_once_its_deviations_are_corrected(name):
    validate_definition(conforming(name))


def test_consent_without_wording_is_rejected():
    form = conforming("reference_property_number")
    (consent,) = (field for field in fields(form) if field["type"] == "CONSENT_SECTION")
    consent["consentSectionConfig"]["consents"] = []
    with pytest.raises(ValueError, match="no consent wording"):
        validate_definition(form)


@pytest.mark.parametrize("required, valid", [(True, True), (False, False)])
def test_section_requiredness_must_match_its_consents(required, valid):
    form = conforming("reference_property_number")
    (consent,) = (field for field in fields(form) if field["type"] == "CONSENT_SECTION")
    consent["consentSectionConfig"]["required"] = required
    if valid:
        validate_definition(form)
    else:
        with pytest.raises(ValueError, match="contradicts"):
            validate_definition(form)


def test_consent_configuration_outside_a_consent_section_is_rejected():
    form = conforming("reference_property_number")
    text = next(field for field in fields(form) if field["type"] == "TEXT_FIELD")
    text["consentSectionConfig"] = {"consents": [{"description": "Zgoda", "required": True}], "files": []}
    with pytest.raises(ValueError, match="Only a consent section"):
        validate_definition(form)


@pytest.mark.parametrize(
    "path, value",
    [
        (("validation",), "REQUIRED"),
        (("validation",), ["UNKNOWN"]),
        (("readOnly",), "false"),
        (("questionOrder",), "1"),
        (("tooltipMessage",), None),
        (("states",), [{"type": "HIDE", "query": "true"}]),
        (("defaultValueType",), "REGISTRY"),
    ],
)
def test_field_value_with_wrong_type_is_rejected(path, value):
    form = conforming("reference_property_number")
    field = next(fields(form))
    field[path[0]] = value
    with pytest.raises(ValueError, match="invalid structure"):
        validate_definition(form)


@pytest.mark.parametrize(
    "key", ["techName", "title", "description", "options", "validation", "readOnly", "questionOrder", "tooltipMessage"]
)
def test_field_missing_a_table_key_is_rejected(key):
    form = conforming("reference_property_number")
    del next(fields(form))[key]
    with pytest.raises(ValueError, match="invalid structure"):
        validate_definition(form)


def test_reused_field_id_is_rejected():
    form = conforming("reference_property_number")
    first, second, *_ = fields(form)
    second["id"] = first["id"]
    with pytest.raises(ValueError, match="reuses an id"):
        validate_definition(form)


def test_untitled_section_is_rejected():
    form = conforming("reference_property_number")
    form["tabs"][0]["questions"][0]["field"]["title"] = " "
    with pytest.raises(ValueError, match="section has no title"):
        validate_definition(form)
