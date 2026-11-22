from flask import flash, request

from app.client import FormApiError, parse_form_json_bytes, send_form_to_form_api
from app.routes.results import get_settings, redirect_home, store_and_redirect


def upload_form():
    settings = get_settings()
    uploaded = request.files.get("form_file")
    if uploaded is None:
        flash("Nie wybrano pliku formularza do przesłania.", "error")
        return redirect_home()

    try:
        result = send_form_to_form_api(
            form_api_url=settings.form_api_url,
            filename=uploaded.filename or "",
            content=uploaded.read(),
            timeout_seconds=settings.request_timeout_seconds,
            max_size_bytes=settings.max_upload_size_bytes,
            client_secret=settings.jwt_client_secret,
        )
    except FormApiError as exc:
        flash(str(exc), "error")
        return redirect_home()
    return store_and_redirect(result, request.form.get("action", "preview_form"))


def upload_json():
    uploaded = request.files.get("json_file")
    pasted = request.form.get("json_text", "").strip()

    raw_bytes: bytes | None = None
    source_name = "wklejony_formularz.json"
    if uploaded is not None and (uploaded.filename or "").strip():
        source_name = uploaded.filename.strip()
        raw_bytes = uploaded.read()
    elif pasted:
        raw_bytes = pasted.encode("utf-8")

    if not raw_bytes:
        flash("Wybierz plik .json lub wklej strukturę JSON formularza.", "error")
        return redirect_home()

    try:
        result = parse_form_json_bytes(raw_bytes, source_name=source_name)
    except FormApiError as exc:
        flash(str(exc), "error")
        return redirect_home()
    return store_and_redirect(result, request.form.get("action", "preview_form"))
