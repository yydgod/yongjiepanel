"""File manager API tests (sandboxed to FILE_ROOT)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_file_browser_flow(client: TestClient) -> None:
    base = "/pytest-files"
    client.delete("/api/files", params={"path": base, "recursive": True})

    created = client.post("/api/files/mkdir", json={"path": base})
    assert created.status_code == 201, created.text
    assert created.json()["path"] == base

    listing = client.get("/api/files/list", params={"path": "/"}).json()
    assert any(item["name"] == "pytest-files" and item["is_dir"] for item in listing["items"])
    assert listing["parent"] is None

    written = client.put(
        "/api/files/write",
        json={"path": f"{base}/hello.txt", "content": "你好，永杰\n"},
    )
    assert written.status_code == 200, written.text
    assert written.json()["size"] > 0

    read = client.get("/api/files/read", params={"path": f"{base}/hello.txt"}).json()
    assert read["content"] == "你好，永杰\n"
    assert read["binary"] is False
    assert read["editable"] is True

    files = client.get("/api/files/list", params={"path": base}).json()
    assert [item["name"] for item in files["items"]] == ["hello.txt"]

    renamed = client.post(
        "/api/files/rename",
        json={"path": f"{base}/hello.txt", "target": f"{base}/notes.txt"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["path"] == f"{base}/notes.txt"

    # non-empty directory requires recursive confirmation
    blocked = client.delete("/api/files", params={"path": base})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "conflict"

    deleted_file = client.delete("/api/files", params={"path": f"{base}/notes.txt"})
    assert deleted_file.status_code == 200
    deleted_dir = client.delete("/api/files", params={"path": base, "recursive": True})
    assert deleted_dir.status_code == 200

    missing = client.get("/api/files/read", params={"path": f"{base}/notes.txt"})
    assert missing.status_code == 404


def test_file_search(client: TestClient) -> None:
    client.delete("/api/files", params={"path": "/pytest-search", "recursive": True})
    assert client.post("/api/files/mkdir", json={"path": "/pytest-search"}).status_code == 201
    assert client.post("/api/files/mkdir", json={"path": "/pytest-search/sub"}).status_code == 201
    assert (
        client.put(
            "/api/files/write",
            json={"path": "/pytest-search/sub/needle-report.txt", "content": "x"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/files/write",
            json={"path": "/pytest-search/other.txt", "content": "y"},
        ).status_code
        == 200
    )

    result = client.get("/api/files/search", params={"q": "needle"}).json()
    assert result["items"][0]["path"] == "/pytest-search/sub/needle-report.txt"
    assert result["items"][0]["is_dir"] is False
    assert result["scanned"] > 0

    dirs = client.get("/api/files/search", params={"q": "pytest-search"}).json()
    assert any(item["path"] == "/pytest-search" and item["is_dir"] for item in dirs["items"])

    client.delete("/api/files", params={"path": "/pytest-search", "recursive": True})


def test_file_path_escape_is_denied(client: TestClient) -> None:
    response = client.get("/api/files/list", params={"path": "/../../etc"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "denied"


def test_binary_file_is_read_only(client: TestClient) -> None:
    client.post("/api/files/mkdir", json={"path": "/pytest-bin"})
    write = client.put(
        "/api/files/write",
        json={"path": "/pytest-bin/raw.txt", "content": "plain"},
    )
    assert write.status_code == 200

    from app.core.config import settings

    (__import__("pathlib").Path(settings.file_root) / "pytest-bin" / "raw.bin").write_bytes(
        b"\x00\x01\x02binary"
    )
    payload = client.get("/api/files/read", params={"path": "/pytest-bin/raw.bin"}).json()
    assert payload["binary"] is True
    assert payload["editable"] is False
    assert payload["content"] == ""

    client.delete("/api/files", params={"path": "/pytest-bin", "recursive": True})
