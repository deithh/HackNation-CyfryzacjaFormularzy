import re
from dataclasses import dataclass, field

from app.dictionaries import get_dictionary_options
from app.html_sanitizer import sanitize_rich_text


@dataclass
class FieldViewModel:
    field_id: str
    field_type: str
    tech_name: str
    title: str
    description: str
    tooltip_message: str
    required: bool
    read_only: bool
    default_value: str
    dictionary_name: str
    validations: list[str]
    options: list[dict]
    consents: list[dict]
    consent_required: bool
    show_queries: list[str]
    show_conditions: list[dict[str, str]]
    children: list[FieldViewModel] = field(default_factory=list)
    hide_label: bool = False


@dataclass
class TabViewModel:
    tab_id: str
    title: str
    tab_type: str
    fields: list[FieldViewModel]


@dataclass
class FormViewModel:
    title: str
    tabs: list[TabViewModel]
    flow_links: list[dict]


def _grid_items(field_obj: dict) -> list[dict]:
    grid = field_obj.get("repeatingSectionGrid")
    return grid if isinstance(grid, list) else []


def _sort_key(item: dict, fallback_order: int) -> tuple[int, int, int]:
    f = item.get("field") if isinstance(item.get("field"), dict) else item
    order = f.get("questionOrder")
    return (
        int(order) if order is not None else fallback_order,
        int(item.get("y", 0) or 0),
        int(item.get("x", 0) or 0),
    )


def _plain(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value).split()).casefold()


_SHOW_QUERY = re.compile(
    r"\(\s*[\"'](?P<value>(?:\\.|[^\"'])*)[\"']\s+in\s+"
    r"tabs\[[\"'](?P<page>(?:\\.|[^\"'])*)[\"']\s+in\s+title\]"
    r"\.questions\[[\"'](?P<section>(?:\\.|[^\"'])*)[\"']\s+in\s+field\.techName\]"
    r"(?:\.field)?(?:\.repeatingSectionGrid|\.__userAnswer\[\$repeatingSectionIndex\])"
    r"\[[\"'](?P<field>(?:\\.|[^\"'])*)[\"']\s+in\s+(?:field\.)?techName\]"
    r"(?:\.field)?\.(?:__userAnswer|answers)\s*\)",
    re.IGNORECASE
)
# Fallback: jeśli struktura ścieżki się różni, wyciągamy oczekiwaną wartość oraz docelowy fieldTechName
_FALLBACK_QUERY = re.compile(
    r"[\"'](?P<value>[^\"']+)[\"']\s+in\s+.*\[[\"'](?P<field>[^\"']+)[\"']\s+in\s+(?:field\.)?techName\]",
    re.IGNORECASE
)
def _show_conditions(queries: list[str]) -> list[dict[str, str]]:
    """Parse JSONata query into sourceTechName and expected value."""
    conditions = []
    for query in queries:
        query_str = query.strip()
        match = _SHOW_QUERY.search(query_str) or _FALLBACK_QUERY.search(query_str)
        if match:
            val = match.group("value").replace(r'\"', '"').replace(r"\'", "'")
            field = match.group("field").replace(r'\"', '"').replace(r"\'", "'")
            conditions.append({"sourceTechName": field, "value": val})
    return conditions


