import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    secret_key: str
    form_api_url: str
    jwt_client_secret: str
    request_timeout_seconds: float
    max_upload_size_bytes: int
    result_store_dir: str
    result_store_ttl_seconds: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            secret_key=os.getenv("FLASK_SECRET_KEY", "dev-preview-secret-change-in-env"),
            form_api_url=os.getenv("FORM_API_URL", "http://form-api:8080").rstrip("/"),
            jwt_client_secret=os.getenv("JWT_CLIENT_SECRET", "").strip(),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "1800")),
            max_upload_size_bytes=int(os.getenv("MAX_UPLOAD_SIZE_BYTES", "10485760")),
            result_store_dir=os.getenv("RESULT_STORE_DIR", "/tmp/form-viewer-results").strip(),
            result_store_ttl_seconds=int(os.getenv("RESULT_STORE_TTL_SECONDS", "3600")),
        )
