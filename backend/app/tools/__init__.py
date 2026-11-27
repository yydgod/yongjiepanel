"""Tool registry and card quick-action tools."""

from app.tools import container_tools, systemd_tools  # noqa: F401
from app.tools.registry import registry

tool_registry = registry

__all__ = ["registry", "tool_registry"]
