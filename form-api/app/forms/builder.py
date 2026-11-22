"""Build a COI form definition from the model's page and field descriptions."""

from itertools import groupby, pairwise

from .conditions import Location, VisibilityConditions
from .dictionaries import SELECT_DICTIONARIES
from .names import TechnicalNames, normalize_label, slug, uid
from .schema import FIELD_TYPES, VALIDATORS, DefinitionFieldKind

GRID_COLS = 3
OPTION_TYPES = {"CHECKBOX", "RADIO", "SELECT"}
TEXT_AND_CONSENT_TYPES = {"TEXT_BLOCK", "CONSENT_SECTION"}


def make_field(
    field_id: str, kind: DefinitionFieldKind, name: str, title: str, description: str, order: int, grid: list
) -> dict:
    return {
        "id": field_id,
        "type": kind,
        "techName": name,
        "title": title,
        "description": description,
        "options": [],
        "validation": [],
        "readOnly": False,
        "states": [],
        "questionOrder": order,
        "tooltipMessage": "",
        "repeatingSectionGrid": grid,
    }


def place_field(field: dict, row: int = 0, rows: int = 1) -> dict:
    return {"x": 0, "y": row, "rows": rows, "cols": GRID_COLS, "field": field}


def _can_group_section(section: dict) -> bool:
    fields = section.get("fields", [])
    return len(fields) == 1 and not section.get("repeating") and fields[0].get("type") != "CONSENT_SECTION"


def _group_sections(page: dict, warnings: list[str]) -> list[dict]:
    sections = []
    for can_group, group in groupby(page.get("sections", []), key=_can_group_section):
        run = list(group)
        if not can_group or len(run) == 1:
            sections.extend(run)
            continue
        sections.append(
            {
                "title": page.get("title") or "Dane",
                "repeating": False,
                "fields": [section["fields"][0] for section in run],
            }
        )
        warnings.append(f"merged {len(run)} single-field sections on page {page.get('title')}")
    return sections


FINISH_TITLE = "Strona końcowa"


def _unique_page_titles(pages: list[dict], warnings: list[str]) -> list[str]:
    titles, seen = [], {normalize_label(FINISH_TITLE)}
    for index, page in enumerate(pages):
        base = (page.get("title") or "").strip() or f"Strona {index + 1}"
        title, n = base, 2
        while normalize_label(title) in seen:
            title, n = f"{base} ({n})", n + 1
        if title != base:
            warnings.append(f"duplicate page title renamed: {base} -> {title}")
        seen.add(normalize_label(title))
        titles.append(title)
    return titles


def _duplicate_key(raw: dict) -> tuple | None:
    title = normalize_label(raw.get("title") or "")
    if not title or (raw.get("show_when_field") or "").strip():
        return None
    options = tuple(normalize_label(option) for option in raw.get("options", []) if option.strip())
    return raw.get("type"), title, options


