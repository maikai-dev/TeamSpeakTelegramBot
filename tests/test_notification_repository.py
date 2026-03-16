from __future__ import annotations

import pytest

from app.core.enums import SubscriptionType
from app.db.models import TS3Client, User
from app.db.repositories.notifications import NotificationRepository


@pytest.mark.asyncio
async def test_user_online_subscription_requires_target_client_id(session) -> None:
    repo = NotificationRepository()
    user = User(telegram_id=1001, username="u1", full_name="User 1", language_code="ru")
    session.add(user)
    await session.flush()

    with pytest.raises(ValueError):
        await repo.create_subscription(
            session=session,
            subscriber_user_id=user.id,
            subscription_type=SubscriptionType.USER_ONLINE,
            target_ts3_client_id=None,
            target_label="ghost",
            channel_id=None,
        )


@pytest.mark.asyncio
async def test_channel_activity_subscription_requires_channel_id(session) -> None:
    repo = NotificationRepository()
    user = User(telegram_id=1002, username="u2", full_name="User 2", language_code="ru")
    session.add(user)
    await session.flush()

    with pytest.raises(ValueError):
        await repo.create_subscription(
            session=session,
            subscriber_user_id=user.id,
            subscription_type=SubscriptionType.CHANNEL_ACTIVITY,
            target_ts3_client_id=None,
            target_label="channel-x",
            channel_id=None,
        )


@pytest.mark.asyncio
async def test_valid_user_online_subscription_created(session) -> None:
    repo = NotificationRepository()
    user = User(telegram_id=1003, username="u3", full_name="User 3", language_code="ru")
    client = TS3Client(client_uid="uid-123", nickname="Nick")
    session.add_all([user, client])
    await session.flush()

    sub = await repo.create_subscription(
        session=session,
        subscriber_user_id=user.id,
        subscription_type=SubscriptionType.USER_ONLINE,
        target_ts3_client_id=client.id,
        target_label=client.nickname,
        channel_id=None,
    )

    assert sub.id is not None
    assert sub.target_ts3_client_id == client.id
