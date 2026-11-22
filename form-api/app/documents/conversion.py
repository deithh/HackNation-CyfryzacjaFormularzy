import asyncio
import io

from fastapi import HTTPException
from PIL import Image

from app.config import config
from app.unoserver import UnoserverClient, UnoserverError, UnoserverTimeout, UnoserverUnavailable

IMAGE_MIMES = {"image/jpeg", "image/png"}
DEFAULT_IMAGE_DPI = 150
A4_HEIGHT_TO_WIDTH = 297 / 210


async def office_to_pdf(content: bytes) -> bytes:
    client = UnoserverClient(config.converter_url, config.converter_timeout_seconds)
    try:
        return await client.convert(content, "pdf")
    except UnoserverTimeout as exc:
        raise HTTPException(status_code=504, detail="The document converter timed out.") from exc
    except UnoserverUnavailable as exc:
        raise HTTPException(status_code=503, detail="The document converter is unavailable.") from exc
    except UnoserverError as exc:
        raise HTTPException(status_code=502, detail="The document could not be converted.") from exc


def split_page_strip(image: Image.Image) -> list[Image.Image]:
    page_height = round(image.width * A4_HEIGHT_TO_WIDTH)
    if image.height <= page_height * 1.5:
        return [image]
    tops = list(range(0, image.height, page_height))
    if len(tops) > 1 and image.height - tops[-1] < page_height // 4:
        tops.pop()
    bottoms = [*tops[1:], image.height]
    return [image.crop((0, top, image.width, bottom)) for top, bottom in zip(tops, bottoms, strict=True)]


def image_pages(content: bytes, mime: str) -> list[tuple[str, bytes]]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            slices = split_page_strip(image)
            if len(slices) == 1:
                return [(mime, content)]
            image_format = "PNG" if mime == "image/png" else "JPEG"
            pages = []
            for page in slices:
                buffer = io.BytesIO()
                page.convert("RGB").save(buffer, format=image_format)
                pages.append((mime, buffer.getvalue()))
            return pages
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The image could not be read.") from exc


def image_to_pdf(content: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as image:
            dpi = image.info.get("dpi", (DEFAULT_IMAGE_DPI,))[0] or DEFAULT_IMAGE_DPI
            first, *rest = [page.convert("RGB") for page in split_page_strip(image)]
            buffer = io.BytesIO()
            first.save(buffer, format="PDF", resolution=float(dpi), save_all=True, append_images=rest)
            return buffer.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The image could not be read.") from exc


async def to_pdf(content: bytes, mime: str) -> bytes:
    if mime == "application/pdf":
        return content
    if mime in IMAGE_MIMES:
        return await asyncio.to_thread(image_to_pdf, content)
    return await office_to_pdf(content)
