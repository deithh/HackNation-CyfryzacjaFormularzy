import asyncio
from time import monotonic

from fastapi import HTTPException

from app.config import NO_PAGE_LIMIT, config
from app.logging import logger

from .conversion import IMAGE_MIMES, image_pages, to_pdf
from .extraction import tika_text
from .rendering import count_pages, render_pages


async def prepare_form_inputs(content: bytes, mime: str) -> tuple[list[tuple[str, bytes]], list[str], str]:
    """Return (page images, page texts, document-level text) for an already validated upload."""
    if mime != "application/pdf":
        logger.info("Converting upload to PDF")
    pdf = await to_pdf(content, mime)

    page_count = await asyncio.to_thread(count_pages, pdf)
    logger.debug("Prepared PDF: pages=%d bytes=%d", page_count, len(pdf))
    if config.max_form_pages != NO_PAGE_LIMIT and page_count > config.max_form_pages:
        logger.warning("Form exceeds page limit: pages=%d limit=%d", page_count, config.max_form_pages)
        raise HTTPException(status_code=413, detail=f"At most {config.max_form_pages} pages are supported.")

    started = monotonic()
    logger.info("Sending PDF to Tika")
    texts, document_level_text = await tika_text(pdf)
    logger.info(
        "Tika extraction finished: characters=%d elapsed=%.2fs",
        sum(map(len, texts)) + len(document_level_text),
        monotonic() - started,
    )
    if mime in IMAGE_MIMES:
        pages = image_pages(content, mime)  # keep the scan at its original quality
    else:
        started = monotonic()
        logger.info("Rendering PDF pages")
        pages = await asyncio.to_thread(render_pages, pdf)
        logger.info("PDF rendering finished: pages=%d elapsed=%.2fs", len(pages), monotonic() - started)
    if not texts and len(pages) == 1:
        texts, document_level_text = [document_level_text], ""
    if len(texts) != len(pages):
        raise HTTPException(502, "Tika page count differs from the rendered PDF.")
    return pages, texts, document_level_text
