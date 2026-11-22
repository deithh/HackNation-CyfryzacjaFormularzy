import xml.etree.ElementTree as ET

import httpx
from fastapi import HTTPException

from app.config import config

# Tika wraps each page in a <div class="page"> directly under <body>.
# The namespace wildcard matches both namespaced and plain XHTML tags.
TIKA_PAGE_SELECTOR = "./{*}div[@class='page']"


async def tika_text(content: bytes) -> tuple[list[str], str]:
    try:
        async with httpx.AsyncClient(timeout=config.tika_timeout_seconds) as client:
            result = await client.put(
                f"{config.extractor_url}/tika",
                content=content,
                headers={"Accept": "text/xml", "Content-Type": "application/octet-stream"},
            )
            result.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Text extraction timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Text could not be extracted.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="The text extractor is unavailable.") from exc
    try:
        # XML forbids the null character even as a numeric reference (&#0;).
        xhtml = result.content.replace(b"&#0;", b"")
        body = ET.fromstring(xhtml).find("{*}body")
    except ET.ParseError as exc:
        raise HTTPException(502, "Tika returned invalid XHTML.") from exc
    if body is None:
        raise HTTPException(502, "Tika returned XHTML without a document body.")

    pages = []
    for page in body.findall(TIKA_PAGE_SELECTOR):
        pages.append("".join(page.itertext()).strip())

        tail = page.tail
        page.clear()
        page.tail = tail
    return pages, "".join(body.itertext()).strip()
