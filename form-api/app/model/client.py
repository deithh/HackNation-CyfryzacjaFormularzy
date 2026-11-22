"""Request a form specification from the vision model."""

import base64
from time import monotonic

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import config
from app.logging import logger
from app.model.chunks import iter_chunks
from app.model.merge import merge_specs
from app.model.prompt import build_prompt
from app.model.schema import FormSpec


async def generate_form_spec(
    pages: list[tuple[str, bytes]],
    texts: list[str],
    document_level_text: str,
) -> dict:
    images = [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"}}
        for mime, image in pages
    ]
    if len(images) != len(texts):
        raise ValueError("Each page image must have a corresponding page text.")

    specs = []
    chunks = iter_chunks(texts, document_level_text, config.llm_chunk_chars, config.llm_max_images_per_request)
    for index, chunk in enumerate(chunks, 1):
        chunk_images = [images[index] for index in chunk.page_indices]
        prompt = build_prompt(chunk.text, chunk.instruction)
        logger.debug(
            "Model chunk %d: first_page=%s images=%d text_chars=%d prompt_chars=%d",
            index,
            chunk.page_indices.start + 1 if chunk.page_indices else None,
            len(chunk_images),
            len(chunk.text),
            len(prompt),
        )
        specs.append(await request_spec(chunk_images, prompt))
    return specs[0] if len(specs) == 1 else merge_specs(specs)


async def request_spec(images: list[dict], prompt: str) -> dict:
    parts = images.copy()
    parts.append({"type": "text", "text": prompt})

    try:
        async with httpx.AsyncClient(timeout=config.llm_timeout_seconds) as client:
            payload = {
                "model": config.llm_model,
                "temperature": 0,
                "max_tokens": config.llm_max_output_tokens,
                "messages": [{"role": "user", "content": parts}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "FormSpec", "schema": FormSpec.model_json_schema()},
                },
            }
            if config.llm_disable_reasoning:
                payload["reasoning"] = {"enabled": False}
            headers = {"Authorization": f"Bearer {config.llm_api_key}"} if config.llm_api_key else {}
            model_started = monotonic()
            logger.info(
                "Sending form to model: model=%s pages=%d timeout=%.0fs",
                config.llm_model,
                len(images),
                config.llm_timeout_seconds,
            )
            response = await client.post(
                f"{config.llm_engine_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            logger.info("Model responded: status=%d elapsed=%.2fs", response.status_code, monotonic() - model_started)
            logger.debug("Model response size: bytes=%d", len(response.content))
            response.raise_for_status()
            completion = response.json()
            choice = completion["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason")
            usage = completion.get("usage") or {}
            logger.debug(
                "Model completion: finish_reason=%s completion_tokens=%s max_tokens=%d",
                finish_reason,
                usage.get("completion_tokens"),
                payload["max_tokens"],
            )
            if finish_reason == "length":
                logger.warning("Model stopped at its token limit before completing the form.")
                raise HTTPException(502, "Model reached its token limit while generating the form.")
            return FormSpec.model_validate_json(message["content"], strict=True).model_dump()
    except httpx.TimeoutException as exc:
        logger.warning("Model request timed out")
        raise HTTPException(status_code=504, detail="Form generation timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="The model server rejected the request.") from exc
    except httpx.RequestError as exc:
        logger.warning("Could not reach model server: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="The model server is unavailable or still loading.") from exc
    except ValidationError as exc:
        error = exc.errors(include_input=False, include_url=False)[0]
        location = ".".join(map(str, error["loc"])) or "root"
        logger.warning("Invalid FormSpec at %s: %s", location, error["type"])
        raise HTTPException(502, f"Invalid model FormSpec at {location}.") from exc
    except (IndexError, TypeError, ValueError, KeyError) as exc:
        logger.warning("Model returned an invalid response")
        raise HTTPException(status_code=502, detail="The model returned invalid JSON.") from exc
