"""Card binding through the running dsh Remote API (mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def test_card_binding_uses_running_dsh(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import settings
    from app.services import dsh_service

    storages = tmp_path / "storages"
    storages.mkdir()
    monkeypatch.setattr(settings, "dsh_cards_store", str(storages / "yongjie-cards.json"))
    monkeypatch.setattr(settings, "dsh_token_file", str(tmp_path / "missing-token"))
    monkeypatch.setattr(settings, "dsh_token", "test-token")
    monkeypatch.setattr(settings, "dsh_base_url", "http://127.0.0.1:3082")
    monkeypatch.setattr(settings, "dsh_public_url", "")

    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_rpc(endpoint: str, args: dict[str, Any]) -> dict[str, Any] | None:
        calls.append((endpoint, args))
        if endpoint == "workspace/create":
            return {
                "workspace": {
                    "workspaceId": "remote-ws-1",
                    "path": args["path"],
                    "title": "remote-title",
                    "sessionIds": [],
                    "createdAt": "2026-11-27T00:00:00.000Z",
                    "updatedAt": "2026-11-27T00:00:00.000Z",
                },
                "created": True,
            }
        if endpoint == "workspace/rename":
            return {
                "workspace": {
                    "workspaceId": args["workspaceId"],
                    "path": "/remote",
                    "title": args["title"],
                    "sessionIds": [],
                    "createdAt": "2026-11-27T00:00:00.000Z",
                    "updatedAt": "2026-11-27T00:00:00.000Z",
                }
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    monkeypatch.setattr(dsh_service, "_remote_rpc", fake_rpc)

    client.delete("/api/files", params={"path": "/pytest-remote-ws", "recursive": True})
    assert client.post("/api/files/mkdir", json={"path": "/pytest-remote-ws"}).status_code == 201

    created = client.post(
        "/api/cards",
        json={
            "title": "远程工作区卡片",
            "card_type": "custom",
            "target_ref": "demo",
            "workspace_path": "/pytest-remote-ws",
        },
    )
    assert created.status_code == 201, created.text
    card = created.json()

    assert calls[0][0] == "workspace/create"
    assert calls[0][1]["path"].endswith("/pytest-remote-ws")
    assert calls[1][0] == "workspace/rename"
    assert calls[1][1]["title"] == "远程工作区卡片"

    mapping_data = json.loads(
        (storages / "yongjie-cards.json").read_text(encoding="utf-8")
    )
    mapping = next(item for item in mapping_data["cards"] if item["card_id"] == card["id"])
    assert mapping["workspace_id"] == "remote-ws-1"
    assert mapping["title"] == "远程工作区卡片"

    dsh = client.get(f"/api/cards/{card['id']}/dsh").json()
    assert dsh["configured"] is True
    assert dsh["workspace_id"] == "remote-ws-1"

    client.delete(f"/api/cards/{card['id']}")
    client.delete("/api/files", params={"path": "/pytest-remote-ws", "recursive": True})
