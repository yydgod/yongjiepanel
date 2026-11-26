"""API contract tests (mock AI channel, collectors disabled)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_and_meta(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    types = client.get("/api/card-types").json()
    assert {item["kind"] for item in types["items"]} == {"container", "systemd", "port", "custom"}
    assert any(tool["name"] == "restart_container" for tool in types["tools"])


def test_card_crud_flow(client: TestClient, card: dict) -> None:
    assert card["agent"]["name"] == "测试助手"
    assert card["status"]["status"] == "unknown"

    listing = client.get("/api/cards", params={"q": "测试容器"}).json()
    assert any(item["id"] == card["id"] for item in listing["items"])
    assert listing["groups"]

    patched = client.patch(
        f"/api/cards/{card['id']}", json={"title": "改名后的容器", "subtitle": "已更新"}
    ).json()
    assert patched["title"] == "改名后的容器"

    reordered = client.post(
        "/api/cards/reorder", json={"items": [{"id": card["id"], "sort_order": 5}]}
    )
    assert reordered.status_code == 200

    detail = client.get(f"/api/cards/{card['id']}").json()
    assert "available_tools" in detail and detail["available_tools"]

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


def test_provider_key_masked_and_preserved(client: TestClient) -> None:
    created = client.post(
        "/api/providers",
        json={
            "name": "测试供应商",
            "kind": "custom",
            "base_url": "http://127.0.0.1:9999/v1",
            "default_model": "demo-model",
            "models": ["demo-model"],
            "api_key": "sk-test-1234567890",
        },
    ).json()
    assert created["has_key"] is True
    assert created["api_key_masked"].startswith("sk-")
    assert "1234567890" not in created["api_key_masked"]

    updated = client.put(
        f"/api/providers/{created['id']}",
        json={
            "name": "测试供应商",
            "kind": "custom",
            "base_url": "http://127.0.0.1:9999/v1",
            "default_model": "demo-model",
            "models": ["demo-model"],
        },
    ).json()
    assert updated["has_key"] is True, "留空 api_key 时不应清空已保存的密钥"

    assert client.delete(f"/api/providers/{created['id']}").status_code == 204


def test_provider_without_key_cannot_be_tested(client: TestClient) -> None:
    created = client.post(
        "/api/providers",
        json={
            "name": "无密钥供应商",
            "kind": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "models": ["deepseek-chat"],
        },
    ).json()
    response = client.post(f"/api/providers/{created['id']}/test")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "not_configured"
    client.delete(f"/api/providers/{created['id']}")


def test_chat_mock_channel(client: TestClient, card: dict) -> None:
    response = client.post(
        f"/api/cards/{card['id']}/chat",
        json={"message": "当前状态如何？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["session_id"]
    assert payload["channel"] == "mock"
    assert "演示通道" in payload["content"]

    session = client.get(f"/api/chat/sessions/{payload['session_id']}").json()
    roles = [message["role"] for message in session["messages"]]
    assert roles[0] == "user" and "assistant" in roles


def test_generate_card_mock(client: TestClient) -> None:
    response = client.post(
        "/api/generate/card",
        json={"description": "监控一个名为 redis-cache 的 Docker 容器"},
    )
    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["card_type"] == "container"
    assert draft["target_ref"] == "redis-cache"
    assert draft["tools"]


def test_customize_card_by_natural_language(client: TestClient, card: dict) -> None:
    response = client.post(
        f"/api/cards/{card['id']}/customize",
        json={"instruction": "归类到核心链路分组，换成紫色，提示词强调只读诊断"},
    )
    assert response.status_code == 200, response.text
    patch = response.json()
    assert patch["accent"] == "violet"
    assert patch["group_name"] == "核心链路"
    assert "只读诊断" in patch["system_prompt"]
    assert patch["channel"] == "local-rule"


def test_agent_config_update(client: TestClient, card: dict) -> None:
    response = client.put(
        f"/api/cards/{card['id']}/agent",
        json={
            "name": "只读守卫",
            "tools": ["get_status", "list_ports"],
            "temperature": 0.1,
            "max_tokens": 512,
            "gateway": "direct",
        },
    )
    assert response.status_code == 200, response.text
    agent = response.json()["agent"]
    assert agent["name"] == "只读守卫"
    assert agent["tools"] == ["get_status", "list_ports"]
    assert agent["gateway"] == "direct"


def test_confirm_unknown_token(client: TestClient) -> None:
    response = client.post("/api/chat/confirm", json={"token": "deadbeef"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_system_status(client: TestClient) -> None:
    payload = client.get("/api/system/status").json()
    assert "collectors" in payload
    assert payload["ai"]["mock_enabled"] is True
    assert payload["openclaw"]["configured"] is False

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
