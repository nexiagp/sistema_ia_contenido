"""Password-only team access for the private editorial application.

The password is stored as a salted PBKDF2 hash. Browser sessions are short-lived,
signed cookies; neither the password nor the signing key is sent to the browser.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time


HASH_ITERATIONS = 310_000
SESSION_SECONDS = 8 * 60 * 60


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def make_password_hash(password: str) -> str:
    if len(password) < 16:
        raise ValueError("The team password must have at least 16 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return f"pbkdf2_sha256${HASH_ITERATIONS}${_encode(salt)}${_encode(digest)}"


def valid_password_hash(encoded: str) -> bool:
    try:
        algorithm, iterations, salt, digest = encoded.split("$")
        return (
            algorithm == "pbkdf2_sha256"
            and HASH_ITERATIONS <= int(iterations) <= 1_000_000
            and len(_decode(salt)) >= 16
            and len(_decode(digest)) == 32
        )
    except (ValueError, TypeError, binascii.Error):
        return False


def verify_password(password: str, encoded: str) -> bool:
    if not valid_password_hash(encoded) or not isinstance(password, str) or len(password) > 256:
        return False
    _, iterations, salt, expected = encoded.split("$")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _decode(salt), int(iterations))
    return hmac.compare_digest(actual, _decode(expected))


def valid_session_secret(secret: str) -> bool:
    return isinstance(secret, str) and len(secret) >= 32


def issue_session(secret: str, *, now: int | None = None) -> str:
    if not valid_session_secret(secret):
        raise ValueError("A strong session secret is required.")
    timestamp = int(time.time() if now is None else now)
    payload = _encode(json.dumps({"v": 1, "iat": timestamp, "exp": timestamp + SESSION_SECONDS}, separators=(",", ":")).encode("utf-8"))
    signature = _encode(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_session(token: str, secret: str, *, now: int | None = None) -> bool:
    if not token or len(token) > 1024 or not valid_session_secret(secret):
        return False
    try:
        payload, signature = token.split(".")
        expected = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature)):
            return False
        data = json.loads(_decode(payload))
        timestamp = int(time.time() if now is None else now)
        return (
            data.get("v") == 1
            and isinstance(data.get("iat"), int)
            and isinstance(data.get("exp"), int)
            and data["iat"] <= timestamp < data["exp"]
            and data["exp"] - data["iat"] == SESSION_SECONDS
        )
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, binascii.Error):
        return False
