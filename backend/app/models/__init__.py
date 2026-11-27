"""Model registry — importing this module registers every mapper."""

from app.models.audit import AuditLog
from app.models.card import ServiceCard
from app.models.host import Host


def load_models() -> None:
    """Touch imported classes so SQLAlchemy registers all mappers."""
    _ = (AuditLog, ServiceCard, Host)


__all__ = ["AuditLog", "Host", "ServiceCard", "load_models"]
