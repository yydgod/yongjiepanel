"""Terminal session and history tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_terminal_sessions_commands_and_history(client: TestClient) -> None:
    created = client.post("/api/terminal/sessions", json={"title": "测试终端"})
    assert created.status_code == 201, created.text
    session = created.json()
    assert session["title"] == "测试终端"
    session_id = session["id"]

    result = client.post(
        "/api/terminal/exec",
        json={"session_id": session_id, "command": "printf 'hello\\n'"},
    ).json()
    assert result["output"] == "hello\n"
    assert result["exit_code"] == 0
    assert result["cwd"] == session["cwd"]

    changed = client.post(
        "/api/terminal/exec",
        json={"session_id": session_id, "command": "cd /tmp"},
    ).json()
    assert changed["exit_code"] == 0
    assert changed["cwd"] == "/tmp"

    pwd = client.post(
        "/api/terminal/exec",
        json={"session_id": session_id, "command": "pwd"},
    ).json()
    assert pwd["output"].strip() == "/tmp"

    failed = client.post(
        "/api/terminal/exec",
        json={"session_id": session_id, "command": "exit 7"},
    ).json()
    assert failed["exit_code"] == 7

    history = client.get("/api/terminal/history").json()["items"]
    assert [item["command"] for item in history[:3]] == ["exit 7", "pwd", "cd /tmp"]

    # 每个终端有独立的工作目录
    second = client.post("/api/terminal/sessions", json={}).json()
    assert second["cwd"] == str(Path.home())
    assert client.delete(f"/api/terminal/sessions/{second['id']}").status_code == 204

    assert client.delete(f"/api/terminal/sessions/{session_id}").status_code == 204
    assert (
        client.post(
            "/api/terminal/exec",
            json={"session_id": session_id, "command": "pwd"},
        ).status_code
        == 404
    )


def test_terminal_rejects_blank_command(client: TestClient) -> None:
    session_id = client.post("/api/terminal/sessions", json={}).json()["id"]
    response = client.post(
        "/api/terminal/exec", json={"session_id": session_id, "command": "   "}
    )
    assert response.status_code == 400
    client.delete(f"/api/terminal/sessions/{session_id}")
