import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import config
from app.model import client as model

FIELD = {
    "type": "TEXT_FIELD",
    "title": "Telefon",
    "description": "",
    "required": True,
    "validators": [],
    "options": [],
    "consents": [],
    "show_when_page": "",
    "show_when_section": "",
    "show_when_field": "",
    "show_when_value": "",
}
EMPTY = {"title": "Wniosek", "pages": []}


def spec(field):
    return {
        "title": "Wniosek",
        "pages": [
            {"title": "Dane", "sections": [{"title": "Kontakt", "repeating": False, "fields": [field]}]},
        ],
    }


@pytest.fixture
def submit(monkeypatch):
    def run(*replies):
        prepared = ([("image/png", b"page")], ["x" * len(replies)], "")
        monkeypatch.setattr(main.documents, "prepare_form_inputs", AsyncMock(return_value=prepared))
        monkeypatch.setattr(config, "llm_chunk_chars", 1)
        responses = iter(replies)

        def respond(request):
            message = {"content": json.dumps(next(responses))}
            return httpx.Response(200, json={"choices": [{"message": message}]})

        async_client = httpx.AsyncClient
        monkeypatch.setattr(
            model.httpx, "AsyncClient", lambda **opts: async_client(transport=httpx.MockTransport(respond), **opts)
        )
        with TestClient(main.app) as api:
            return api.post("/form", files={"file": ("form.pdf", b"%PDF-1.7\n", "application/pdf")})

    return run


@pytest.mark.parametrize(
    "bad_spec",
    [
        {"title": "Wniosek", "pages": "Dane"},
        spec(dict(FIELD, required="true")),
        spec(dict(FIELD, validators=["UNKNOWN"])),
        spec({"type": "TEXT_FIELD"}),
        spec(dict(FIELD, type="CONSENT_SECTION", consents=["Oświadczam, że dane są prawdziwe."])),
        spec(dict(FIELD, type="CONSENT_SECTION", consents=[{"description": "Zgoda", "required": "yes"}])),
    ],
)
def test_invalid_chunk_rejected_before_merge(submit, bad_spec):
    response = submit(spec(FIELD), bad_spec)
    assert response.status_code == 502
    assert "FormSpec at pages" in response.json()["detail"]


def test_empty_excerpt_allowed_if_another_contains_input(submit):
    response = submit(EMPTY, spec(FIELD))
    assert response.status_code == 200
    assert [tab["type"] for tab in response.json()["tabs"]] == ["MAIN", "FINISH"]


@pytest.mark.parametrize("reply", [EMPTY, spec(dict(FIELD, type="TEXT_BLOCK"))])
def test_form_without_input_rejected(submit, reply):
    response = submit(reply)
    assert response.status_code == 502
    assert "no applicant input fields" in response.json()["detail"]


def test_choice_field_without_options_becomes_text_field(submit):
    response = submit(spec(dict(FIELD, type="RADIO")))
    assert response.status_code == 200
    field = response.json()["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]
    assert field["type"] == "TEXT_FIELD"
    assert "RADIO without options: Telefon" in json.loads(response.headers["X-Form-Warnings"])


def test_broken_navigation_rejected(submit, monkeypatch):
    build = main.form_builder.build_form

    def disconnected(spec):
        definition, warnings = build(spec)
        definition["flow"]["links"] = []
        return definition, warnings

    monkeypatch.setattr(main.form_builder, "build_form", disconnected)
    response = submit(spec(FIELD))
    assert response.status_code == 502
    assert "navigation links" in response.json()["detail"]


def test_consent_items_reach_the_form_unchanged(submit):
    consents = [
        {"description": "Oświadczam, że dane są prawdziwe.", "required": True},
        {"description": "Zgadzam się na kontakt e-mail.", "required": False},
    ]
    consent = dict(FIELD, type="CONSENT_SECTION", title="", consents=consents)
    reply = {
        "title": "Wniosek",
        "pages": [
            {
                "title": "Dane",
                "sections": [
                    {"title": "Kontakt", "repeating": False, "fields": [FIELD]},
                    {"title": "Zgody", "repeating": False, "fields": [consent]},
                ],
            }
        ],
    }
    response = submit(reply)
    assert response.status_code == 200, response.text
    zgody = response.json()["tabs"][0]["questions"][1]["field"]["repeatingSectionGrid"][0]["field"]
    assert zgody["consentSectionConfig"] == {"consents": consents, "required": True, "files": []}


def test_consent_section_without_wording_rejected(submit):
    response = submit(spec(dict(FIELD, type="CONSENT_SECTION", consents=[])))
    assert response.status_code == 502
    assert "no consent wording" in response.json()["detail"]
