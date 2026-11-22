"""COI technical names, deterministic IDs, and label matching."""

import re
import unicodedata
import uuid

NAMESPACE = uuid.UUID("6f1c2a3e-0000-4000-8000-00000000c01d")
_POLISH = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.translate(_POLISH))
    text = text.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "pole"


def normalize_label(text: str) -> str:
    return " ".join(text.strip().rstrip(":").casefold().split())


class TechnicalNames:
    def __init__(self) -> None:
        self.used: set[str] = set()

    def allocate(self, title: str, fallback: str = "pole") -> str:
        base = (slug(title) if title else fallback)[:60]
        name, n = base, 2
        while name in self.used:
            name, n = f"{base}_{n}", n + 1
        self.used.add(name)
        return name


def uid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))