def _build_field_vm(item: dict) -> FieldViewModel:
    f = item.get("field") if isinstance(item.get("field"), dict) else item
    validations = [str(v) for v in (f.get("validation") or [])]
    consent_cfg = f.get("consentSectionConfig") if isinstance(f.get("consentSectionConfig"), dict) else {}

    raw_consents = [c for c in (consent_cfg.get("consents") or []) if isinstance(c, dict)]
    consents: list[dict] = []
    for c in raw_consents:
        c_copy = dict(c)
        raw_desc = c.get("description") or "Zgoda"
        c_copy["description_html"] = sanitize_rich_text(str(raw_desc))
        consents.append(c_copy)

    states = [s for s in (f.get("states") or []) if isinstance(s, dict)]
    show_queries = [
        str(s.get("query", ""))
        for s in states
        if str(s.get("type", "")).upper() == "SHOW" and s.get("query")
    ]
    show_conditions = _show_conditions(show_queries)

    children = [
        _build_field_vm(child_item)
        for child_item in _grid_items(f)
        if isinstance(child_item, dict)
    ]

    dictionary_name = str(f.get("dictionaryName") or "").strip()
    field_type = str(f.get("type", "TEXT_FIELD")).upper()

    raw_title = str(f.get("title") or "")
    raw_desc = str(f.get("description") or "")
    raw_tooltip = str(f.get("tooltipMessage") or "")

    clean_options: list[dict] = []
    for o in (f.get("options") or []):
        if isinstance(o, dict):
            o_copy = dict(o)
            opt_label = str(o.get("name") or o.get("techName") or o.get("id") or "")
            o_copy["name_html"] = sanitize_rich_text(opt_label)
            clean_options.append(o_copy)

    if not clean_options and dictionary_name:
        clean_options = get_dictionary_options(dictionary_name, field_type)

    consent_required = bool(consent_cfg.get("required", False))
    hide_label = (
        field_type == "CHECKBOX"
        and len(clean_options) == 1
        and _plain(str(clean_options[0].get("name") or "")) == _plain(raw_title)
    )

    return FieldViewModel(
        field_id=str(f.get("id", "")),
        field_type=field_type,
        tech_name=str(f.get("techName", "")),
        title=sanitize_rich_text(raw_title),
        description=sanitize_rich_text(raw_desc),
        tooltip_message=sanitize_rich_text(raw_tooltip),
        required="REQUIRED" in validations or consent_required,
        read_only=bool(f.get("readOnly", False)),
        default_value=str(f.get("defaultValue") or ""),
        dictionary_name=dictionary_name,
        validations=validations,
        options=clean_options,
        consents=consents,
        consent_required=consent_required,
        show_queries=show_queries,
        show_conditions=show_conditions,
        children=children,
        hide_label=hide_label,
    )


def build_form_view_model(form_data: dict) -> FormViewModel:
    title = sanitize_rich_text(str(form_data.get("title") or "Formularz eUsługi (podgląd)")).strip()
    raw_tabs = [t for t in (form_data.get("tabs") or []) if isinstance(t, dict)]
    flow = form_data.get("flow") if isinstance(form_data.get("flow"), dict) else {}
    links = [lnk for lnk in (flow.get("links") or []) if isinstance(lnk, dict)]

    tabs_by_id = {str(t.get("id", "")): t for t in raw_tabs if t.get("id")}
    ordered_tabs: list[dict] = []
    seen_ids: set[str] = set()

    if links and tabs_by_id:
        targets = {str(lnk.get("target", "")) for lnk in links}
        sources = [str(lnk.get("source", "")) for lnk in links]
        starts = [s for s in sources if s and s not in targets and s in tabs_by_id]
        current_id = starts[0] if starts else str(raw_tabs[0].get("id", ""))
        next_map = {str(lnk.get("source", "")): str(lnk.get("target", "")) for lnk in links}

        while current_id and current_id in tabs_by_id and current_id not in seen_ids:
            ordered_tabs.append(tabs_by_id[current_id])
            seen_ids.add(current_id)
            current_id = next_map.get(current_id, "")

    for t in raw_tabs:
        tid = str(t.get("id", ""))
        if tid not in seen_ids:
            ordered_tabs.append(t)
            if tid:
                seen_ids.add(tid)

    tab_models: list[TabViewModel] = []
    for t_idx, tab in enumerate(ordered_tabs):
        questions = [q for q in (tab.get("questions") or []) if isinstance(q, dict)]
        ordered = sorted(enumerate(questions), key=lambda pair: _sort_key(pair[1], pair[0]))
        field_vms = [_build_field_vm(q) for _, q in ordered]
        tab_models.append(
            TabViewModel(
                tab_id=str(tab.get("id", f"tab-{t_idx}")),
                title=sanitize_rich_text(str(tab.get("title") or f"Strona {t_idx + 1}")),
                tab_type=str(tab.get("type") or "MAIN").upper(),
                fields=field_vms,
            )
        )

    return FormViewModel(title=title, tabs=tab_models, flow_links=links)
