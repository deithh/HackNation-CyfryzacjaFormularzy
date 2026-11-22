import base64
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.config import config
from app.model import client as model
from app.model.chunks import iter_chunks


def test_exact_limit_keeps_pages_and_notes_in_one_request():
    text = "A\n\nB\n\nC"
    (chunk,) = iter_chunks(["A", "B"], "C", limit=len(text))
    assert chunk.text == text
    assert list(chunk.page_indices) == [0, 1]


@pytest.mark.parametrize("text", ["a" * 13, "Żółć\n\n  Łódź\t ąę"])
def test_oversized_page_preserves_every_character(text):
    chunks = list(iter_chunks([text], "", limit=6))
    assert len(chunks) > 1
    assert "".join(chunk.text for chunk in chunks) == text
    assert all(len(chunk.text) <= 6 for chunk in chunks)
    assert all(list(chunk.page_indices) == [0] for chunk in chunks)


def test_blank_page_keeps_image_and_document_text_has_none():
    chunks = list(iter_chunks(["", "ABCDE"], "12345", limit=4))
    assert [(chunk.text, list(chunk.page_indices)) for chunk in chunks] == [
        ("", [0]),
        ("ABCD", [1]),
        ("E", [1]),
        ("1234", []),
        ("5", []),
    ]


def partial_spec(*titles):
    fields = [{"title": title, "type": "TEXT_FIELD"} for title in titles]
    return {
        "title": "Wniosek",
        "pages": [
            {"title": "Dane", "sections": [{"title": "Kontakt", "repeating": False, "fields": fields}]},
        ],
    }


def test_form_pairs_excerpts_with_their_page_and_builds_one_grid(monkeypatch):
    images = [("image/png", b"first"), ("image/png", b"second")]
    prepared = (images, ["ABCDEFGHI", "Tel"], "")
    monkeypatch.setattr(main.documents, "prepare_form_inputs", AsyncMock(return_value=prepared))
    monkeypatch.setattr(config, "llm_chunk_chars", 5)
    request = AsyncMock(
        side_effect=[
            partial_spec("Imię"),
            partial_spec("Imię", "Nazwisko"),
            partial_spec("Telefon"),
        ]
    )
    monkeypatch.setattr(model, "request_spec", request)

    with TestClient(main.app) as client:
        response = client.post("/form", files={"file": ("form.pdf", b"%PDF-1.7\n", "application/pdf")})
    assert response.status_code == 200, response.text
    assert request.await_count == 3
    for call, excerpt, expected_image in zip(
        request.await_args_list, ["ABCDE", "FGHI", "Tel"], [b"first", b"first", b"second"], strict=True
    ):
        supplied_images, prompt = call.args
        (image,) = supplied_images
        assert base64.b64decode(image["image_url"]["url"].split(",", 1)[1]) == expected_image
        assert prompt.endswith("Extracted text of the form:\n" + excerpt)

    form = response.json()
    data, finish = form["tabs"]
    assert (data["type"], finish["type"]) == ("MAIN", "FINISH")
    (section,) = data["questions"]
    grid = section["field"]["repeatingSectionGrid"]
    assert [(item["field"]["title"], item["x"], item["y"]) for item in grid] == [
        ("Imię", 0, 0),
        ("Nazwisko", 0, 1),
        ("Telefon", 0, 2),
    ]
    (link,) = form["flow"]["links"]
    assert (link["source"], link["target"]) == (data["id"], finish["id"])


async def test_failed_chunk_stops_processing(monkeypatch):
    monkeypatch.setattr(config, "llm_chunk_chars", 2)
    request = AsyncMock(side_effect=[partial_spec("Imię"), HTTPException(502, "Model failed")])
    monkeypatch.setattr(model, "request_spec", request)
    with pytest.raises(HTTPException) as error:
        await model.generate_form_spec([("image/png", b"page")], ["abcdef"], "")
    assert error.value.status_code == 502
    assert request.await_count == 2


@pytest.mark.parametrize("pages", [6, 16])
def test_short_text_on_many_pages_is_sent_in_windows_of_pages(pages):
    texts = [f"Strona {number}" for number in range(1, pages + 1)]
    chunks = list(iter_chunks(texts, "", limit=10_000, max_images=4))
    windows = [list(chunk.page_indices) for chunk in chunks]
    assert all(len(window) <= 4 for window in windows)
    assert [index for window in windows for index in window] == list(range(pages))
    assert "\n\n".join(chunk.text for chunk in chunks) == "\n\n".join(texts)


def test_long_text_on_many_pages_sends_one_image_per_request():
    texts = [f"Strona {number}" for number in range(1, 17)]
    chunks = list(iter_chunks(texts, "", limit=5, max_images=4))
    assert all(len(chunk.page_indices) == 1 for chunk in chunks)
    assert sorted({chunk.page_indices.start for chunk in chunks}) == list(range(16))


def test_document_level_text_gets_its_own_imageless_request_when_pages_are_windowed():
    chunks = list(iter_chunks(["a", "b", "c"], "AcroForm", limit=100, max_images=2))
    assert [(list(c.page_indices), c.text) for c in chunks] == [([0, 1], "a\n\nb"), ([2], "c"), ([], "AcroForm")]


def test_max_images_must_be_positive():
    with pytest.raises(ValueError, match="LLM_MAX_IMAGES_PER_REQUEST"):
        list(iter_chunks(["a"], "", limit=10, max_images=0))
