import io
from unittest.mock import AsyncMock

import pypdfium2 as pdfium
import pytest
from fastapi import HTTPException

from app.config import NO_PAGE_LIMIT, Config, config
from app.documents import pipeline


def blank_pdf(pages: int) -> bytes:
    document = pdfium.PdfDocument.new()
    for _ in range(pages):
        document.new_page(595, 842)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_default_cap_covers_the_supplied_long_forms():
    assert config.max_form_pages >= 16


async def test_oversized_pdf_is_rejected_before_ocr_and_rendering(monkeypatch):
    monkeypatch.setattr(config, "max_form_pages", 20)
    tika = AsyncMock()
    render = AsyncMock()
    monkeypatch.setattr(pipeline, "tika_text", tika)
    monkeypatch.setattr(pipeline, "render_pages", render)

    with pytest.raises(HTTPException) as error:
        await pipeline.prepare_form_inputs(blank_pdf(21), "application/pdf")

    assert error.value.status_code == 413
    assert "20 pages" in error.value.detail
    tika.assert_not_called()
    render.assert_not_called()


async def test_pdf_at_the_cap_has_every_page_prepared(monkeypatch):
    monkeypatch.setattr(config, "max_form_pages", 20)
    monkeypatch.setattr(config, "page_render_scale", 0.2)
    monkeypatch.setattr(pipeline, "tika_text", AsyncMock(return_value=([f"p{i}" for i in range(20)], "")))

    pages, texts, _ = await pipeline.prepare_form_inputs(blank_pdf(20), "application/pdf")

    assert len(pages) == len(texts) == 20


async def test_no_page_limit_prepares_a_pdf_above_the_default_cap(monkeypatch):
    monkeypatch.setattr(config, "max_form_pages", NO_PAGE_LIMIT)
    monkeypatch.setattr(config, "page_render_scale", 0.2)
    monkeypatch.setattr(pipeline, "tika_text", AsyncMock(return_value=([f"p{i}" for i in range(21)], "")))

    pages, texts, _ = await pipeline.prepare_form_inputs(blank_pdf(21), "application/pdf")

    assert len(pages) == len(texts) == 21


@pytest.mark.parametrize(("raw", "expected"), [("-1", NO_PAGE_LIMIT), ("1", 1), ("30", 30)])
def test_page_limit_setting_accepts_minus_one_and_positive_values(monkeypatch, raw, expected):
    monkeypatch.setenv("MAX_FORM_PAGES", raw)
    assert Config.from_env().max_form_pages == expected


@pytest.mark.parametrize("raw", ["0", "-2"])
def test_page_limit_setting_rejects_other_values(monkeypatch, raw):
    monkeypatch.setenv("MAX_FORM_PAGES", raw)
    with pytest.raises(ValueError, match="MAX_FORM_PAGES"):
        Config.from_env()
