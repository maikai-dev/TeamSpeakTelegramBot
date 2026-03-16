from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ChatMessageType, Ts3EventType
from app.db.models import ChannelEvent, ChatMessage, ServerSnapshot, Session, TS3Client


class TS3Repository:
    async def get_client_by_uid(self, session: AsyncSession, client_uid: str) -> TS3Client | None:
        stmt = select(TS3Client).where(TS3Client.client_uid == client_uid)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_clients_by_name(self, session: AsyncSession, name_part: str, limit: int = 10) -> list[TS3Client]:
        stmt = (
            select(TS3Client)
            .where(TS3Client.nickname.ilike(f"%{name_part}%"))
            .order_by(TS3Client.nickname.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_client(
        self,
        session: AsyncSession,
        client_uid: str,
        nickname: str,
        client_database_id: int | None,
        channel_id: int | None,
        channel_name: str | None,
    ) -> TS3Client:
        client = await self.get_client_by_uid(session, client_uid)
        if client is None:
            client = TS3Client(
                client_uid=client_uid,
                nickname=nickname,
                client_database_id=client_database_id,
                last_seen_at=datetime.utcnow(),
                last_channel_id=channel_id,
                last_channel_name=channel_name,
            )
            session.add(client)
            await session.flush()
            return client

        client.nickname = nickname
        client.client_database_id = client_database_id
        client.last_seen_at = datetime.utcnow()
        client.last_channel_id = channel_id
        client.last_channel_name = channel_name
        return client

    async def get_open_session(self, session: AsyncSession, ts3_client_id: int) -> Session | None:
        stmt = (
            select(Session)
            .where(Session.ts3_client_id == ts3_client_id, Session.ended_at.is_(None))
            .order_by(Session.started_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def start_session(
        self,
        session: AsyncSession,
        ts3_client_id: int,
        channel_id: int,
        channel_name: str | None,
        started_at: datetime,
    ) -> Session:
        db_session = Session(
            ts3_client_id=ts3_client_id,
            channel_id=channel_id,
            channel_name=channel_name,
            started_at=started_at,
        )
        session.add(db_session)
        await session.flush()
        return db_session

    async def close_open_session(self, session: AsyncSession, ts3_client_id: int, ended_at: datetime) -> Session | None:
        open_session = await self.get_open_session(session, ts3_client_id)
        if not open_session:
            return None
        open_session.ended_at = ended_at
        open_session.duration_seconds = max(0, int((ended_at - open_session.started_at).total_seconds()))
        return open_session

    async def close_stale_sessions(self, session: AsyncSession, alive_client_ids: Sequence[int], ended_at: datetime) -> int:
        stmt = select(Session).where(Session.ended_at.is_(None))
        if alive_client_ids:
            stmt = stmt.where(~Session.ts3_client_id.in_(alive_client_ids))
        stale = (await session.execute(stmt)).scalars().all()
        for item in stale:
            item.ended_at = ended_at
            item.duration_seconds = max(0, int((ended_at - item.started_at).total_seconds()))
        return len(stale)

    async def add_channel_event(
        self,
        session: AsyncSession,
        ts3_client_id: int | None,
        event_type: Ts3EventType,
        occurred_at: datetime,
        from_channel_id: int | None = None,
        from_channel_name: str | None = None,
        to_channel_id: int | None = None,
        to_channel_name: str | None = None,
    ) -> ChannelEvent:
        event = ChannelEvent(
            ts3_client_id=ts3_client_id,
            event_type=event_type,
            from_channel_id=from_channel_id,
            from_channel_name=from_channel_name,
            to_channel_id=to_channel_id,
            to_channel_name=to_channel_name,
            occurred_at=occurred_at,
        )
        session.add(event)
        await session.flush()
        return event

    async def add_chat_message(
        self,
        session: AsyncSession,
        ts3_client_id: int | None,
        message_type: ChatMessageType,
        channel_id: int | None,
        channel_name: str | None,
        invoker_name: str,
        message_text: str,
        occurred_at: datetime,
        is_bot_message: bool,
    ) -> ChatMessage:
        msg = ChatMessage(
            ts3_client_id=ts3_client_id,
            message_type=message_type,
            channel_id=channel_id,
            channel_name=channel_name,
            invoker_name=invoker_name,
            message_text=message_text,
            occurred_at=occurred_at,
            is_bot_message=is_bot_message,
        )
        session.add(msg)
        await session.flush()
        return msg

    async def add_server_snapshot(
        self,
        session: AsyncSession,
        captured_at: datetime,
        total_online: int,
        payload: dict,
    ) -> ServerSnapshot:
        snapshot = ServerSnapshot(
            captured_at=captured_at,
            total_online=total_online,
            payload=payload,
        )
        session.add(snapshot)
        await session.flush()
        return snapshot

    async def find_last_seen(self, session: AsyncSession, name_part: str) -> TS3Client | None:
        stmt = (
            select(TS3Client)
            .where(TS3Client.nickname.ilike(f"%{name_part}%"))
            .order_by(desc(TS3Client.last_seen_at))
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_current_open_sessions(self, session: AsyncSession) -> list[Session]:
        stmt = select(Session).where(Session.ended_at.is_(None))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_top_online_today(self, session: AsyncSession, limit: int = 10) -> list[tuple[str, int]]:
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        duration_expr = func.coalesce(
            Session.duration_seconds,
            func.extract("epoch", func.now() - Session.started_at),
        )
        stmt = (
            select(TS3Client.nickname, func.sum(duration_expr).label("seconds"))
            .join(Session, Session.ts3_client_id == TS3Client.id)
            .where(Session.started_at >= day_start)
            .group_by(TS3Client.nickname)
            .order_by(desc("seconds"))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [(name, int(seconds or 0)) for name, seconds in result.all()]

    async def get_messages_today_by_user(self, session: AsyncSession, ts3_client_id: int) -> int:
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count(ChatMessage.id)).where(
            ChatMessage.ts3_client_id == ts3_client_id,
            ChatMessage.occurred_at >= day_start,
        )
        return int((await session.execute(stmt)).scalar_one() or 0)

    async def list_active_sessions_over_hours(self, session: AsyncSession, hours: int) -> list[Session]:
        threshold = datetime.utcnow().timestamp() - (hours * 3600)
        stmt = select(Session).where(
            and_(
                Session.ended_at.is_(None),
                func.extract("epoch", Session.started_at) <= threshold,
            )
        )
        return list((await session.execute(stmt)).scalars().all())

    async def relink_client_to_user(self, session: AsyncSession, client_uid: str, user_id: int) -> None:
        stmt = (
            update(TS3Client)
            .where(TS3Client.client_uid == client_uid)
            .values(telegram_user_id=user_id)
        )
        await session.execute(stmt)
