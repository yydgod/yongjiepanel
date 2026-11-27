"""Test bootstrap: isolated DB and all collectors disabled (deterministic)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.update(
    {
        "DATABASE_URL": "sqlite:////tmp/yongjie_test.db",
        "SEED_DEMO": "false",
        "DOCKER_ENABLED": "false",
        "SYSTEMD_ENABLED": "false",
        "PORT_ENABLED": "false",
        "SECRET_KEY": "test-secret-key-do-not-use-in-prod",
        "ADMIN_TOKEN": "",
        "COLLECT_INTERVAL": "3600",
    }
)
Path("/tmp/yongjie_test.db").unlink(missing_ok=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def card(client: TestClient) -> dict:
    response = client.post(
        "/api/cards",
        json={
            "title": "测试容器",
            "card_type": "container",
            "target_ref": "demo-container",
            "group_name": "测试分组",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
