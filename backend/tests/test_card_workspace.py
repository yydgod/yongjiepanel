"""Card ↔ dsh workspace binding tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _prepare_storages(tmp_path: Path) -> Path:
    storages = tmp_path / "dsh-home" / "storages"
    storages.mkdir(parents=True)
    (storages / "workspace.json").write_text(
        json.dumps({"tables": {"workspaces": {}}, "global": {"workspaceIds": []}}),
        encoding="utf-8",
    )
    (storages / "yongjie-cards.json").write_text(
        json.dumps({"unit": {"name": "yongjie-cards", "version": 1}, "cards": []}),
        encoding="utf-8",
    )
    return storages


def test_card_workspace_binding(client: TestClient, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import settings

    storages = _prepare_storages(tmp_path)
    monkeypatch.setattr(settings, "dsh_cards_store", str(storages / "yongjie-cards.json"))
    monkeypatch.setattr(settings, "dsh_token_file", str(tmp_path / "missing-token"))
    monkeypatch.setattr(settings, "dsh_token", "test-token")
    monkeypatch.setattr(settings, "dsh_base_url", "http://127.0.0.1:3082")
    monkeypatch.setattr(settings, "dsh_public_url", "")

    client.delete("/api/files", params={"path": "/pytest-card-ws", "recursive": True})
    assert client.post("/api/files/mkdir", json={"path": "/pytest-card-ws"}).status_code == 201

    created = client.post(
        "/api/cards",
        json={
            "title": "带工作区的卡片",
            "card_type": "custom",
            "target_ref": "demo",
            "group_name": "测试",
            "workspace_path": "/pytest-card-ws",
        },
    )
    assert created.status_code == 201, created.text
    card = created.json()
    assert card["workspace_path"] == "/pytest-card-ws"

    workspace_data = json.loads((storages / "workspace.json").read_text(encoding="utf-8"))
    table = workspace_data["tables"]["workspaces"]
    entry = next(item for item in table.values() if item["path"].endswith("/pytest-card-ws"))
    assert entry["title"] == "带工作区的卡片"

    cards_data = json.loads((storages / "yongjie-cards.json").read_text(encoding="utf-8"))
    mapping = next(item for item in cards_data["cards"] if item["card_id"] == card["id"])
    assert mapping["path"].endswith("/pytest-card-ws")
    assert mapping["workspace_id"] in table

    dsh = client.get(f"/api/cards/{card['id']}/dsh").json()
    assert dsh["configured"] is True
    assert dsh["workspace_id"] == mapping["workspace_id"]

    # 目录未变化时编辑其他字段，不应移除已有映射
    renamed = client.patch(
        f"/api/cards/{card['id']}",
        json={"title": "改名后的卡片", "workspace_path": "/pytest-card-ws"},
    )
    assert renamed.status_code == 200, renamed.text
    cards_data = json.loads((storages / "yongjie-cards.json").read_text(encoding="utf-8"))
    assert any(item["card_id"] == card["id"] for item in cards_data["cards"])

    # 清空目录 → 解除绑定
    cleared = client.patch(f"/api/cards/{card['id']}", json={"workspace_path": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["workspace_path"] is None
    cards_data = json.loads((storages / "yongjie-cards.json").read_text(encoding="utf-8"))
    assert not any(item["card_id"] == card["id"] for item in cards_data["cards"])
    assert client.get(f"/api/cards/{card['id']}/dsh").json()["configured"] is False

    # 目录不存在时拒绝保存
    bad = client.patch(
        f"/api/cards/{card['id']}", json={"workspace_path": "/pytest-card-ws-missing"}
    )
    assert bad.status_code == 400

    client.delete(f"/api/cards/{card['id']}")
    client.delete("/api/files", params={"path": "/pytest-card-ws", "recursive": True})
