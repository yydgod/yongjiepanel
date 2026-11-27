"""MCP server tool tests (no real Docker, systemd or panel API)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app import mcp_server


def test_create_workspace(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: list[tuple[str, str, Any]] = []

    def fake_api(method: str, path: str, payload: Any = None) -> Any:
        captured.append((method, path, payload))
        return {"workspace_id": "ws-1"}

    monkeypatch.setattr(mcp_server, "_api", fake_api)
    result = mcp_server.create_workspace("/data/demo", "演示工作区")
    assert result["workspace_id"] == "ws-1"
    assert captured == [
        ("POST", "/dsh/workspaces", {"path": "/data/demo", "title": "演示工作区"})
    ]


def test_create_service_card_passes_workspace(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: list[tuple[str, str, Any]] = []

    def fake_api(method: str, path: str, payload: Any = None) -> Any:
        captured.append((method, path, payload))
        if path == "/cards":
            return {"id": "card-1", "title": payload["title"]}
        if path == "/system/collect":
            return {"cards": 1}
        if path == "/cards/card-1":
            return {"id": "card-1", "workspace_path": "/data/demo"}
        raise AssertionError(path)

    monkeypatch.setattr(mcp_server, "_api", fake_api)
    result = mcp_server.create_service_card(
        "demo", "container", "demo-container", workspace_path="/data/demo"
    )
    assert result["id"] == "card-1"
    assert captured[0] == (
        "POST",
        "/cards",
        {
            "title": "demo",
            "card_type": "container",
            "target_ref": "demo-container",
            "group_name": "AI 生成",
            "workspace_path": "/data/demo",
        },
    )
    assert captured[1] == ("POST", "/system/collect", None)


class FakeContainer:
    short_id = "abc123"
    status = "running"

    def __init__(self) -> None:
        self.attrs = {"NetworkSettings": {"Ports": {"80/tcp": [{"HostPort": "8080"}]}}}
        self.reloaded = 0

    def reload(self) -> None:
        self.reloaded += 1

    def start(self) -> None:
        self.status = "running"


class FakeContainers:
    def __init__(self) -> None:
        self.run_kwargs: dict[str, Any] | None = None

    def get(self, _name: str) -> Any:
        raise RuntimeError("not found")

    def run(self, *args: Any, **kwargs: Any) -> FakeContainer:
        self.run_kwargs = kwargs
        return FakeContainer()


class FakeClient:
    def __init__(self) -> None:
        self.containers = FakeContainers()


def test_create_container_registers_card(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = FakeClient()
    monkeypatch.setattr(mcp_server, "_docker_client", lambda: client)
    captured: list[tuple[str, str, Any]] = []

    def fake_api(method: str, path: str, payload: Any = None) -> Any:
        captured.append((method, path, payload))
        if path == "/cards":
            return {"id": "card-2"}
        if path == "/system/collect":
            return {"cards": 1}
        if path == "/cards/card-2":
            return {"id": "card-2", "status": {"ports": [8080]}}
        raise AssertionError(path)

    monkeypatch.setattr(mcp_server, "_api", fake_api)
    result = mcp_server.create_container(
        "demo",
        "nginx:alpine",
        ports={"80/tcp": 8080},
        env={"A": "B"},
        volumes=["/data/demo:/app:rw"],
        workspace_path="/data/demo",
    )
    assert result["container"]["host_ports"] == [8080]
    assert result["card"]["id"] == "card-2"

    card_payload = captured[0][2]
    assert card_payload["card_type"] == "container"
    assert card_payload["target_ref"] == "demo"
    assert card_payload["workspace_path"] == "/data/demo"

    assert client.containers.run_kwargs is not None
    assert client.containers.run_kwargs["ports"] == {"80/tcp": 8080}
    assert client.containers.run_kwargs["environment"] == {"A": "B"}
    assert client.containers.run_kwargs["volumes"] == {
        "/data/demo": {"bind": "/app", "mode": "rw"}
    }


def test_create_systemd_service(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mcp_server, "UNIT_DIR", tmp_path)

    class Result:
        returncode = 0
        stdout = "active\n"
        stderr = ""

    calls: list[tuple[str, ...]] = []

    def fake_systemctl(*args: str) -> Result:
        calls.append(args)
        return Result()

    monkeypatch.setattr(mcp_server, "_systemctl", fake_systemctl)
    captured: list[tuple[str, str, Any]] = []

    def fake_api(method: str, path: str, payload: Any = None) -> Any:
        captured.append((method, path, payload))
        if path == "/cards":
            return {"id": "card-3"}
        if path == "/system/collect":
            return {"cards": 1}
        if path == "/cards/card-3":
            return {"id": "card-3"}
        raise AssertionError(path)

    monkeypatch.setattr(mcp_server, "_api", fake_api)
    result = mcp_server.create_systemd_service(
        "demo",
        "/bin/sleep 10",
        working_directory=str(tmp_path),
        environment={"MODE": "test"},
        workspace_path="/data/demo",
    )
    assert result["service"]["active"] is True
    unit = (tmp_path / "demo.service").read_text(encoding="utf-8")
    assert "ExecStart=/bin/sleep 10" in unit
    assert f"WorkingDirectory={tmp_path}" in unit
    assert 'Environment="MODE=test"' in unit
    assert ("enable", "--now", "demo.service") in calls
    assert captured[0][2]["card_type"] == "systemd"
    assert captured[0][2]["target_ref"] == "demo.service"
    assert captured[0][2]["workspace_path"] == "/data/demo"


def test_create_systemd_service_rejects_existing_unit(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mcp_server, "UNIT_DIR", tmp_path)
    (tmp_path / "demo.service").write_text("[Unit]\n", encoding="utf-8")
    try:
        mcp_server.create_systemd_service("demo", "/bin/true")
    except RuntimeError as exc:
        assert "unit 已存在" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
