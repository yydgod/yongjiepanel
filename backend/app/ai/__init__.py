"""AI gateway package (OpenClaw + OpenAI-compatible providers)."""

from app.ai.gateway import AIGateway, GatewayRequest, GatewayResult, gateway
from app.ai.providers import PRESETS, ProviderConfig, list_presets

__all__ = ["AIGateway", "GatewayRequest", "GatewayResult", "PRESETS", "ProviderConfig", "gateway", "list_presets"]
