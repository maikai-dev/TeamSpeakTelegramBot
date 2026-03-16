from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminActionType
from app.db.models import AdminAction


class AdminRepository:
    async def log_action(
        self,
        session: AsyncSession,
        admin_user_id: int,
        action_type: AdminActionType,
        success: bool,
        target_ts3_client_id: int | None = None,
        target_label: str | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AdminAction:
        action = AdminAction(
            admin_user_id=admin_user_id,
            action_type=action_type,
            success=success,
            target_ts3_client_id=target_ts3_client_id,
            target_label=target_label,
            reason=reason,
            payload=payload or {},
        )
        session.add(action)
        await session.flush()
        return action