class _FormBuilder:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.names = TechnicalNames()
        self.conditions = VisibilityConditions()

    def build_main_tab(self, sections: list[dict], title: str, page_index: int) -> dict | None:
        tab_id = uid("tab", str(page_index), title)
        questions = []
        next_row = 0
        for index, section in enumerate(sections):
            section_title = (section.get("title") or "").strip() or f"Sekcja {index + 1}"
            field = self.build_section(section, section_title, tab_id, title, len(questions))
            if field is not None:
                rows = len(field["repeatingSectionGrid"]) + 1
                questions.append(place_field(field, next_row, rows))
                next_row += rows
        if not questions:
            self.warnings.append(f"page without fields dropped: {title}")
            return None
        return {"id": tab_id, "title": title, "type": "MAIN", "questions": questions}

    def build_section(
        self,
        section: dict,
        title: str,
        tab_id: str,
        page_title: str,
        order: int,
    ) -> dict | None:
        if not section.get("fields"):
            self.warnings.append(f"empty section dropped: {title}")
            return None

        tech = self.names.allocate(title)
        repeating = bool(section.get("repeating"))
        grid = []
        seen = set()
        for index, raw in enumerate(section["fields"]):
            key = _duplicate_key(raw)
            if key is not None and key in seen:
                self.warnings.append(f"duplicate field dropped: {raw.get('type')} / {raw.get('title')!r} in {title}")
                continue
            if key is not None:
                seen.add(key)
            field = self.build_field(raw, tab_id, tech, index)
            if field is None:
                continue
            place = Location(
                page_title,
                title,
                tech,
                field["techName"],
                repeating,
                tuple(option["name"] for option in field["options"]),
            )
            self.conditions.register(field, raw, place)
            grid.append(place_field(field, len(grid)))
        if not grid:
            self.warnings.append(f"section without valid fields dropped: {title}")
            return None
        kind = "REPEATING_SECTION" if repeating else "SECTION"
        return make_field(uid("section", tab_id, tech), kind, tech, title, "", order, grid)

    def build_field(self, raw: dict, tab_id: str, section_tech: str, order: int) -> dict | None:
        kind = raw.get("type")
        title = (raw.get("title") or "").strip().rstrip(":").strip()
        if kind not in FIELD_TYPES or (not title and kind not in TEXT_AND_CONSENT_TYPES):
            self.warnings.append(f"invalid field dropped: {kind} / {title!r}")
            return None

        tech = self.names.allocate(title, kind.lower())
        field = make_field(
            uid("field", tab_id, section_tech, tech),
            kind,
            tech,
            title,
            (raw.get("description") or "").strip(),
            order,
            [],
        )
        if kind in OPTION_TYPES:
            self.set_choices(field, raw)
        if kind == "CONSENT_SECTION":
            field["consentSectionConfig"] = self.build_consents(field, raw)
        if raw.get("required") and kind not in TEXT_AND_CONSENT_TYPES:
            field["validation"].append("REQUIRED")
        for validator in raw.get("validators", []):
            if validator in VALIDATORS and validator not in field["validation"]:
                field["validation"].append(validator)
        return field

    def set_choices(self, field: dict, raw: dict) -> None:
        names = [option.strip() for option in raw.get("options", []) if option.strip()]
        if not names:
            dictionary = SELECT_DICTIONARIES.get(normalize_label(field["title"]))
            if field["type"] == "SELECT" and dictionary:
                field["dictionaryName"] = dictionary
                return
            if field["type"] == "CHECKBOX":
                names = [field["title"]]
            else:
                self.warnings.append(f"{field['type']} without options: {field['title']}")
                field["type"] = "TEXT_FIELD"
        field["options"] = [
            {"id": uid("option", field["id"], str(index)), "name": name, "techName": slug(name)[:60]}
            for index, name in enumerate(names)
        ]

    def build_consents(self, field: dict, raw: dict) -> dict:
        consents = [
            {"description": consent["description"].strip(), "required": bool(consent["required"])}
            for consent in raw.get("consents", [])
            if consent.get("description", "").strip()
        ]
        if not consents:
            self.warnings.append(f"consent section without wording: {field['title'] or field['techName']}")
        return {"consents": consents, "required": any(c["required"] for c in consents), "files": []}


def _build_finish_tab() -> dict:
    finish_id = uid("tab", "finish")
    info = make_field(
        uid("field", finish_id, "podsumowanie"),
        "INFO_SECTION",
        "podsumowanie",
        "Wniosek jest gotowy do wysłania",
        "Sprawdź wprowadzone dane i wyślij wniosek.",
        0,
        [],
    )
    summary = make_field(
        uid("section", finish_id, "podglad"),
        "SECTION",
        "podglad_uzupelnionego_wniosku",
        "Podgląd uzupełnionego wniosku",
        "",
        0,
        [place_field(info)],
    )
    return {
        "id": finish_id,
        "title": FINISH_TITLE,
        "type": "FINISH",
        "questions": [place_field(summary, rows=2)],
    }


def build_form(spec: dict) -> tuple[dict, list[str]]:
    builder = _FormBuilder()
    pages = spec.get("pages", [])
    titles = _unique_page_titles(pages, builder.warnings)
    tabs = []
    for index, (page, title) in enumerate(zip(pages, titles, strict=True)):
        tab = builder.build_main_tab(_group_sections(page, builder.warnings), title, index)
        if tab is not None:
            tabs.append(tab)

    builder.conditions.resolve(builder.warnings)
    tabs.append(_build_finish_tab())
    links = [{"id": uid("link", a["id"], b["id"]), "source": a["id"], "target": b["id"]} for a, b in pairwise(tabs)]
    title = (spec.get("title") or "").strip()[:255]
    if not title:
        builder.warnings.append("missing title")
    if len(tabs) < 2:
        builder.warnings.append("form has fewer than two tabs")
    return {"title": title, "tabs": tabs, "flow": {"links": links}}, builder.warnings
