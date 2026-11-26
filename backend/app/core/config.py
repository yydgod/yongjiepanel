"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "永杰面板"
    env: str = "dev"
    api_prefix: str = "/api"

    # storage
    database_url: str = f"sqlite:///{DATA_DIR / 'board.db'}"
    sqlite_wal: bool = True
    seed_demo: bool = True

    # security
    secret_key: str = "dev-insecure-secret-change-me-32bytes"
    admin_token: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

    # collectors
    collect_interval: int = 5
    collect_timeout: float = 8.0
    docker_enabled: bool = True
    systemd_enabled: bool = True
    port_enabled: bool = True
    metric_history_points: int = 180
    log_tail_lines: int = 200

    # host monitor (主页看板：CPU / 内存 / 磁盘 / 网络)
    host_interval: float = 3.0
    host_history_points: int = 120

    # optional provider keys (alternative to entering them in the UI)
    deepseek_api_key: str = ""
    hunyuan_api_key: str = ""
    qwen_api_key: str = ""

    # AI gateway
    openclaw_base_url: str = ""
    openclaw_token: str = ""
    openclaw_mode: str = "openai"  # openai | channel
    openclaw_health_ttl: int = 30
    llm_timeout: float = 60.0
    allow_mock_ai: bool = True
    chat_max_tool_rounds: int = 4
    confirm_token_ttl: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
