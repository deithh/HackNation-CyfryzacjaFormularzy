import os
from dataclasses import dataclass, field


def _url(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


NO_PAGE_LIMIT = -1


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _page_limit(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value != NO_PAGE_LIMIT and value < 1:
        raise ValueError(f"{name} must be positive or {NO_PAGE_LIMIT}")
    return value


@dataclass
class Config:
    extractor_url: str
    converter_url: str
    converter_timeout_seconds: float
    tika_timeout_seconds: float
    page_render_scale: float
    max_form_pages: int
    max_upload_size_bytes: int
    llm_engine_url: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_output_tokens: int
    llm_chunk_chars: int
    llm_max_images_per_request: int
    llm_api_key: str
    llm_disable_reasoning: bool
    log_level: str | None
    jwt_secret: str = field(default="", repr=False)
    jwt_client_secret: str = field(default="", repr=False)
    jwt_issuer: str = "form-digitizer"
    jwt_audience: str = "form-api"

    @classmethod
    def from_env(cls) -> Config:
        jwt_secret = os.getenv("JWT_SECRET", "")
        if jwt_secret and len(jwt_secret.encode()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 bytes")
        jwt_client_secret = os.getenv("JWT_CLIENT_SECRET", "")
        if jwt_client_secret:
            if not jwt_secret:
                raise ValueError("JWT_CLIENT_SECRET requires JWT_SECRET")
            if len(jwt_client_secret.encode()) < 32:
                raise ValueError("JWT_CLIENT_SECRET must be at least 32 bytes")
            if jwt_client_secret == jwt_secret:
                raise ValueError("JWT_CLIENT_SECRET must differ from JWT_SECRET")
        return cls(
            extractor_url=_url("EXTRACTOR_URL", "http://tika:8081"),
            converter_url=_url("CONVERTER_URL", "http://unoserver:2003"),
            converter_timeout_seconds=float(os.getenv("CONVERTER_TIMEOUT_SECONDS", "180")),
            tika_timeout_seconds=float(os.getenv("TIKA_TIMEOUT_SECONDS", "300")),
            page_render_scale=float(os.getenv("PAGE_RENDER_SCALE", "2")),
            max_form_pages=_page_limit("MAX_FORM_PAGES", 20),
            max_upload_size_bytes=int(os.getenv("MAX_UPLOAD_SIZE_BYTES", "10485760")),
            llm_engine_url=_url("LLM_ENGINE_URL", "http://model-runner.docker.internal/engines/v1"),
            llm_model=os.getenv("LLM_MODEL", "hf.co/qwen/qwen3-vl-8b-instruct-gguf:q4_k_m"),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "1800")),
            llm_max_output_tokens=_positive_int("LLM_MAX_OUTPUT_TOKENS", 16000),
            llm_chunk_chars=_positive_int("LLM_CHUNK_CHARS", 6000),
            llm_max_images_per_request=_positive_int("LLM_MAX_IMAGES_PER_REQUEST", 4),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_disable_reasoning=os.getenv("LLM_DISABLE_REASONING", "true").strip().lower() != "false",
            log_level=os.getenv("LOG_LEVEL", "").strip().upper() or None,
            jwt_secret=jwt_secret,
            jwt_client_secret=jwt_client_secret,
            jwt_issuer=os.getenv("JWT_ISSUER", "form-digitizer"),
            jwt_audience=os.getenv("JWT_AUDIENCE", "form-api"),
        )


config = Config.from_env()
