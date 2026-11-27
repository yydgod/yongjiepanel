"""Unit tests for collector helpers (no external systems touched)."""

from __future__ import annotations

import pytest

from app.collectors.base import Snapshot
from app.collectors.port_collector import parse_port
from app.collectors.scheduler import CollectScheduler


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("8080", ("tcp", 8080)), ("tcp/5432", ("tcp", 5432)), ("udp/53", ("udp", 53))],
)
def test_parse_port_valid(raw: str, expected: tuple[str, int]) -> None:
    assert parse_port(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "70000", "tcp/", "http/80"])
def test_parse_port_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_port(raw)


def test_unavailable_snapshot_shape() -> None:
    snap = Snapshot.unavailable("nginx", "denied", "no permission", "container")
    payload = snap.to_dict()
    assert payload["status"] == "unavailable"
    assert payload["error"] == {"code": "denied", "message": "no permission"}
    assert payload["collected_at"]


def test_scheduler_marks_saturated_as_warning() -> None:
    snap = Snapshot(target="x", status="running", cpu_percent=91.2, memory_mb=100, memory_limit_mb=128)
    decorated = CollectScheduler._decorate(snap)
    assert decorated.status == "warning"
    assert "资源占用偏高" in decorated.detail
