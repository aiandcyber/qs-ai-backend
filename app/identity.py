"""Caller-identity seam for the QS agent.

Only the QS Agent endpoint is protected — to stop bots / abuse of LLM tokens.
Everything else stays open.

* AUTH_MODE=dev   - every request is one fixed local principal (open, offline dev).
* AUTH_MODE=auth0 - validate an Auth0 RS256 Bearer JWT; login is enforced.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Header, HTTPException

from app import config

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class Principal:
    owner_id: str
    email: str | None = None
    name: str | None = None
    claims: dict | None = None

    @property
    def storage_key(self) -> str:
        return _UNSAFE.sub("_", self.owner_id).strip("_") or "anon"


_DEV_PRINCIPAL = Principal(owner_id=config.DEV_OWNER_ID, email="dev@local", name="Dev User")

_jwk_client = None


def _verify_auth0(token: str) -> Principal:
    if not config.AUTH0_DOMAIN or not config.AUTH0_AUDIENCE:
        raise HTTPException(500, "AUTH0_DOMAIN/AUTH0_AUDIENCE are not configured")
    import jwt
    from jwt import PyJWKClient

    global _jwk_client
    if _jwk_client is None:
        _jwk_client = PyJWKClient(f"https://{config.AUTH0_DOMAIN}/.well-known/jwks.json")

    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        data = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.AUTH0_AUDIENCE,
            issuer=f"https://{config.AUTH0_DOMAIN}/",
        )
    except Exception as exc:  # noqa: BLE001 - any decode failure is a 401
        raise HTTPException(401, f"Invalid token: {exc}") from exc

    sub = data.get("sub")
    if not sub:
        raise HTTPException(401, "Token is missing the 'sub' claim")
    return Principal(owner_id=sub, email=data.get("email"), name=data.get("name"), claims=data)


def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    """FastAPI dependency: resolve the caller. Enforces login only under AUTH_MODE=auth0."""
    if config.AUTH_MODE == "dev":
        return _DEV_PRINCIPAL
    if config.AUTH_MODE == "auth0":
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Missing or malformed Authorization Bearer token")
        return _verify_auth0(authorization.split(" ", 1)[1].strip())
    raise HTTPException(500, f"Unknown AUTH_MODE {config.AUTH_MODE!r}")
