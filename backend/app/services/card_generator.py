"""AI card generation: structured draft from a natural-language description.

The LLM output is always re-validated and clamped to registered card types —
the model never gets to invent new tool names or break the schema.
"""

from __future__ import annotations

import re
from typing import Any

from app.ai.gateway import GatewayRequest, gateway
from app.ai.providers import ProviderConfig
from app.core.logging import get_logger
from app.schemas.generate import CardDraft, CustomizeCardResult, GenerateCardResponse
from app.services.card_types import default_display_config, get_card_type, list_card_types, tools_for

log = get_logger("ai.card_gen")

SCHEMA_HINT = """请输出 JSON 对象，字段：
{
  "title": "卡片标题，简短中文",
  "subtitle": "一句话说明，可为 null",
  "card_type": "container | systemd | port | custom 之一",
  "target_ref": "容器名 / unit 名 / 端口号 / 目标标识",
  "group_name": "分组名",
  "icon": "box | server | radio | sparkles | database | globe | shield 之一",
  "accent": "teal | violet | blue | amber 之一",
  "display_config": {"showMetrics": true, "showPorts": true, "showUptime": true},
  "system_prompt": "该卡片专属 agent 的系统提示词，中文，包含运维职责与安全约束",
  "tools": ["get_status", "get_metrics"],
  "rationale": "为什么这样设计"
}"""

_TYPE_HINTS = {
    "container": ("docker", "容器", "container", "compose", "镜像"),
    "systemd": ("systemd", "unit", "systemctl", "守护进程"),
    "port": ("端口", "port", "监听", "tcp"),
}

_ACCENTS = ("teal", "violet", "blue", "amber")
_ICONS = ("box", "server", "radio", "sparkles", "database", "globe", "shield")


def _guess_type(text: str) -> str:
    lowered = text.lower()
    for kind in ("container", "systemd", "port"):
        if any(hint in lowered for hint in _TYPE_HINTS[kind]):
            return kind
    return "custom"


def _guess_target(text: str, kind: str) -> str:
    if kind == "port":
        match = re.search(r"(\d{2,5})", text)
        return match.group(1) if match else ""
    if kind == "systemd":
        match = re.search(r"([A-Za-z0-9@._\-]+\.service)", text)
        return match.group(1) if match else ""
    match = re.search(r"[「\"'`]([A-Za-z0-9@._\-]{2,64})[」\"'`]", text)
    if match:
        return match.group(1)
    match = re.search(r"(?:名为|叫做|叫)\s*([A-Za-z0-9@._\-]{2,64})", text)
    if match:
        return match.group(1)
    return ""


def heuristic_draft(description: str) -> CardDraft:
    kind = _guess_type(description)
    target = _guess_target(description, kind)
    spec = get_card_type(kind) or {}
    title = {
        "container": "新建容器卡片",
        "systemd": "新建服务卡片",
        "port": "新建端口卡片",
        "custom": "新建自定义卡片",
    }[kind]
    if target:
        title = f"{target}"
    return CardDraft(
        title=title,
        subtitle=description.strip()[:80],
        card_type=kind,
        target_ref=target,
        group_name="AI 生成",
        icon=spec.get("icon", "sparkles"),
        accent=spec.get("accent", "teal"),
        display_config=default_display_config(kind),
        system_prompt=(
            f"你是「{title}」的专属运维 agent，负责监控 {kind} 目标「{target or '待填写'}」。"
            "先读取状态再判断，破坏性操作必须请求确认。"
        ),
        tools=tools_for(kind),
        rationale="未获得可用模型输出，按关键词生成草稿，请检查目标对象后保存。",
        channel="mock",
    )


