"""Provider presets + a plain config object decoupled from the ORM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "kind": "deepseek",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "docs": "https://platform.deepseek.com/api_docs",
        "extra": {"supports_json_mode": True},
    },
    "hunyuan": {
        "kind": "hunyuan",
        "label": "腾讯混元 HY",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "models": ["hunyuan-turbos-latest", "hunyuan-pro", "hunyuan-lite"],
        "docs": "https://cloud.tencent.com/document/product/1729",
        "extra": {"supports_json_mode": True},
    },
    "qwen": {
        "kind": "qwen",
        "label": "通义千问 Qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
        "docs": "https://help.aliyun.com/zh/model-studio/",
        "extra": {"supports_json_mode": True},
    },
    "custom": {
        "kind": "custom",
        "label": "自定义 OpenAI 兼容端点",
        "base_url": "http://127.0.0.1:11434/v1",
        "models": ["local-model"],
        "docs": "任意兼容 /v1/chat/completions 的服务",
        "extra": {},
    },
}


def list_presets() -> list[dict[str, Any]]:
    return [dict(value) for value in PRESETS.values()]


@dataclass(slots=True)
class ProviderConfig:
    """Resolved provider ready for HTTP calls (key already decrypted)."""

    id: str
    name: str
    kind: str
    base_url: str
    api_key: str | None
    default_model: str
    models: list[str] = field(default_factory=list)
    timeout: float = 60.0
    extra: dict[str, Any] = field(default_factory=dict)

    def model_or(self, requested: str | None) -> str:
        if requested:
            return requested
        if self.default_model:
            return self.default_model
        return self.models[0] if self.models else "gpt-4o-mini"

    @property
    def usable(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)
