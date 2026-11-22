from flask import flash, make_response, render_template

from app.client import ALLOWED_FORM_EXTENSIONS
from app.renderer import build_form_view_model
from app.routes.results import get_settings, load_stored_result, redirect_home


def index():
    settings = get_settings()
    return render_template(
        "index.html",
        settings=settings,
        stored=load_stored_result(),
        allowed_extensions=ALLOWED_FORM_EXTENSIONS,
    )


def preview_form():
    result = load_stored_result()
    if result is None:
        flash("Brak wczytanego JSON-a formularza. Prześlij plik lub wgraj gotowy JSON.", "error")
        return redirect_home()
    return render_template("form_preview.html", result=result, form=build_form_view_model(result.form_data))


def view_json():
    result = load_stored_result()
    if result is None:
        flash("Brak JSON-a do wyświetlenia.", "error")
        return redirect_home()
    return render_template("json_preview.html", result=result)


def download_json():
    result = load_stored_result()
    if result is None:
        flash("Brak pliku JSON do pobrania.", "error")
        return redirect_home()

    base_name = result.source_name.rsplit(".", 1)[0] if "." in result.source_name else result.source_name
    safe_base = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in base_name).strip("_") or "formularz"
    response = make_response(result.raw_json_text)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{safe_base}.form.json"'
    return response