def _clamp(draft: CardDraft) -> CardDraft:
    if get_card_type(draft.card_type) is None:
        draft.card_type = "custom"
    allowed = tools_for(draft.card_type)
    draft.tools = [tool for tool in draft.tools if tool in allowed] or allowed
    if draft.icon not in _ICONS:
        draft.icon = get_card_type(draft.card_type)["icon"]
    if draft.accent not in _ACCENTS:
        draft.accent = get_card_type(draft.card_type)["accent"]
    draft.display_config = {
        **default_display_config(draft.card_type),
        **(draft.display_config or {}),
    }
    return draft


async def generate_card(
    description: str, provider: ProviderConfig | None
) -> GenerateCardResponse:
    warnings: list[str] = []
    prompt = (
        "你是服务器看板的产品助手，需要把用户的自然语言需求转成一张服务卡片定义。\n"
        f"可用卡片类型：{[spec['kind'] for spec in list_card_types()]}。\n"
        "容器类请给出真实容器名，端口类请给出端口号，systemd 类请给出 unit 全名。\n"
        f"用户需求：{description}"
    )
    request = GatewayRequest(
        messages=[{"role": "user", "content": prompt}],
        provider=provider,
        gateway="auto",
        temperature=0.2,
        max_tokens=900,
    )
    parsed: dict[str, Any] | None = None
    channel = "mock"
    try:
        parsed, channel = await gateway.structured(request, SCHEMA_HINT)
    except Exception as exc:  # noqa: BLE001 - generation must degrade, not 500
        log.warning("AI 生成卡片失败，使用启发式草稿: %s", exc)
        warnings.append(f"模型调用失败（{type(exc).__name__}），已生成基础草稿")

    if not parsed:
        draft = heuristic_draft(description)
        if channel != "mock":
            warnings.append("模型未返回可解析 JSON，已生成基础草稿")
        return GenerateCardResponse(draft=_clamp(draft), channel=channel, warnings=warnings)

    try:
        draft = CardDraft(**{**parsed, "channel": channel})
    except Exception as exc:  # noqa: BLE001
        log.warning("草稿校验失败: %s", exc)
        warnings.append("模型输出字段不完整，已回退到关键词草稿")
        return GenerateCardResponse(
            draft=_clamp(heuristic_draft(description)), channel=channel, warnings=warnings
        )

    draft = _clamp(draft)
    draft.channel = channel
    if not draft.target_ref:
        warnings.append("目标对象为空，请在保存前填写真实容器名 / unit / 端口")
    if draft.card_type == "custom":
        warnings.append("该需求未匹配到内置类型，将创建为自定义卡片")
    return GenerateCardResponse(draft=draft, channel=channel, warnings=warnings)


def customize_card(card: Any, instruction: str) -> CustomizeCardResult:
    """Deterministic natural-language customization (no model needed)."""
    text = instruction.strip()
    accent = card.accent
    for keyword, value in (("紫", "violet"), ("蓝", "blue"), ("青", "teal"), ("琥珀", "amber"), ("黄", "amber")):
        if keyword in text:
            accent = value
            break
    icon = card.icon
    for keyword, value in (("数据库", "database"), ("网络", "globe"), ("安全", "shield"), ("服务器", "server")):
        if keyword in text:
            icon = value
            break
    group = card.group_name
    match = re.search(
        r"(?:归类到|移动到|分组改为|分组为|分组叫|分组)\s*[「\"'`]?([^\s「」\"'`，,。；;、]{1,20})",
        text,
    )
    if match:
        candidate = match.group(1).removesuffix("分组").strip()
        if candidate:
            group = candidate
    prompt = card.agent.system_prompt if card.agent else ""
    if "提示词" in text or "角色" in text:
        prompt = f"{prompt}\n\n## 追加要求\n{text}" if prompt else text
    return CustomizeCardResult(
        title=card.title,
        subtitle=card.subtitle,
        group_name=group,
        icon=icon,
        accent=accent,
        display_config=dict(card.display_config or {}),
        system_prompt=prompt,
        tools=list(card.agent.tools) if card.agent else [],
        rationale=f"已根据指令「{text[:40]}」调整卡片外观与 agent 提示词。",
        channel="local-rule",
    )
