"""Merge partial form specifications returned by the model."""


def get_or_add_group(groups: list[dict], title: str, children: str) -> dict:
    key = title.strip().casefold()
    for group in groups:
        if group["title"].strip().casefold() == key:
            return group

    group = {"title": title, children: []}
    groups.append(group)
    return group


def merge_specs(specs: list[dict]) -> dict:
    """Combine matching pages and sections in the order they first appear."""
    title = ""
    pages = []
    for spec in specs:
        title = title or spec["title"].strip()
        for page in spec["pages"]:
            merged_page = get_or_add_group(pages, page["title"], "sections")
            for section in page["sections"]:
                merged_section = get_or_add_group(merged_page["sections"], section["title"], "fields")
                merged_section["repeating"] = bool(merged_section.get("repeating") or section.get("repeating"))
                fields = merged_section["fields"]
                # Compare before extending so repeated fields within this section survive.
                new_fields = [field for field in section["fields"] if field not in fields]
                fields.extend(new_fields)
    return {"title": title, "pages": pages}
