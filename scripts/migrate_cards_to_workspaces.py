#!/usr/bin/env python3
"""把「永杰面板」已有卡片迁移为 dsh 工作区。

用法（先停止 dsh，避免注册表并发写）：
    python3 scripts/migrate_cards_to_workspaces.py \
        --api http://127.0.0.1:8000/api \
        --workspaces /data/workspaces \
        --dsh-home ~/.dsh

行为：
- 读取 /api/cards 的卡片清单；
- 为每张卡片创建 <workspaces>/<card-id> 目录（已存在则复用）；
- 在 $DSH_HOME/storages/workspace.json 中按 path 幂等注册工作区（标题=卡片标题）；
- 写入 $DSH_HOME/storages/yongjie-cards.json 供后续卡片网格插件读取；
- 修改注册表前自动备份为 workspace.json.bak-<timestamp>。
"""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


def fetch_cards(api: str) -> list[dict]:
    with urllib.request.urlopen(f"{api.rstrip('/')}/cards", timeout=30) as response:
        return json.load(response)["items"]


def main() -> None:
    parser = argparse.ArgumentParser(description="卡片 → dsh 工作区迁移")
    parser.add_argument("--api", default="http://127.0.0.1:8000/api")
    parser.add_argument("--workspaces", default="/data/workspaces")
    parser.add_argument("--dsh-home", default=str(Path.home() / ".dsh"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cards = fetch_cards(args.api)
    storage = Path(args.dsh_home).expanduser() / "storages" / "workspace.json"
    cards_store = storage.with_name("yongjie-cards.json")
    root = Path(args.workspaces)

    data = json.loads(storage.read_text())
    table = data.setdefault("tables", {}).setdefault("workspaces", {})
    ids = data.setdefault("global", {}).setdefault("workspaceIds", [])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    migrated = []
    for card in cards:
        path = root / card["id"]
        existing = next((wid for wid, item in table.items() if item.get("path") == str(path)), None)
        workspace_id = existing or str(uuid.uuid4())
        if not existing:
            table[workspace_id] = {
                "path": str(path),
                "title": card["title"],
                "sessionIds": [],
                "createdAt": now,
                "updatedAt": now,
            }
            ids.append(workspace_id)
        migrated.append(
            {
                "card_id": card["id"],
                "workspace_id": workspace_id,
                "path": str(path),
                "title": card["title"],
                "icon": card.get("icon"),
                "accent": card.get("accent"),
                "group": card.get("group_name"),
                "card_type": card.get("card_type"),
                "target_ref": card.get("target_ref"),
            }
        )
        print(f"{'[dry-run] ' if args.dry_run else ''}{card['title']} -> {workspace_id} ({path})")

    if args.dry_run:
        return

    backup = storage.with_name(f"workspace.json.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(storage, backup)
    for item in migrated:
        Path(item["path"]).mkdir(parents=True, exist_ok=True)
    storage.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    cards_store.write_text(
        json.dumps(
            {"unit": {"name": "yongjie-cards", "version": 1}, "cards": migrated},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"backup: {backup}")
    print(f"workspaces: {len(ids)} | cards store: {cards_store}")


if __name__ == "__main__":
    main()
