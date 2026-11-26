"""Collector registry — add a new service kind here (plus a card type spec)."""

from __future__ import annotations

from app.collectors.base import BaseCollector
from app.collectors.custom_collector import CustomCollector
from app.collectors.docker_collector import DockerCollector
from app.collectors.port_collector import PortCollector
from app.collectors.systemd_collector import SystemdCollector


class CollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, BaseCollector] = {}
        for collector in (
            DockerCollector(),
            SystemdCollector(),
            PortCollector(),
            CustomCollector(),
        ):
            self._collectors[collector.kind] = collector

    def get(self, kind: str) -> BaseCollector | None:
        return self._collectors.get(kind)

    def all(self) -> list[BaseCollector]:
        return list(self._collectors.values())

    def diagnostics(self) -> list[dict[str, object]]:
        items = []
        for collector in self._collectors.values():
            ok, reason = collector.available()
            items.append(
                {
                    "kind": collector.kind,
                    "label": collector.label,
                    "available": ok,
                    "reason": reason,
                }
            )
        return items


registry = CollectorRegistry()
