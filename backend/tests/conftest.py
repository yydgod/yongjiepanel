"""Test bootstrap: isolated DB and all collectors disabled (deterministic)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

FILES_ROOT = Path("/tmp/yongjie_files_root")
shutil.rmtree(FILES_ROOT, ignore_errors=True)
FILES_ROOT.mkdir(parents=True, exist_ok=True)

TERMINAL_HISTORY = Path("/tmp/yongjie_terminal_history.json")
TERMINAL_HISTORY.unlink(missing_ok=True)

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
        "FILE_ROOT": str(FILES_ROOT),
        # 测试不接触真实 dsh 进程，工作区注册走文件回退
        "DSH_REMOTE_WRITE": "false",
        "TERMINAL_HISTORY_FILE": str(TERMINAL_HISTORY),
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
