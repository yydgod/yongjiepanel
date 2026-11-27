"""AI card workspace bootstrap tests."""

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
    return storages


def test_bootstrap_workspace_creates_directory_and_registry(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import settings

    storages = _prepare_storages(tmp_path)
    workspace_root = tmp_path / "workspaces"
    monkeypatch.setattr(settings, "workspace_root", str(workspace_root))
    monkeypatch.setattr(settings, "dsh_cards_store", str(storages / "yongjie-cards.json"))
    monkeypatch.setattr(settings, "dsh_token_file", str(tmp_path / "missing-token"))
    monkeypatch.setattr(settings, "dsh_token", "test-token")
    monkeypatch.setattr(settings, "dsh_base_url", "http://127.0.0.1:3082")

    response = client.post(
        "/api/dsh/workspaces/bootstrap",
        json={"title": "演示卡片", "directory": "demo-card"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["directory"] == "demo-card"
    assert payload["title"] == "演示卡片"
    assert payload["created"] is True
    expected = (workspace_root / "demo-card").resolve()
    assert Path(payload["absolute_path"]) == expected
    assert expected.is_dir()

    registry = json.loads((storages / "workspace.json").read_text(encoding="utf-8"))
    entry = registry["tables"]["workspaces"][payload["workspace_id"]]
    assert entry["path"] == str(expected)
    assert entry["title"] == "演示卡片"

    again = client.post(
        "/api/dsh/workspaces/bootstrap",
        json={"title": "演示卡片", "directory": "demo-card"},
    )
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["workspace_id"] == payload["workspace_id"]


def test_bootstrap_rejects_invalid_directory(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import settings

    storages = _prepare_storages(tmp_path)
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "dsh_cards_store", str(storages / "yongjie-cards.json"))

    for name in ("../escape", "-hidden", "带中文", "a/b"):
        response = client.post(
            "/api/dsh/workspaces/bootstrap",
            json={"title": "坏目录", "directory": name},
        )
        assert response.status_code == 400, (name, response.text)

    missing_title = client.post(
        "/api/dsh/workspaces/bootstrap", json={"title": "", "directory": "ok"}
    )
    assert missing_title.status_code == 422


def test_bootstrap_generates_directory_when_omitted(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import settings

    storages = _prepare_storages(tmp_path)
    workspace_root = tmp_path / "workspaces"
    monkeypatch.setattr(settings, "workspace_root", str(workspace_root))
    monkeypatch.setattr(settings, "dsh_cards_store", str(storages / "yongjie-cards.json"))

    response = client.post(
        "/api/dsh/workspaces/bootstrap", json={"title": "自动目录"}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["directory"].startswith("card-")
    assert (workspace_root / payload["directory"]).is_dir()
