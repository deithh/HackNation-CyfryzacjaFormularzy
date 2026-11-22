"""Plan model requests from page images and extracted text."""

from collections.abc import Iterator
from dataclasses import dataclass
from textwrap import wrap


def split_text(text: str, limit: int) -> list[str]:
    if limit < 1:
        raise ValueError("LLM_CHUNK_CHARS must be positive")
    if len(text) <= limit:
        return [text]
    return wrap(
        text, width=limit, expand_tabs=False, replace_whitespace=False, drop_whitespace=False, break_on_hyphens=False
    )


@dataclass(frozen=True)
class Chunk:
    text: str
    page_indices: range
    instruction: str = ""


def iter_chunks(
    texts: list[str],
    document_level_text: str,
    limit: int,
    max_images: int = 4,
) -> Iterator[Chunk]:
    if max_images < 1:
        raise ValueError("LLM_MAX_IMAGES_PER_REQUEST must be positive")
    full_text = "\n\n".join(part for part in [*texts, document_level_text] if part)
    if len(full_text) <= limit:
        if len(texts) <= max_images:
            yield Chunk(full_text, range(len(texts)))
            return
        for start in range(0, len(texts), max_images):
            window = range(start, min(start + max_images, len(texts)))
            instruction = (
                f"Source pages {window.start + 1}-{window.stop} of {len(texts)}. "
                "Extract fields from these pages only. Use headings from the source."
            )
            yield Chunk("\n\n".join(part for part in (texts[i] for i in window) if part), window, instruction)
        if document_level_text:
            yield Chunk(document_level_text, range(0), "Supplementary document-level form data without a page image.")
        return

    for page_index, text in enumerate(texts):
        excerpts = split_text(text, limit)
        for number, excerpt in enumerate(excerpts, 1):
            instruction = (
                f"Source page {page_index + 1} of {len(texts)}, excerpt {number} of {len(excerpts)}. "
                "Extract fields from this excerpt. Use headings from the source."
            )
            if number == 1:
                instruction += " Include fields visible only in this page image."
            yield Chunk(excerpt, range(page_index, page_index + 1), instruction)

    if document_level_text:
        for excerpt in split_text(document_level_text, limit):
            yield Chunk(excerpt, range(0), "Supplementary document-level form data without a page image.")
