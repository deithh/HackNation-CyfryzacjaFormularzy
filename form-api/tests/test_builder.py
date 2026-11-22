import pytest

from app.forms.builder import build_form
from app.forms.schema import FieldKind, validate_definition


def field(title, kind: FieldKind = "TEXT_FIELD", **extra):
    return {
        "type": kind,
        "title": title,
        "description": "",
        "required": True,
        "validators": [],
        "options": [],
        "consents": [],
        "show_when_page": "",
        "show_when_section": "",
        "show_when_field": "",
        "show_when_value": "",
        **extra,
    }


def shown_when(title, source, value, page="", section="", **extra):
    return field(
        title, show_when_field=source, show_when_value=value, show_when_page=page, show_when_section=section, **extra
    )


def section(title, *fields, repeating=False):
    return {"title": title, "repeating": repeating, "fields": list(fields)}


def form(*pages):
    return {"title": "Wniosek", "pages": [{"title": title, "sections": list(sections)} for title, *sections in pages]}


def find(definition, title):
    for tab in definition["tabs"]:
        for question in tab["questions"]:
            for item in question["field"]["repeatingSectionGrid"]:
                if item["field"]["title"] == title:
                    return item["field"]
    raise KeyError(title)


def sections_of(definition):
    return {q["field"]["title"]: q["field"] for tab in definition["tabs"] for q in tab["questions"]}


COUNTRY = dict(options=["Polska", "Inny kraj"])


def test_each_consent_keeps_its_own_wording_and_requiredness():
    required = "Oświadczam, że dane podane we wniosku są zgodne z prawdą."
    optional = "Wyrażam zgodę na kontakt telefoniczny  w sprawie wniosku (dobrowolne)."
    consents = [{"description": required, "required": True}, {"description": optional, "required": False}]
    definition, warnings = build_form(
        form(
            ("Dane", section("Dane", field("Imię"), field("Nazwisko"))),
            ("Zgody", section("Zgody", field("", "CONSENT_SECTION", consents=consents))),
        )
    )

    consent = sections_of(definition)["Zgody"]["repeatingSectionGrid"][0]["field"]
    assert consent["title"] == ""
    assert consent["validation"] == []
    assert consent["consentSectionConfig"] == {"consents": consents, "required": True, "files": []}
    assert warnings == []
    validate_definition(definition)


def test_consent_section_without_wording_is_not_filled_in_and_fails_validation():
    definition, warnings = build_form(
        form(
            ("Dane", section("Dane", field("Imię"), field("Nazwisko"))),
            (
                "Zgody",
                section(
                    "Zgody",
                    field("Oświadczenia", "CONSENT_SECTION", consents=[{"description": "  ", "required": True}]),
                ),
            ),
        )
    )
    consent = find(definition, "Oświadczenia")
    assert consent["consentSectionConfig"]["consents"] == []
    assert any("consent section without wording" in w for w in warnings)
    with pytest.raises(ValueError, match="no consent wording"):
        validate_definition(definition)


def test_blank_title_is_kept_for_text_blocks_but_unlabelled_inputs_are_dropped():
    definition, warnings = build_form(
        form(
            (
                "Dane",
                section(
                    "Dane",
                    field("", "TEXT_BLOCK", description="Wypełnij drukowanymi literami."),
                    field(""),
                    field("Imię"),
                ),
            ),
        )
    )
    grid = sections_of(definition)["Dane"]["repeatingSectionGrid"]
    assert [(i["field"]["type"], i["field"]["title"]) for i in grid] == [("TEXT_BLOCK", ""), ("TEXT_FIELD", "Imię")]
    assert grid[0]["field"]["techName"] == "text_block"
    assert any("invalid field dropped" in w for w in warnings)
    validate_definition(definition)


def test_duplicate_page_titles_are_made_unique_for_jsonata():
    definition, warnings = build_form(
        form(
            ("Dane", section("Wnioskodawca", field("Imię"), field("Nazwisko"))),
            ("Dane", section("Pełnomocnik", field("Imię"), field("Nazwisko"))),
            ("Strona końcowa", section("Uwagi", field("Uwagi", "TEXTAREA"), field("Data", "DATEPICKER"))),
        )
    )
    assert [tab["title"] for tab in definition["tabs"]] == ["Dane", "Dane (2)", "Strona końcowa (2)", "Strona końcowa"]
    assert sum("duplicate page title" in w for w in warnings) == 2
    validate_definition(definition)


