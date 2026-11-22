"""Shared-secret HS256 tokens for local API access."""

import hmac
import time
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import config

router = APIRouter()
bearer = HTTPBearer(auto_error=False, bearerFormat="JWT")
client_bearer = HTTPBearer(
    auto_error=False, scheme_name="ClientCredential", description="Client secret used to request a short-lived JWT."
)
TOKEN_TTL_SECONDS = 900
ALGORITHM = "HS256"


def require_jwt(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
    if not config.jwt_secret:
        return
    try:
        if credentials is None:
            raise ValueError("Missing bearer token")
        claims = jwt.decode(
            credentials.credentials,
            config.jwt_secret,
            algorithms=[ALGORITHM],
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
            options={"require": ["exp", "iss", "aud"]},
        )
        if type(claims["exp"]) is not int or ("nbf" in claims and type(claims["nbf"]) is not int):
            raise ValueError("Invalid JWT timestamp")
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _mint_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {"iss": config.jwt_issuer, "aud": config.jwt_audience, "iat": now, "exp": now + TOKEN_TTL_SECONDS},
        config.jwt_secret,
        algorithm=ALGORITHM,
    )


@router.post("/token")
def issue_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(client_bearer)],
    response: Response,
) -> dict[str, str | int]:
    if not config.jwt_secret or not config.jwt_client_secret:
        raise HTTPException(status_code=404, detail="Automatic token issuance is disabled.")
    if credentials is None or not hmac.compare_digest(
        credentials.credentials.encode(),
        config.jwt_client_secret.encode(),
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid client credential is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": _mint_token(), "token_type": "Bearer", "expires_in": TOKEN_TTL_SECONDS}


if __name__ == "__main__":
    if not config.jwt_secret:
        raise SystemExit("Set JWT_SECRET before minting a token.")
    print(_mint_token())
