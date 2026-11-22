import io

import pypdfium2 as pdfium
from fastapi import HTTPException

from app.config import config


def count_pages(pdf: bytes) -> int:
    try:
        return len(pdfium.PdfDocument(pdf))
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The document could not be read.") from exc


def render_pages(pdf: bytes) -> list[tuple[str, bytes]]:
    try:
        document = pdfium.PdfDocument(pdf)
        pages = []
        for page in document:
            buffer = io.BytesIO()
            page.render(scale=config.page_render_scale).to_pil().convert("RGB").save(buffer, format="PNG")
            pages.append(("image/png", buffer.getvalue()))
        return pages
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The document could not be rendered.") from exc
