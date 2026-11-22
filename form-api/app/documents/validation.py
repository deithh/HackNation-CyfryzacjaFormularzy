import io
import zipfile

import magic
from fastapi import HTTPException


MAX_FILENAME_LENGTH = 250
FORBIDDEN_FILENAME_CHARS = set(";:><\\/|'*%$")

OOXML_WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
OOXML_SHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ODS = "application/vnd.oasis.opendocument.spreadsheet"

# extension -> MIME types that the file content may be detected as
ALLOWED = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword", OOXML_WORD},
    "docx": {OOXML_WORD, "application/msword"},
    "ods": {ODS},
    "xlsx": {OOXML_SHEET},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
}

# libmagic sometimes reports the container instead of the document type.
_OLE_MIMES = {
    "application/msword",
    "application/x-ole-storage",
    "application/CDFV2",
    "application/vnd.ms-office",
    "application/octet-stream",
}
_ZIP_MIMES = {"application/zip", "application/octet-stream", "application/x-zip"}


def detect_mime(content: bytes) -> str:
    mime = magic.from_buffer(content, mime=True)
    if mime in _ZIP_MIMES:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "mimetype" in names:
                    declared = archive.read("mimetype").decode("ascii", "ignore").strip()
                    if declared:
                        return declared
                if "word/document.xml" in names:
                    return OOXML_WORD
                if "xl/workbook.xml" in names:
                    return OOXML_SHEET
        except zipfile.BadZipFile:
            pass
    elif mime in _OLE_MIMES and content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "application/msword"
    return mime


def validate_filename(filename: str | None) -> str:
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="The file name is missing.")
    if len(filename) > MAX_FILENAME_LENGTH:
        raise HTTPException(status_code=400, detail=f"The file name is longer than {MAX_FILENAME_LENGTH} characters.")
    bad = sorted(set(filename) & FORBIDDEN_FILENAME_CHARS)
    if bad:
        raise HTTPException(status_code=400, detail="The file name contains forbidden characters: " + " ".join(bad))
    return filename


def validate_upload(filename: str | None, content: bytes) -> tuple[str, str]:
    """Check name, extension and that the content matches the extension.

    Returns (extension, detected MIME type)."""
    filename = validate_filename(filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: " + ", ".join(f".{e}" for e in ALLOWED),
        )
    mime = detect_mime(content)
    if mime not in ALLOWED[extension]:
        raise HTTPException(
            status_code=415,
            detail=f"The file content ({mime}) does not match the .{extension} extension.",
        )
    return extension, mime
