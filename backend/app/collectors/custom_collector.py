"""Custom cards have no automatic telemetry — they always report 'unknown'."""

from __future__ import annotations

from app.collectors.base import BaseCollector, Snapshot


class CustomCollector(BaseCollector):
    kind = "custom"
    label = "自定义卡片"

    def available(self) -> tuple[bool, str | None]:
        return True, None

    async def collect(self, targets: list[str]) -> dict[str, Snapshot]:
        return {
            target: Snapshot(
                target=target,
                status="unknown",
                detail="自定义卡片：由人工维护状态，可在 dsh 工作区中继续处理",
                collector=self.kind,
            )
            for target in targets
        }