def test_repeating_group_of_properties_becomes_repeating_section_with_its_own_path():
    definition, warnings = build_form(
        form(
            (
                "Nieruchomości",
                section(
                    "Dane nieruchomości",
                    field("Rodzaj nieruchomości", "RADIO", options=["Lokal", "Budynek"]),
                    field("Adres nieruchomości"),
                    shown_when("Numer lokalu", "Rodzaj nieruchomości", "Lokal"),
                    repeating=True,
                ),
            ),
        )
    )
    group = sections_of(definition)["Dane nieruchomości"]
    assert group["type"] == "REPEATING_SECTION"
    (state,) = find(definition, "Numer lokalu")["states"]
    assert state == {
        "type": "SHOW",
        "query": (
            '("Lokal" in tabs["Nieruchomości" in title].questions["dane_nieruchomosci" in field.techName]'
            '.field.__userAnswer[$repeatingSectionIndex]["rodzaj_nieruchomosci" in fieldTechName].answers)'
        ),
    }
    assert warnings == []
    validate_definition(definition)


def test_condition_on_a_repeating_field_from_outside_its_section_is_reported():
    definition, warnings = build_form(
        form(
            (
                "Nieruchomości",
                section(
                    "Dane nieruchomości",
                    field("Rodzaj nieruchomości", "RADIO", options=["Lokal", "Budynek"]),
                    field("Adres nieruchomości"),
                    repeating=True,
                ),
                section(
                    "Opłaty",
                    field("Kwota", "NUMBER"),
                    shown_when("Numer księgi wieczystej", "Rodzaj nieruchomości", "Lokal"),
                ),
            ),
        )
    )
    assert find(definition, "Numer księgi wieczystej")["states"] == []
    assert any("inside a repeating section" in w for w in warnings)


def two_addresses(*dependent_sections):
    return form(
        (
            "Dane",
            section(
                "Adres zamieszkania",
                field("Kraj", "SELECT", **COUNTRY),
                field("Adres"),
                shown_when("Kod pocztowy", "Kraj", "Polska"),
            ),
            section(
                "Adres do korespondencji",
                field("Kraj", "SELECT", **COUNTRY),
                field("Adres"),
                shown_when("Kod pocztowy korespondencyjny", "Kraj", "Polska"),
            ),
            *dependent_sections,
        )
    )


def source_of(state):
    return state["query"].split(".questions[", 1)[1].split("]", 1)[0], state["query"].split(
        ".repeatingSectionGrid[", 1
    )[1].split("]", 1)[0]


def test_repeated_label_resolves_to_the_field_in_the_dependent_fields_own_section():
    definition, warnings = build_form(two_addresses())
    (home,) = find(definition, "Kod pocztowy")["states"]
    (mail,) = find(definition, "Kod pocztowy korespondencyjny")["states"]
    assert source_of(home) == ('"adres_zamieszkania" in field.techName', '"kraj" in field.techName')
    assert source_of(mail) == ('"adres_do_korespondencji" in field.techName', '"kraj_2" in field.techName')
    assert warnings == []
    validate_definition(definition)


def test_page_and_section_hints_pick_the_intended_field():
    definition, warnings = build_form(
        two_addresses(
            section(
                "Doręczenie",
                field("Sposób doręczenia", "RADIO", options=["Poczta", "ePUAP"]),
                shown_when("Adres skrytki", "Adres", "x"),
                shown_when("Uwagi do doręczenia", "Kraj", "Inny kraj", page="Dane", section="Adres do korespondencji"),
            ),
        )
    )
    (state,) = find(definition, "Uwagi do doręczenia")["states"]
    assert source_of(state) == ('"adres_do_korespondencji" in field.techName', '"kraj_2" in field.techName')
    assert find(definition, "Adres skrytki")["states"] == []
    assert any("ambiguous: 'Adres'" in w for w in warnings)


def test_ambiguous_label_without_hints_is_reported_not_guessed():
    definition, warnings = build_form(
        two_addresses(
            section(
                "Doręczenie",
                field("Sposób doręczenia", "RADIO", options=["Poczta", "ePUAP"]),
                shown_when("Numer telefonu", "Kraj", "Polska"),
            ),
        )
    )
    assert find(definition, "Numer telefonu")["states"] == []
    (warning,) = [w for w in warnings if "ambiguous" in w]
    assert "Dane / Adres zamieszkania; Dane / Adres do korespondencji" in warning


