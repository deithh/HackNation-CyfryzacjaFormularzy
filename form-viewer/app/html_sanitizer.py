import re
from html.parser import HTMLParser
from urllib.parse import urlparse

_ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "span",
    "ul", "ol", "li", "a", "div",
}
_STRIP_CONTENT_TAGS = {"script", "style", "head", "meta", "link", "title"}
_WRAPPER_TAGS = {"html", "body"}


class _FragmentSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in _STRIP_CONTENT_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0 or t in _WRAPPER_TAGS:
            return
        if t not in _ALLOWED_TAGS:
            return

        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if t == "a":
            href = attr_map.get("href", "").strip()
            parsed = urlparse(href)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                safe_href = href.replace('"', "&quot;")
                self._parts.append(
                    f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">'
                )
            else:
                self._parts.append("<span>")
            return

        if t == "br":
            self._parts.append("<br>")
            return

        self._parts.append(f"<{t}>")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in _STRIP_CONTENT_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0 or t in _WRAPPER_TAGS or t == "br":
            return
        if t in _ALLOWED_TAGS:
            self._parts.append(f"</{t}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        escaped = (
            data.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        self._parts.append(escaped)

    def get_html(self) -> str:
        raw = "".join(self._parts)
        # Usuń puste tagi <p></p> lub <span></span> powstałe po wycięciu obrazków/stylów
        raw = re.sub(r"<(p|span|div)>\s*</\1>", "", raw)
        return re.sub(r"\s{2,}", " ", raw).strip()


def sanitize_rich_text(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""

    if "<" not in text and ">" not in text:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

    parser = _FragmentSanitizer()
    parser.feed(text)
    parser.close()
    cleaned = parser.get_html()
    if cleaned:
        return cleaned

    fallback = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", fallback).strip()
