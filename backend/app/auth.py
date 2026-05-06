"""Admin auth: bcrypt password verification + JWT issuing/decoding.

A single admin user is bootstrapped from env (NMS10_ADMIN_PASSWORD) on startup.
JWT carries the admin user id and a 24h expiry. FastAPI dependency
`require_admin` guards admin routes.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text

from . import config
from .db import engine


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def issue_token(admin_id: int, username: str) -> dict:
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(seconds=config.JWT_TTL_SECONDS)
    payload = {
        "sub": str(admin_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    return {"token": token, "expires_at": exp.isoformat()}


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])


def ensure_admin_user() -> None:
    """Create the single admin row from env-var password if it doesn't exist.
    Idempotent. If the password env var changes later, we update the hash."""
    pw_hash = hash_password(config.ADMIN_PASSWORD)
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id, password_hash FROM admin_users WHERE username = :u"),
            {"u": config.ADMIN_USERNAME},
        ).first()
        if existing is None:
            conn.execute(
                text("INSERT INTO admin_users (username, password_hash) VALUES (:u, :h)"),
                {"u": config.ADMIN_USERNAME, "h": pw_hash},
            )
            return
        # If the configured password no longer matches, update the stored hash.
        if not verify_password(config.ADMIN_PASSWORD, existing.password_hash):
            conn.execute(
                text("UPDATE admin_users SET password_hash = :h WHERE id = :id"),
                {"h": pw_hash, "id": existing.id},
            )


def require_admin(authorization: Optional[str] = Header(default=None)) -> dict:
    """FastAPI dependency. Raises 401 unless a valid JWT is present in the
    Authorization: Bearer <token> header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return payload


def authenticate(username: str, password: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, username, password_hash FROM admin_users WHERE username = :u"),
            {"u": username},
        ).first()
    if row is None:
        return None
    if not verify_password(password, row.password_hash):
        return None
    return {"id": row.id, "username": row.username}
