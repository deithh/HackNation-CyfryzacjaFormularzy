import uuid

from flask import current_app, redirect, session, url_for

from app.client import FormResult
from app.config import Settings
from app.result_store import load_result, save_result

_ACTION_ENDPOINTS = {
    "preview_form": "viewer.preview_form",
    "view_json": "viewer.view_json",
    "download_json": "viewer.download_json",
}


def get_settings() -> Settings:
    return current_app.config["SETTINGS"]


def store_result(result: FormResult) -> None:
    result_id = session.get("result_id")
    if not isinstance(result_id, str) or not result_id:
        result_id = str(uuid.uuid4())
        session["result_id"] = result_id
    settings = get_settings()
    save_result(settings.result_store_dir, settings.result_store_ttl_seconds, result_id, result)
    session.pop("last_form_result", None)


def load_stored_result() -> FormResult | None:
    result_id = session.get("result_id")
    if not isinstance(result_id, str) or not result_id:
        return None
    settings = get_settings()
    return load_result(settings.result_store_dir, settings.result_store_ttl_seconds, result_id)


def store_and_redirect(result: FormResult, action: str):
    store_result(result)
    return redirect(url_for(_ACTION_ENDPOINTS.get(action, "viewer.preview_form")))


def redirect_home():
    return redirect(url_for("viewer.index"))
