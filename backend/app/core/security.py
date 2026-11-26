"""Password hashing and opaque token helpers.

Passwords use ``hashlib.scrypt`` (OWASP-recommended memory-hard KDF) so the
service needs no extra runtime dependency. Hashes are self-describing and can
be re-hashed when parameters change. Raw tokens are never stored: only their
SHA-256 digest is persisted.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 3
_SALT_BYTES = 16
_DK_LEN = 32
_MAXMEM = 128 * 1024 * 1024

_DUMMY_HASH: str | None = None


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=_DK_LEN,
        maxmem=_MAXMEM,
    )


def _encode(salt: bytes, derived: bytes, n: int, r: int, p: int) -> str:
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(derived)}"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return _encode(salt, derived, SCRYPT_N, SCRYPT_R, SCRYPT_P)


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, n_raw, r_raw, p_raw, salt_raw, hash_raw = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = _unb64(salt_raw)
        expected = _unb64(hash_raw)
        derived = _derive(password, salt, int(n_raw), int(r_raw), int(p_raw))
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(derived, expected)


def needs_rehash(encoded: str | None) -> bool:
    if not encoded:
        return True
    try:
        scheme, n_raw, r_raw, p_raw, _, _ = encoded.split("$")
    except ValueError:
        return True
    return (
        scheme != "scrypt"
        or int(n_raw) != SCRYPT_N
        or int(r_raw) != SCRYPT_R
        or int(p_raw) != SCRYPT_P
    )


def dummy_password_hash() -> str:
    """Fixed-cost hash used to keep unknown-account logins timing-similar."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
    return _DUMMY_HASH


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equal(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
