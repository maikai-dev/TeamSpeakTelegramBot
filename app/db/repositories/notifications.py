from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import NotificationType, SubscriptionType
from app.db.models import NotificationSetting, Subscription


class NotificationRepository:
    async def get_or_create_setting(
        self,
        session: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
    ) -> NotificationSetting:
        stmt = select(NotificationSetting).where(
            NotificationSetting.user_id == user_id,
            NotificationSetting.notification_type == notification_type,
        )
        setting = (await session.execute(stmt)).scalar_one_or_none()
        if setting:
            return setting
        setting = NotificationSetting(user_id=user_id, notification_type=notification_type, enabled=True)
        session.add(setting)
        await session.flush()
        return setting

    async def set_enabled(
        self,
        session: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
        enabled: bool,
    ) -> NotificationSetting:
        setting = await self.get_or_create_setting(session, user_id, notification_type)
        setting.enabled = enabled
        return setting

    async def list_settings_for_user(self, session: AsyncSession, user_id: int) -> list[NotificationSetting]:
        stmt = select(NotificationSetting).where(NotificationSetting.user_id == user_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def is_notification_enabled(
        self,
        session: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
        now_dt: datetime,
    ) -> bool:
        setting = await self.get_or_create_setting(session, user_id, notification_type)
        if not setting.enabled:
            return False
        if setting.mute_until and setting.mute_until > now_dt:
            return False
        if setting.quiet_hours_start is not None and setting.quiet_hours_end is not None:
            hour = now_dt.hour
            start = setting.quiet_hours_start
            end = setting.quiet_hours_end
            if start < end and start <= hour < end:
                return False
            if start > end and (hour >= start or hour < end):
                return False
        return True

    async def create_subscription(
        self,
        session: AsyncSession,
        subscriber_user_id: int,
        subscription_type: SubscriptionType,
        target_ts3_client_id: int | None,
        target_label: str | None,
        channel_id: int | None,
    ) -> Subscription:
        if subscription_type == SubscriptionType.USER_ONLINE and target_ts3_client_id is None:
            raise ValueError("target_ts3_client_id обязателен для USER_ONLINE")
        if subscription_type == SubscriptionType.CHANNEL_ACTIVITY and channel_id is None:
            raise ValueError("channel_id обязателен для CHANNEL_ACTIVITY")

        stmt = select(Subscription).where(
            Subscription.subscriber_user_id == subscriber_user_id,
            Subscription.subscription_type == subscription_type,
            Subscription.target_ts3_client_id == target_ts3_client_id,
            Subscription.channel_id == channel_id,
            Subscription.target_label == target_label,
            Subscription.is_active.is_(True),
        )
        exists = (await session.execute(stmt)).scalar_one_or_none()
        if exists:
            return exists
        sub = Subscription(
            subscriber_user_id=subscriber_user_id,
            subscription_type=subscription_type,
            target_ts3_client_id=target_ts3_client_id,
            target_label=target_label,
            channel_id=channel_id,
            is_active=True,
        )
        session.add(sub)
        await session.flush()
        return sub

    async def list_subscriptions_for_target_user(
        self,
        session: AsyncSession,
        target_ts3_client_id: int,
    ) -> list[Subscription]:
        stmt = select(Subscription).where(
            Subscription.subscription_type == SubscriptionType.USER_ONLINE,
            Subscription.target_ts3_client_id == target_ts3_client_id,
            Subscription.is_active.is_(True),
        )
        return list((await session.execute(stmt)).scalars().all())

    async def list_subscriptions_for_channel(
        self,
        session: AsyncSession,
        channel_id: int,
    ) -> list[Subscription]:
        stmt = select(Subscription).where(
            Subscription.subscription_type == SubscriptionType.CHANNEL_ACTIVITY,
            Subscription.channel_id == channel_id,
            Subscription.is_active.is_(True),
        )
        return list((await session.execute(stmt)).scalars().all())

    async def list_user_subscriptions(self, session: AsyncSession, user_id: int) -> list[Subscription]:
        stmt = select(Subscription).where(
            Subscription.subscriber_user_id == user_id,
            Subscription.is_active.is_(True),
        )
        return list((await session.execute(stmt)).scalars().all())
