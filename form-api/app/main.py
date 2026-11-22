import json
from time import monotonic

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import Response

from app import documents
from app.auth import require_jwt
from app.auth import router as auth_router
from app.config import config
from app.forms import builder as form_builder
from app.forms.schema import validate_definition
from app.logging import logger
from app.model import client as model

app = FastAPI(title="Form API")
app.include_router(auth_router)


async def read_upload(file: UploadFile) -> bytes:
    documents.validate_filename(file.filename)
    try:
        content = await file.read(config.max_upload_size_bytes + 1)
    finally:
        await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > config.max_upload_size_bytes:
        raise HTTPException(status_code=413, detail="The uploaded file is too large.")
    return content


@app.post("/form", dependencies=[Depends(require_jwt)])
async def form(file: UploadFile):
    """Convert an uploaded form (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) into a FormDefinition.

    The file is validated (name, extension, content type, size), turned into a PDF, and its
    text and page images are sent to the language model.
    """
    started = monotonic()
    content = await read_upload(file)
    _, mime = documents.validate_upload(file.filename, content)
    logger.info("Form upload accepted: mime=%s bytes=%d", mime, len(content))
    try:
        # Tika can return text outside its page tags, such as PDF form-field values.
        # Keep it as document_level_text because it has no page image of its own.
        pages, texts, document_level_text = await documents.prepare_form_inputs(content, mime)
    except HTTPException as exc:
        logger.warning("Document preparation failed: %s", exc.detail)
        raise
    spec = await model.generate_form_spec(pages, texts, document_level_text)
    definition, warnings = form_builder.build_form(spec)
    logger.debug(
        "Form assembled: main_tabs=%d flow_links=%d", len(definition["tabs"]) - 1, len(definition["flow"]["links"])
    )
    try:
        validate_definition(definition)
    except ValueError as exc:
        logger.warning("Invalid generated form: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.info(
        "Form generated: tabs=%d warnings=%d elapsed=%.2fs",
        len(definition["tabs"]),
        len(warnings),
        monotonic() - started,
    )
    return Response(
        content=json.dumps(definition, ensure_ascii=False),
        media_type="application/json",
        headers={"X-Form-Warnings": json.dumps(warnings)},
    )