def test_hint_naming_a_missing_section_is_reported():
    definition, warnings = build_form(
        two_addresses(
            section(
                "Doręczenie",
                field("Sposób doręczenia", "RADIO", options=["Poczta", "ePUAP"]),
                shown_when("Numer telefonu", "Kraj", "Polska", page="Dane", section="Adres służbowy"),
            ),
        )
    )
    assert find(definition, "Numer telefonu")["states"] == []
    assert any("not found: 'Kraj' in section 'Adres służbowy'" in w for w in warnings)


def test_value_that_is_not_an_option_of_the_source_is_reported():
    definition, warnings = build_form(
        two_addresses(
            section(
                "Doręczenie",
                field("Sposób doręczenia", "RADIO", options=["Poczta", "ePUAP"]),
                shown_when("Numer telefonu", "Kraj", "Niemcy", section="Adres zamieszkania"),
            ),
        )
    )
    assert find(definition, "Numer telefonu")["states"] == []
    assert any("'Niemcy' is not an option of 'Kraj'" in w for w in warnings)


def test_condition_value_uses_the_emitted_option_spelling():
    definition, _ = build_form(
        form(
            (
                "Dane",
                section(
                    "Wnioskodawca",
                    field("Wnioskuję jako", "RADIO", options=["Osoba fizyczna", "Firma"]),
                    shown_when("Nazwa firmy", "wnioskuję jako:", "firma"),
                ),
            ),
        )
    )
    (state,) = find(definition, "Nazwa firmy")["states"]
    assert state["query"].startswith('("Firma" in ')


def test_section_with_only_optional_consents_is_not_required():
    consents = [{"description": "Wyrażam zgodę na newsletter.", "required": False}]
    definition, _ = build_form(
        form(
            ("Dane", section("Dane", field("Imię"), field("Nazwisko"))),
            ("Zgody", section("Zgody", field("", "CONSENT_SECTION", consents=consents))),
        )
    )
    config = sections_of(definition)["Zgody"]["repeatingSectionGrid"][0]["field"]["consentSectionConfig"]
    assert config == {"consents": consents, "required": False, "files": []}
    validate_definition(definition)


def test_country_dictionary_is_resolved_from_an_unrestricted_dropdown():
    definition, warnings = build_form(
        form(
            (
                "Adres",
                section(
                    "Adres",
                    field("Kraj", "SELECT"),
                    field("Państwo pobytu", "SELECT", **COUNTRY),
                    field("Kraj urodzenia"),
                    field("Miasto", "SELECT", dictionary="Kraje"),
                ),
            )
        )
    )
    assert find(definition, "Kraj")["dictionaryName"] == "Kraje"
    assert [o["name"] for o in find(definition, "Państwo pobytu")["options"]] == COUNTRY["options"]
    for title in ("Państwo pobytu", "Kraj urodzenia", "Miasto"):
        assert "dictionaryName" not in find(definition, title)
    assert "SELECT without options: Miasto" in warnings
    assert find(definition, "Miasto")["type"] == "TEXT_FIELD"
    validate_definition(definition)


def test_radio_without_options_becomes_text_field():
    definition, warnings = build_form(form(("Dane", section("Dane", field("Imię"), field("Płeć", "RADIO")))))
    assert find(definition, "Płeć")["type"] == "TEXT_FIELD"
    assert find(definition, "Płeć")["options"] == []
    assert "RADIO without options: Płeć" in warnings
    validate_definition(definition)


def test_exact_duplicate_field_in_a_section_is_dropped():
    definition, warnings = build_form(
        form(
            (
                "Adres",
                section(
                    "Adres",
                    field("Ulica"),
                    field("Numer lokalu", required=False),
                    field("Numer lokalu:"),
                    field("Numer lokalu", "TEXTAREA"),
                    shown_when("Numer lokalu", "Ulica", "x"),
                ),
                section("Adres do korespondencji", field("Ulica"), field("Numer lokalu")),
            ),
        )
    )
    grid = sections_of(definition)["Adres"]["repeatingSectionGrid"]
    assert [(i["field"]["type"], i["field"]["title"]) for i in grid] == [
        ("TEXT_FIELD", "Ulica"),
        ("TEXT_FIELD", "Numer lokalu"),
        ("TEXTAREA", "Numer lokalu"),
        ("TEXT_FIELD", "Numer lokalu"),
    ]
    assert grid[1]["field"]["validation"] == []
    assert len(sections_of(definition)["Adres do korespondencji"]["repeatingSectionGrid"]) == 2
    assert sum("duplicate field dropped" in w for w in warnings) == 1
