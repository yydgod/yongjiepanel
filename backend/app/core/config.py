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

    # dsh（DeepSeek Harness）原生工作区
    dsh_base_url: str = "http://127.0.0.1:3082"
    dsh_public_url: str = ""  # 浏览器访问地址；为空时回退 dsh_base_url
    dsh_token: str = ""
    dsh_token_file: str = "/data/yongjie/dsh-token"
    dsh_cards_store: str = "~/.dsh/storages/yongjie-cards.json"


    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
