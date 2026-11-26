"""API key encryption (Fernet) and optional bearer auth."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException

from app.core.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str | None) -> str | None:
    if not plain:
        return None
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher: str | None) -> str | None:
    if not cipher:
        return None
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def mask_key(plain_or_cipher: str | None) -> str:
    if not plain_or_cipher:
        return ""
    if len(plain_or_cipher) <= 8:
        return "****"
    return f"{plain_or_cipher[:3]}****{plain_or_cipher[-4:]}"


async def require_admin(authorization: str | None = Header(default=None)) -> None:
    """Optional bearer guard: enforced only when ADMIN_TOKEN is configured."""
    if not settings.admin_token:
        return
    expected = f"Bearer {settings.admin_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="缺少或错误的访问令牌")
