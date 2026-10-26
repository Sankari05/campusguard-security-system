# =============================================================
# app/core/security.py
# Purpose : JWT token operations + BCrypt password hashing
# Pattern : Zero Plaintext Fallback, Cryptographic Token Verification
# =============================================================

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# BCrypt password context (strict enterprise hashing)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password Utilities ──────────────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using BCrypt."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a BCrypt hash.
    Strictly zero plaintext fallbacks: plain_password == hashed_password is NOT permitted.
    """
    if not hashed_password or not plain_password:
        return False
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


# ── JWT Utilities ───────────────────────────────────────────────────────────


def create_access_token(subject: str, role: str, jti: Optional[str] = None) -> str:
    """
    Generate a cryptographically signed JWT access token.
    Each token includes a unique 'jti' identifier enabling instant server-side revocation.
    """
    token_jti = jti or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.jwt_expiration_hours)
    payload = {
        "sub": subject,
        "role": role,
        "jti": token_jti,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and cryptographically validate a JWT token.
    Explicitly whitelists the configured HMAC algorithm to prevent 'alg: none' exploits.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None
