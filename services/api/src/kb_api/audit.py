from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kb_api.auth import Principal
from kb_api.db import AuditRow


def audit(
    db: AsyncSession,
    principal: Principal,
    action: str,
    target: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Stage an audit row in the caller's transaction."""
    db.add(
        AuditRow(
            org_id=principal.org_id,
            actor=principal.actor,
            action=action,
            target=target,
            details=details or {},
        )
    )
