from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import NotificationType, SubscriptionType
from app.core.logging import get_logger
from app.db.repositories.notifications import NotificationRepository
from app.db.repositories.users import UserRepository


class NotificationService:
    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        user_repo: UserRepository,
        notification_repo: NotificationRepository,
        redis: Redis | None,
    ) -> None:
        self._bot = bot
        self._settings = settings
        self._user_repo = user_repo
        self._notification_repo = notification_repo
        self._redis = redis
        self._log = get_logger(component="notification_service")

    async def _dedupe(self, key: str) -> bool:
        ttl = self._settings.notify_antispam_seconds
        if ttl <= 0:
            return False
        if not self._redis:
            return False
        redis_key = f"notify:dedupe:{key}"
        created = await self._redis.set(redis_key, "1", ex=ttl, nx=True)
        return created is None

    async def notify_admins(
        self,
        session: AsyncSession,
        notification_type: NotificationType,
        text: str,
        dedupe_key: str | None = None,
    ) -> None:
        if dedupe_key and await self._dedupe(dedupe_key):
            return

        admin_ids = await self._user_repo.list_admin_telegram_ids(session)
        now_dt = datetime.now(timezone.utc)
        for telegram_id in admin_ids:
            user = await self._user_repo.get_by_telegram_id(session, telegram_id)
            if not user:
                continue
            enabled = await self._notification_repo.is_notification_enabled(
                session,
                user.id,
                notification_type,
                now_dt,
            )
            if not enabled:
                continue
            await self._safe_send(telegram_id, text)

    async def notify_subscription(
        self,
        session: AsyncSession,
        target_ts3_client_id: int,
        message: str,
    ) -> None:
        subscriptions = await self._notification_repo.list_subscriptions_for_target_user(
            session,
            target_ts3_client_id,
        )
        for sub in subscriptions:
            if sub.subscription_type != SubscriptionType.USER_ONLINE:
                continue
            await self._safe_send(sub.subscriber.telegram_id, message)

    async def notify_channel_subscriptions(
        self,
        session: AsyncSession,
        channel_id: int,
        message: str,
    ) -> None:
        subscriptions = await self._notification_repo.list_subscriptions_for_channel(session, channel_id)
        for sub in subscriptions:
            await self._safe_send(sub.subscriber.telegram_id, message)

    async def subscribe_user_online(
        self,
        session: AsyncSession,
        subscriber_user_id: int,
        target_ts3_client_id: int | None,
        target_label: str | None,
    ) -> None:
        await self._notification_repo.create_subscription(
            session=session,
            subscriber_user_id=subscriber_user_id,
            subscription_type=SubscriptionType.USER_ONLINE,
            target_ts3_client_id=target_ts3_client_id,
            target_label=target_label,
            channel_id=None,
        )

    async def subscribe_channel_activity(
        self,
        session: AsyncSession,
        subscriber_user_id: int,
        channel_id: int,
        target_label: str | None = None,
    ) -> None:
        await self._notification_repo.create_subscription(
            session=session,
            subscriber_user_id=subscriber_user_id,
            subscription_type=SubscriptionType.CHANNEL_ACTIVITY,
            target_ts3_client_id=None,
            target_label=target_label,
            channel_id=channel_id,
        )

    async def list_subscriptions(self, session: AsyncSession, user_id: int):
        return await self._notification_repo.list_user_subscriptions(session, user_id)

    async def toggle_notification(
        self,
        session: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
        enabled: bool,
    ) -> None:
        await self._notification_repo.set_enabled(
            session=session,
            user_id=user_id,
            notification_type=notification_type,
            enabled=enabled,
        )

    async def is_enabled(
        self,
        session: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
    ) -> bool:
        setting = await self._notification_repo.get_or_create_setting(session, user_id, notification_type)
        return bool(setting.enabled)

    async def _safe_send(self, telegram_id: int, text: str) -> None:
        try:
            await self._bot.send_message(telegram_id, text)
        except TelegramAPIError as exc:
            self._log.warning("telegram_send_failed", telegram_id=telegram_id, error=str(exc))
