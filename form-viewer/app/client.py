import json
from dataclasses import dataclass
from pathlib import Path

import httpx

ALLOWED_FORM_EXTENSIONS = (".pdf", ".doc", ".docx", ".ods", ".xlsx", ".jpg", ".jpeg", ".png")
FORBIDDEN_FILENAME_CHARS = set(';:><\\/|\'*%$')
MAX_FILENAME_LENGTH = 250


class FormApiError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class FormResult:
    source_name: str
    form_data: dict
    raw_json_text: str
    warnings: list[str]
    critical_count: int
    warning_count: int


def validate_upload_metadata(filename: str | None, size_bytes: int, max_size_bytes: int) -> str:
    if not filename or not filename.strip():
        raise FormApiError("Brak nazwy przesyłanego pliku.", status_code=400)
    clean_name = filename.strip()
    if len(clean_name) > MAX_FILENAME_LENGTH:
        raise FormApiError(
            f"Nazwa pliku przekracza limit {MAX_FILENAME_LENGTH} znaków.", status_code=400
        )
    bad_chars = sorted(set(clean_name) & FORBIDDEN_FILENAME_CHARS)
    if bad_chars:
        raise FormApiError(
            "Nazwa pliku zawiera niedozwolone znaki: " + " ".join(bad_chars), status_code=400
        )
    if size_bytes <= 0:
        raise FormApiError("Przesłany plik jest pusty.", status_code=400)
    if size_bytes > max_size_bytes:
        raise FormApiError(
            f"Przesłany plik przekracza dozwolony rozmiar ({max_size_bytes} bajtów).",
            status_code=413,
        )
    ext = Path(clean_name).suffix.lower()
    if ext not in ALLOWED_FORM_EXTENSIONS:
        raise FormApiError(
            "Nieobsługiwane rozszerzenie pliku. Dozwolone: "
            + ", ".join(sorted(ALLOWED_FORM_EXTENSIONS)),
            status_code=415,
        )
    return clean_name


def parse_form_json_bytes(
    raw_bytes: bytes,
    source_name: str,
    warnings: list[str] | None = None,
    critical_count: int = 0,
    warning_count: int = 0,
) -> FormResult:
    try:
        decoded = raw_bytes.decode("utf-8")
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FormApiError(f"Otrzymano niepoprawny plik JSON: {exc}", status_code=502) from exc

    if not isinstance(parsed, dict) or "tabs" not in parsed or not isinstance(parsed["tabs"], list):
        raise FormApiError(
            "JSON nie zawiera wymaganej struktury formularza (klucz 'tabs' jako lista).",
            status_code=422,
        )

    pretty_json = json.dumps(parsed, ensure_ascii=False, indent=2)
    return FormResult(
        source_name=source_name,
        form_data=parsed,
        raw_json_text=pretty_json,
        warnings=warnings or [],
        critical_count=critical_count,
        warning_count=warning_count,
    )


def _parse_nonnegative_int_header(raw_header: str | None, header_name: str) -> int:
    try:
        value = int(raw_header or "0")
    except ValueError as exc:
        raise FormApiError(f"Nieprawidłowa wartość nagłówka {header_name}.") from exc
    return max(value, 0)


def _fetch_access_token(client: httpx.Client, base_url: str, client_secret: str) -> str:
    response = client.post(f"{base_url}/token", headers={"Authorization": f"Bearer {client_secret}"})
    if response.status_code == 404:
        raise FormApiError("form-api nie wydaje tokenów (brak JWT_SECRET lub JWT_CLIENT_SECRET w form-api).", 502)
    if response.status_code == 401:
        raise FormApiError("form-api odrzucił JWT_CLIENT_SECRET przeglądarki formularzy.", 502)
    if response.status_code >= 400:
        raise FormApiError(f"Nie udało się pobrać tokenu z form-api (HTTP {response.status_code}).", 502)
    try:
        return str(response.json()["access_token"])
    except (ValueError, KeyError, TypeError) as exc:
        raise FormApiError("form-api zwrócił niepoprawną odpowiedź z tokenem.", 502) from exc


def send_form_to_form_api(
    form_api_url: str,
    filename: str,
    content: bytes,
    timeout_seconds: float,
    max_size_bytes: int,
    client_secret: str = "",
) -> FormResult:
    clean_name = validate_upload_metadata(filename, len(content), max_size_bytes)
    base_url = form_api_url.rstrip("/")
    endpoint = f"{base_url}/form"

    files = {"file": (clean_name, content, "application/octet-stream")}

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            headers = {}
            if client_secret:
                headers["Authorization"] = f"Bearer {_fetch_access_token(client, base_url, client_secret)}"
            response = client.post(endpoint, files=files, headers=headers)
    except httpx.TimeoutException as exc:
        raise FormApiError("Przekroczono limit czasu oczekiwania na odpowiedź form-api.", 504) from exc
    except httpx.RequestError as exc:
        raise FormApiError(f"Nie udało się połączyć z form-api ({base_url}): {exc}", 503) from exc

    if response.status_code == 401:
        raise FormApiError(
            "form-api wymaga tokenu JWT. Ustaw JWT_CLIENT_SECRET w form-viewer/.env (ta sama wartość co w form-api).",
            502,
        )
    if response.status_code >= 400:
        detail = response.text.strip() or f"Błąd HTTP {response.status_code}"
        raise FormApiError(f"form-api zwrócił błąd ({response.status_code}): {detail}", response.status_code)

    return parse_form_json_bytes(
        response.content,
        source_name=clean_name,
        critical_count=_parse_nonnegative_int_header(
            response.headers.get("X-Form-Critical-Count"), "X-Form-Critical-Count"
        ),
        warning_count=_parse_nonnegative_int_header(
            response.headers.get("X-Form-Warning-Count"), "X-Form-Warning-Count"
        ),
    )
