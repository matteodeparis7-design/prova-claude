"""Password e token di accesso, solo con la libreria standard."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApiToken, User

_ITERATIONS = 310_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("La password deve avere almeno 8 caratteri.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return f"{_ALGO}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != _ALGO:
            return False
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check, digest)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(session: Session, user: User, ttl_hours: int) -> str:
    raw = secrets.token_urlsafe(32)
    session.add(ApiToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    ))
    session.flush()
    return raw


def user_for_token(session: Session, raw: str) -> User | None:
    if not raw:
        return None
    tok = session.scalar(select(ApiToken).where(ApiToken.token_hash == _hash_token(raw)))
    if tok is None:
        return None
    expires = tok.expires_at if tok.expires_at.tzinfo else tok.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    user = tok.user
    return user if user.is_active else None


def revoke_token(session: Session, raw: str) -> None:
    tok = session.scalar(select(ApiToken).where(ApiToken.token_hash == _hash_token(raw)))
    if tok is not None:
        session.delete(tok)
