"""Short-lived, filesystem-backed results shared by all Gunicorn workers."""

import json
import os
import time
from pathlib import Path

from app.client import FormApiError, FormResult, parse_form_json_bytes


def _result_path(directory: str, result_id: str) -> Path:
    if not result_id or any(char not in "0123456789abcdef-" for char in result_id.lower()):
        raise ValueError("invalid result id")
    return Path(directory) / f"{result_id}.json"


def _cleanup(directory: Path, ttl_seconds: int) -> None:
    threshold = time.time() - max(ttl_seconds, 1)
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_mtime < threshold:
                path.unlink()
        except OSError:
            continue


def save_result(directory: str, ttl_seconds: int, result_id: str, result: FormResult) -> None:
    base = Path(directory)
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    _cleanup(base, ttl_seconds)
    payload = {
        "source_name": result.source_name,
        "raw_json_text": result.raw_json_text,
        "warnings": result.warnings,
        "critical_count": result.critical_count,
        "warning_count": result.warning_count,
    }
    target = _result_path(directory, result_id)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, target)


def load_result(directory: str, ttl_seconds: int, result_id: str) -> FormResult | None:
    try:
        target = _result_path(directory, result_id)
        if not target.is_file() or target.stat().st_mtime < time.time() - max(ttl_seconds, 1):
            target.unlink(missing_ok=True)
            return None
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("raw_json_text"), str):
        return None
    try:
        return parse_form_json_bytes(
            payload["raw_json_text"].encode("utf-8"),
            source_name=str(payload.get("source_name") or "formularz.json"),
            warnings=payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
            critical_count=int(payload.get("critical_count", 0)),
            warning_count=int(payload.get("warning_count", 0)),
        )
    except (FormApiError, TypeError, ValueError):
        return None
