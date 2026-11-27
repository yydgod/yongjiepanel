"""API contract tests (collectors disabled)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_and_meta(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    types = client.get("/api/card-types").json()
    assert {item["kind"] for item in types["items"]} == {"container", "systemd", "port", "custom"}
    assert any(tool["name"] == "restart_container" for tool in types["tools"])


def test_card_crud_flow(client: TestClient, card: dict) -> None:
    assert card["status"]["status"] == "unknown"

    listing = client.get("/api/cards", params={"q": "测试容器"}).json()
    assert any(item["id"] == card["id"] for item in listing["items"])
    assert listing["groups"]

    patched = client.patch(
        f"/api/cards/{card['id']}", json={"title": "改名后的容器", "subtitle": "已更新"}
    ).json()
    assert patched["title"] == "改名后的容器"
    assert "agent" not in patched

    reordered = client.post(
        "/api/cards/reorder", json={"items": [{"id": card["id"], "sort_order": 5}]}
    )
    assert reordered.status_code == 200

    detail = client.get(f"/api/cards/{card['id']}").json()
    assert detail["id"] == card["id"]
    assert "available_tools" not in detail

    assert client.delete(f"/api/cards/{card['id']}").status_code == 204
    assert client.get(f"/api/cards/{card['id']}").status_code == 404


def test_unknown_card_type_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/cards", json={"title": "bad", "card_type": "nope", "target_ref": "x"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation"


def test_quick_action_denied_for_port_card(client: TestClient) -> None:
    created = client.post(
        "/api/cards",
        json={"title": "端口卡", "card_type": "port", "target_ref": "9999"},
    ).json()
    response = client.post(f"/api/cards/{created['id']}/actions", json={"action": "restart"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "denied"


def test_system_status(client: TestClient) -> None:
    payload = client.get("/api/system/status").json()
    assert "collectors" in payload
    assert "ai" not in payload


def test_host_overview(client: TestClient) -> None:
    assert client.get("/api/host/overview").status_code == 200
    sampled = client.post("/api/host/sample")
    assert sampled.status_code == 200
    payload = client.get("/api/host/overview").json()
    assert payload["available"] is True
    assert payload["system"]["hostname"]
    assert payload["memory"]["total_mb"] > 0
    assert len(payload["cpu"]["per_core"]) >= 1
    assert isinstance(payload["disk"]["partitions"], list)
    assert isinstance(payload["network"]["interfaces"], list)
    assert isinstance(payload["processes"], list)
    assert payload["health"]["status"] in {"ok", "warning", "critical"}
    assert isinstance(payload["history"], list) and payload["history"]
    point = payload["history"][-1]
    assert {"ts", "cpu", "mem", "net_up", "net_down", "disk_read", "disk_write"} <= set(point)
