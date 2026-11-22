"""Resolve field visibility after all source fields have been placed."""

import json
from dataclasses import dataclass

from .names import normalize_label


@dataclass(frozen=True)
class Location:
    page: str
    section_title: str
    section_tech: str
    field_tech: str
    repeating: bool
    options: tuple[str, ...]


def show_when_answer_contains(source: Location, value: str) -> str:
    """Write the COI SHOW rule evaluated when an applicant fills in the form.

    For example, a dependent address field can be shown when “Kraj” contains “Polska”.
    In JSONata, brackets filter a list: tabs["Dane" in title] selects the matching tab.
    """
    page_title = json.dumps(source.page, ensure_ascii=False)
    section_name = json.dumps(source.section_tech, ensure_ascii=False)
    field_name = json.dumps(source.field_tech, ensure_ascii=False)
    expected_answer = json.dumps(value, ensure_ascii=False)

    page = f"tabs[{page_title} in title]"
    section = f"{page}.questions[{section_name} in field.techName].field"
    if source.repeating:
        # Each row has its own answers. Read the source field in the current row.
        current_row = f"{section}.__userAnswer[$repeatingSectionIndex]"
        answers = f"{current_row}[{field_name} in fieldTechName].answers"
    else:
        # COI also calls the field list in an ordinary section “repeatingSectionGrid”.
        source_field = f"{section}.repeatingSectionGrid[{field_name} in field.techName].field"
        answers = f"{source_field}.__userAnswer"

    return f"({expected_answer} in {answers})"


class VisibilityConditions:
    def __init__(self) -> None:
        self.locations: dict[str, list[Location]] = {}
        self.pending: list[tuple[dict, dict, Location]] = []

    def register(self, field: dict, raw: dict, place: Location) -> None:
        if field["title"]:
            self.locations.setdefault(normalize_label(field["title"]), []).append(place)
        if raw.get("show_when_field", "").strip() and raw.get("show_when_value", "").strip():
            self.pending.append((field, raw, place))

    def find_source(self, raw: dict, target: Location) -> Location | str:
        label = raw["show_when_field"].strip()
        candidates = self.locations.get(normalize_label(label), [])
        if not candidates:
            return f"condition source not found: {label!r}"
        for hint, attribute in (
            (raw.get("show_when_page", ""), "page"),
            (raw.get("show_when_section", ""), "section_title"),
        ):
            if hint.strip():
                narrowed = [c for c in candidates if normalize_label(getattr(c, attribute)) == normalize_label(hint)]
                if not narrowed:
                    return f"condition source not found: {label!r} in {attribute.split('_')[0]} {hint!r}"
                candidates = narrowed
        if len(candidates) > 1:
            same = [c for c in candidates if (c.page, c.section_tech) == (target.page, target.section_tech)]
            if len(same) == 1:
                candidates = same
        if len(candidates) > 1:
            where = "; ".join(f"{c.page} / {c.section_title}" for c in candidates)
            return f"condition source ambiguous: {label!r} appears in {where}"
        (source,) = candidates
        if source.field_tech == target.field_tech:
            return f"condition refers to its own field: {label!r}"
        if source.repeating and (source.page, source.section_tech) != (target.page, target.section_tech):
            return f"condition source {label!r} is inside a repeating section the field is not part of"
        return source

    def resolve(self, warnings: list[str]) -> None:
        for field, raw, target in self.pending:
            source = self.find_source(raw, target)
            if isinstance(source, str):
                warnings.append(f"{source} (field {field['title'] or field['techName']!r} kept visible)")
                continue
            value = raw["show_when_value"].strip()
            if source.options:
                match = next(
                    (option for option in source.options if normalize_label(option) == normalize_label(value)), None
                )
                if match is None:
                    warnings.append(
                        f"condition value {value!r} is not an option of {raw['show_when_field'].strip()!r} "
                        f"(field {field['title'] or field['techName']!r} kept visible)"
                    )
                    continue
                value = match
            field["states"].append({"type": "SHOW", "query": show_when_answer_contains(source, value)})
