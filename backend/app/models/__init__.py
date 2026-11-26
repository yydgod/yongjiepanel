"""Model registry — importing this module registers every mapper."""

from app.models.audit import AuditLog
from app.models.card import Agent, ServiceCard
from app.models.chat import ChatMessage, ChatSession, PendingAction
from app.models.host import Host
from app.models.provider import Provider


def load_models() -> None:
    """Touch imported classes so SQLAlchemy registers all mappers."""
    _ = (AuditLog, Agent, ServiceCard, ChatMessage, ChatSession, PendingAction, Host, Provider)


__all__ = [
    "Agent",
    "AuditLog",
    "ChatMessage",
    "ChatSession",
    "Host",
    "PendingAction",
    "Provider",
    "ServiceCard",
    "load_models",
]
