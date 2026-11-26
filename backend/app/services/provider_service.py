"""Provider CRUD + connectivity test. Keys are encrypted at rest and masked out."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.ai.gateway import GatewayRequest, gateway
from app.ai.providers import PRESETS, ProviderConfig, list_presets
from app.core.errors import NOT_CONFIGURED, AppError, not_found
from app.core.security import decrypt_secret, encrypt_secret, mask_key
from app.models import Agent, Provider
from app.schemas.provider import ProviderIn, ProviderOut, ProviderTestResult


def to_config(provider: Provider) -> ProviderConfig:
    return ProviderConfig(
        id=provider.id,
        name=provider.name,
        kind=provider.kind,
        base_url=provider.base_url,
        api_key=decrypt_secret(provider.api_key_encrypted),
        default_model=provider.default_model,
        models=list(provider.models or []),
        timeout=provider.timeout,
        extra=dict(provider.extra or {}),
    )


def serialize(provider: Provider) -> dict[str, Any]:
    key = decrypt_secret(provider.api_key_encrypted)
    payload = ProviderOut.model_validate(
        {
            "id": provider.id,
            "name": provider.name,
            "kind": provider.kind,
            "base_url": provider.base_url,
            "default_model": provider.default_model,
            "models": list(provider.models or []),
            "extra": dict(provider.extra or {}),
            "temperature": provider.temperature,
            "timeout": provider.timeout,
            "is_default": provider.is_default,
            "enabled": provider.enabled,
            "has_key": bool(key),
            "api_key_masked": mask_key(key),
            "created_at": provider.created_at,
        }
    )
    return payload.model_dump(mode="json")


def list_providers(db: Session) -> list[dict[str, Any]]:
    rows = db.query(Provider).order_by(Provider.created_at).all()
    return [serialize(row) for row in rows]


def get_provider(db: Session, provider_id: str) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise not_found("供应商", provider_id)
    return provider


def _apply_default(db: Session, provider: Provider) -> None:
    if not provider.is_default:
        return
    for other in db.query(Provider).filter(Provider.id != provider.id).all():
        other.is_default = False


def create_provider(db: Session, payload: ProviderIn) -> dict[str, Any]:
    provider = Provider(
        name=payload.name,
        kind=payload.kind,
        base_url=payload.base_url.rstrip("/"),
        default_model=payload.default_model,
        models=payload.models,
        api_key_encrypted=encrypt_secret(payload.api_key),
        extra=payload.extra,
        temperature=payload.temperature,
        timeout=payload.timeout,
        is_default=payload.is_default or db.query(Provider).count() == 0,
        enabled=payload.enabled,
    )
    db.add(provider)
    db.flush()
    _apply_default(db, provider)
    db.commit()
    return serialize(provider)


def update_provider(db: Session, provider_id: str, payload: ProviderIn) -> dict[str, Any]:
    provider = get_provider(db, provider_id)
    provider.name = payload.name
    provider.kind = payload.kind
    provider.base_url = payload.base_url.rstrip("/")
    provider.default_model = payload.default_model
    provider.models = payload.models
    provider.extra = payload.extra
    provider.temperature = payload.temperature
    provider.timeout = payload.timeout
    provider.is_default = payload.is_default
    provider.enabled = payload.enabled
    if payload.api_key:
        provider.api_key_encrypted = encrypt_secret(payload.api_key)
    _apply_default(db, provider)
    db.commit()
    return serialize(provider)


def delete_provider(db: Session, provider_id: str) -> None:
    provider = get_provider(db, provider_id)
    for agent in db.query(Agent).filter(Agent.provider_id == provider_id).all():
        agent.provider_id = None
    db.delete(provider)
    db.commit()
    remaining = db.query(Provider).order_by(Provider.created_at).first()
    if remaining is not None and not any(p.is_default for p in db.query(Provider).all()):
        remaining.is_default = True
        db.commit()


def default_provider(db: Session) -> Provider | None:
    return (
        db.query(Provider)
        .filter(Provider.enabled.is_(True))
        .order_by(Provider.is_default.desc(), Provider.created_at)
        .first()
    )


async def test_provider(db: Session, provider_id: str) -> ProviderTestResult:
    provider = get_provider(db, provider_id)
    config = to_config(provider)
    if not config.usable:
        raise AppError(NOT_CONFIGURED, "该供应商尚未配置 API Key，无法测试", 400)
    started = time.perf_counter()
    result = await gateway.chat(
        GatewayRequest(
            messages=[
                {"role": "system", "content": "你是连通性测试助手，请只回复 OK。"},
                {"role": "user", "content": "ping"},
            ],
            provider=config,
            gateway="direct",
            max_tokens=16,
            temperature=0,
        )
    )
    latency = int((time.perf_counter() - started) * 1000)
    return ProviderTestResult(
        ok=True,
        latency_ms=latency,
        model=result.model,
        channel=result.channel,
        message="连通性正常",
        sample=(result.content or "")[:120],
    )


def presets() -> list[dict[str, Any]]:
    return list_presets()


def preset_for(kind: str) -> dict[str, Any]:
    return PRESETS.get(kind, PRESETS["custom"])
