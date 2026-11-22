from pathlib import Path

import pytest
from fastapi import HTTPException

from app import documents
from app.config import config
from app.documents import conversion
from app.unoserver import client as unoserver_client

pytestmark = pytest.mark.integration

SAMPLES = Path(__file__).parent / "samples"
HEADING = "WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO"

DOCUMENT_EXTENSIONS = ["pdf", "doc", "docx", "ods", "xlsx"]
IMAGE_EXTENSIONS = ["jpg", "jpeg", "png"]


def sample(extension: str) -> tuple[str, bytes]:
    path = SAMPLES / f"wniosek.{extension}"
    return path.name, path.read_bytes()


def test_form_rejects_empty_file(client):
    response = client.post("/form", files={"file": ("form.pdf", b"", "application/pdf")})

    assert response.status_code == 400


def test_form_rejects_content_not_matching_extension(client):
    _, content = sample("pdf")

    response = client.post("/form", files={"file": ("form.docx", content, "application/pdf")})

    assert response.status_code == 415


def test_form_rejects_unsupported_extension(client):
    response = client.post("/form", files={"file": ("form.exe", b"MZ", "application/octet-stream")})

    assert response.status_code == 415


@pytest.mark.parametrize("extension", DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS)
async def test_sample_is_prepared_for_the_model(services, extension):
    name, content = sample(extension)
    _, mime = documents.validate_upload(name, content)

    pages, page_texts, document_level_text = await documents.prepare_form_inputs(content, mime)

    assert len(page_texts) == len(pages)
    assert HEADING in "\n".join(page_texts)
    assert isinstance(document_level_text, str)
    assert len(pages) == (1 if extension in IMAGE_EXTENSIONS else 2)
    assert all(page_mime in {"image/png", "image/jpeg"} for page_mime, _ in pages)


async def test_unreachable_converter_yields_service_unavailable(services, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(config, "converter_url", "http://127.0.0.1:1")
    monkeypatch.setattr(unoserver_client.asyncio, "sleep", no_sleep)
    name, content = sample("docx")

    with pytest.raises(HTTPException) as error:
        await conversion.office_to_pdf(content)

    assert error.value.status_code == 503
