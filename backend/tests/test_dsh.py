"""dsh workspace creation tests (isolated registry)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _prepare_registry(tmp_path: Path):  # type: ignore[no-untyped-def]
    storages = tmp_path / "dsh-home" / "storages"
    storages.mkdir(parents=True)
    store = storages / "workspace.json"
    store.write_text(
        json.dumps({"tables": {"workspaces": {}}, "global": {"workspaceIds": []}}),
        encoding="utf-8",
    )
    return storages, store


def test_create_workspace_from_directory(client: TestClient, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import settings

    storages, store = _prepare_registry(tmp_path)
    monkeypatch.setattr(settings, "dsh_cards_store", str(storages / "yongjie-cards.json"))
    monkeypatch.setattr(settings, "dsh_token_file", str(tmp_path / "missing-token"))
    monkeypatch.setattr(settings, "dsh_token", "test-token")
    monkeypatch.setattr(settings, "dsh_base_url", "http://127.0.0.1:3082")
    monkeypatch.setattr(settings, "dsh_public_url", "")

    client.delete("/api/files", params={"path": "/pytest-workspace", "recursive": True})
    assert client.post("/api/files/mkdir", json={"path": "/pytest-workspace"}).status_code == 201

    created = client.post(
        "/api/dsh/workspaces",
        json={"path": "/pytest-workspace", "title": "演示工作区"},
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["created"] is True
    assert payload["configured"] is True
    assert payload["title"] == "演示工作区"
    assert "workspace=" in payload["url"]

    data = json.loads(store.read_text(encoding="utf-8"))
    workspace = data["tables"]["workspaces"][payload["workspace_id"]]
    assert workspace["path"].endswith("/pytest-workspace")
    assert payload["workspace_id"] in data["global"]["workspaceIds"]
    assert list(storages.glob("workspace.json.bak-*"))

    again = client.post("/api/dsh/workspaces", json={"path": "/pytest-workspace"})
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["workspace_id"] == payload["workspace_id"]

    missing = client.post("/api/dsh/workspaces", json={"path": "/pytest-workspace-missing"})
    assert missing.status_code == 404

    client.delete("/api/files", params={"path": "/pytest-workspace", "recursive": True})


def test_create_workspace_requires_registry(client: TestClient, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "dsh_cards_store", str(tmp_path / "missing-storages" / "yongjie-cards.json")
    )

    client.delete("/api/files", params={"path": "/pytest-workspace-2", "recursive": True})
    assert client.post("/api/files/mkdir", json={"path": "/pytest-workspace-2"}).status_code == 201

    response = client.post("/api/dsh/workspaces", json={"path": "/pytest-workspace-2"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_configured"

    client.delete("/api/files", params={"path": "/pytest-workspace-2", "recursive": True})
