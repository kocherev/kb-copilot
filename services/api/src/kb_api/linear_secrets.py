"""The key behind stored Linear tokens and the OAuth state."""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Annotated

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException

from kb_api.settings import PLACEHOLDERS, load_settings

STATE_TTL_SECONDS = 600
NONCE_BYTES = 12


class InvalidState(Exception):
    pass


@dataclass(frozen=True)
class LinearConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    key: bytes


def parse_key(raw: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except binascii.Error:
        key = b""
    if len(key) != 32:
        raise HTTPException(
            status_code=503,
            detail="LINEAR_TOKEN_KEY must be 32 random bytes in base64",
        )
    return key


def optional_linear_config() -> LinearConfig | None:
    settings = load_settings()
    required = (
        settings.linear_client_id,
        settings.linear_client_secret,
        settings.linear_token_key,
    )
    if any(value.strip() in PLACEHOLDERS for value in required):
        return None
    return LinearConfig(
        client_id=settings.linear_client_id.strip(),
        client_secret=settings.linear_client_secret.strip(),
        redirect_uri=settings.linear_redirect_uri,
        key=parse_key(settings.linear_token_key.strip()),
    )


def linear_config() -> LinearConfig:
    config = optional_linear_config()
    if config is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Linear is not configured: set LINEAR_CLIENT_ID, "
                "LINEAR_CLIENT_SECRET and LINEAR_TOKEN_KEY"
            ),
        )
    return config


Config = Annotated[LinearConfig, Depends(linear_config)]


def encrypt(key: bytes, org_id: str, plaintext: str) -> bytes:
    """Bind the ciphertext to its org, so a copied row does not decrypt elsewhere."""
    nonce = secrets.token_bytes(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext.encode(), org_id.encode())


def decrypt(key: bytes, org_id: str, stored: bytes) -> str:
    nonce, ciphertext = stored[:NONCE_BYTES], stored[NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ciphertext, org_id.encode()).decode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(key: bytes, payload: str) -> str:
    state_key = hmac.new(key, b"linear-oauth-state", hashlib.sha256).digest()
    return _b64(hmac.new(state_key, payload.encode(), hashlib.sha256).digest())


@dataclass(frozen=True)
class StateClaims:
    org_id: str
    user_id: str
    nonce: str
    expires_at: int


def sign_state(key: bytes, org_id: str, user_id: str, now: float) -> str:
    claims = {
        "o": org_id,
        "u": user_id,
        "n": secrets.token_urlsafe(16),
        "e": int(now) + STATE_TTL_SECONDS,
    }
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{payload}.{_mac(key, payload)}"


def verify_state(key: bytes, state: str, now: float) -> StateClaims:
    payload, _, mac = state.partition(".")
    if not hmac.compare_digest(mac, _mac(key, payload)):
        raise InvalidState
    try:
        claims = json.loads(_unb64(payload))
        parsed = StateClaims(
            org_id=claims["o"],
            user_id=claims["u"],
            nonce=claims["n"],
            expires_at=claims["e"],
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidState from exc
    if parsed.expires_at < now:
        raise InvalidState
    return parsed
