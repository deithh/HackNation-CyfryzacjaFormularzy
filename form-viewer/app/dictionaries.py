"""Local dictionary registry. TERYT CSV files are loaded once per worker and never fetched at runtime."""

import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from app.html_sanitizer import sanitize_rich_text

_SUPPORTED_DICTIONARY_FIELD_TYPES = {"SELECT", "RADIO", "CHECKBOX"}
_SELECT_ONLY_DICTIONARIES = {"WOJEWODZTWO", "POWIAT", "GMINA", "MIEJSCOWOSC", "KRAJE"}
_DICTS_DIR = Path(__file__).resolve().parent / "dictionaries_data"
_TERYT_DIR = _DICTS_DIR / "teryt"
_TRANSLITERATION = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def normalize_dictionary_name(dictionary_name: str | None) -> str:
    if not dictionary_name:
        return ""
    cleaned = str(dictionary_name).translate(_TRANSLITERATION).strip()
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", cleaned).strip("_")
    return cleaned.upper()


def _option(option_id: str, name: str, tech_name: str | None = None) -> dict:
    return {"id": option_id, "name": name, "techName": tech_name or option_id,
            "name_html": sanitize_rich_text(name)}


def _latest_csv(prefix: str) -> Path | None:
    candidates = sorted(_TERYT_DIR.glob(f"{prefix}_Urzedowy_*.csv"))
    return candidates[-1] if candidates else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def _load_json_dictionaries() -> dict[str, list[dict]]:
    registry: dict[str, list[dict]] = {}
    for path in sorted(_DICTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            continue
        options: list[dict] = []
        for index, item in enumerate(data["items"]):
            if isinstance(item, str) and item.strip():
                name = item.strip()
                option_id = normalize_dictionary_name(name).lower() or f"opt_{index}"
                options.append(_option(option_id, name, option_id.upper()))
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("label") or item.get("id") or "").strip()
                if name:
                    option_id = str(item.get("id") or normalize_dictionary_name(name).lower() or f"opt_{index}")
                    options.append(_option(option_id, name, str(item.get("techName") or item.get("code") or option_id)))
        aliases = [path.stem, *(data.get("aliases") if isinstance(data.get("aliases"), list) else [])]
        for alias in aliases:
            key = normalize_dictionary_name(alias)
            if key:
                registry[key] = options
    return registry


def _load_teryt_dictionaries() -> dict[str, list[dict]]:
    terc_path, simc_path = _latest_csv("TERC"), _latest_csv("SIMC")
    if terc_path is None or simc_path is None:
        return {}
    terc = _read_csv(terc_path)
    wojewodztwa = [_option(row["WOJ"], row["NAZWA"].title(), row["WOJ"])
                    for row in terc if not row["POW"]]
    powiaty = [_option(row["WOJ"] + row["POW"], f"{row['NAZWA_DOD']} {row['NAZWA']}", row["WOJ"] + row["POW"])
                for row in terc if row["POW"] and not row["GMI"]]
    gminy: list[dict] = []
    gmina_names: dict[tuple[str, str, str], str] = {}
    for row in terc:
        if not row["GMI"]:
            continue
        code = row["WOJ"] + row["POW"] + row["GMI"] + row["RODZ"]
        label = f"{row['NAZWA']} ({row['NAZWA_DOD']})"
        gminy.append(_option(code, label, code))
        gmina_names.setdefault((row["WOJ"], row["POW"], row["GMI"]), label)
    miejscowosci = []
    for row in _read_csv(simc_path):
        unit = gmina_names.get((row["WOJ"], row["POW"], row["GMI"]), "")
        label = f"{row['NAZWA']} ({unit})" if unit else row["NAZWA"]
        miejscowosci.append(_option(row["SYM"], label, row["SYM"]))
    return {
        "WOJEWODZTWO": wojewodztwa, "WOJEWODZTWA": wojewodztwa,
        "POWIAT": powiaty, "POWIATY": powiaty,
        "GMINA": gminy, "GMINY": gminy,
        "MIEJSCOWOSC": miejscowosci, "MIEJSCOWOSCI": miejscowosci,
    }


@lru_cache(maxsize=1)
def _registry() -> dict[str, list[dict]]:
    registry = _load_json_dictionaries()
    registry.update(_load_teryt_dictionaries())
    return registry


def get_dictionary_options(dictionary_name: str | None, field_type: str | None = None) -> list[dict]:
    field_kind = (field_type or "").upper()
    key = normalize_dictionary_name(dictionary_name)
    if field_kind not in _SUPPORTED_DICTIONARY_FIELD_TYPES or not key:
        return []
    if key in _SELECT_ONLY_DICTIONARIES and field_kind != "SELECT":
        return []
    return _registry().get(key, [])
