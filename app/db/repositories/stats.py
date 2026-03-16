from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import String, case, desc, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PeriodType
from app.db.models import ChatMessage, ServerSnapshot, Session, TS3Client


class StatsRepository:
    def _period_start(self, period: PeriodType) -> datetime | None:
        now = datetime.now(timezone.utc)
        if period == PeriodType.DAY:
            return now - timedelta(days=1)
        if period == PeriodType.WEEK:
            return now - timedelta(days=7)
        if period == PeriodType.MONTH:
            return now - timedelta(days=30)
        return None

    async def top_users_by_time(
        self,
        session: AsyncSession,
        period: PeriodType,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        start = self._period_start(period)
        duration_expr = func.coalesce(
            Session.duration_seconds,
            func.extract("epoch", func.now() - Session.started_at),
        )
        stmt = (
            select(TS3Client.nickname, func.sum(duration_expr).label("seconds"))
            .join(Session, Session.ts3_client_id == TS3Client.id)
            .group_by(TS3Client.nickname)
            .order_by(desc("seconds"))
            .limit(limit)
        )
        if start:
            stmt = stmt.where(Session.started_at >= start)
        result = await session.execute(stmt)
        return [(nickname, int(seconds or 0)) for nickname, seconds in result.all()]

    async def top_users_by_joins(
        self,
        session: AsyncSession,
        period: PeriodType,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        start = self._period_start(period)
        stmt = (
            select(TS3Client.nickname, func.count(Session.id).label("joins"))
            .join(Session, Session.ts3_client_id == TS3Client.id)
            .group_by(TS3Client.nickname)
            .order_by(desc("joins"))
            .limit(limit)
        )
        if start:
            stmt = stmt.where(Session.started_at >= start)
        result = await session.execute(stmt)
        return [(nickname, int(joins or 0)) for nickname, joins in result.all()]

    async def average_session_duration(self, session: AsyncSession, limit: int = 20) -> list[tuple[str, float]]:
        duration_expr = func.coalesce(
            Session.duration_seconds,
            func.extract("epoch", func.now() - Session.started_at),
        )
        stmt = (
            select(TS3Client.nickname, func.avg(duration_expr).label("avg_seconds"))
            .join(Session, Session.ts3_client_id == TS3Client.id)
            .group_by(TS3Client.nickname)
            .order_by(desc("avg_seconds"))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [(nickname, float(avg_seconds or 0)) for nickname, avg_seconds in result.all()]

    async def top_channels_by_time(self, session: AsyncSession, limit: int = 10) -> list[tuple[str, int]]:
        duration_expr = func.coalesce(
            Session.duration_seconds,
            func.extract("epoch", func.now() - Session.started_at),
        )
        channel_label = case(
            (Session.channel_name.is_not(None), Session.channel_name),
            else_=func.cast(Session.channel_id, String),
        )
        stmt = (
            select(
                channel_label.label("channel"),
                func.sum(duration_expr).label("seconds"),
            )
            .group_by("channel")
            .order_by(desc("seconds"))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [(str(channel), int(seconds or 0)) for channel, seconds in result.all()]

    async def weekday_distribution(self, session: AsyncSession) -> list[tuple[int, int]]:
        stmt = (
            select(
                extract("dow", Session.started_at).label("weekday"),
                func.count(Session.id).label("cnt"),
            )
            .group_by("weekday")
            .order_by("weekday")
        )
        rows = (await session.execute(stmt)).all()
        return [(int(day), int(cnt)) for day, cnt in rows]

    async def first_last_seen(self, session: AsyncSession, limit: int = 50) -> list[tuple[str, datetime | None, datetime | None]]:
        stmt = (
            select(
                TS3Client.nickname,
                func.min(Session.started_at).label("first_seen"),
                func.max(func.coalesce(Session.ended_at, Session.started_at)).label("last_seen"),
            )
            .join(Session, Session.ts3_client_id == TS3Client.id)
            .group_by(TS3Client.nickname)
            .order_by(desc("last_seen"))
            .limit(limit)
        )
        return list((await session.execute(stmt)).all())

    async def messages_count(self, session: AsyncSession, period: PeriodType) -> list[tuple[str, int]]:
        start = self._period_start(period)
        stmt = (
            select(ChatMessage.invoker_name, func.count(ChatMessage.id).label("cnt"))
            .group_by(ChatMessage.invoker_name)
            .order_by(desc("cnt"))
            .limit(30)
        )
        if start:
            stmt = stmt.where(ChatMessage.occurred_at >= start)
        rows = (await session.execute(stmt)).all()
        return [(name, int(cnt)) for name, cnt in rows]

    async def total_server_time(self, session: AsyncSession) -> int:
        duration_expr = func.coalesce(
            Session.duration_seconds,
            func.extract("epoch", func.now() - Session.started_at),
        )
        stmt = select(func.sum(duration_expr))
        return int((await session.execute(stmt)).scalar_one() or 0)

    async def peak_hours(self, session: AsyncSession, period: PeriodType) -> list[tuple[int, int]]:
        start = self._period_start(period)
        stmt = (
            select(extract("hour", Session.started_at).label("hour"), func.count(Session.id).label("cnt"))
            .group_by("hour")
            .order_by("hour")
        )
        if start:
            stmt = stmt.where(Session.started_at >= start)
        rows = (await session.execute(stmt)).all()
        return [(int(hour), int(cnt)) for hour, cnt in rows]

    async def average_online_per_hour(self, session: AsyncSession) -> list[tuple[int, float]]:
        stmt = (
            select(extract("hour", ServerSnapshot.captured_at).label("hour"), func.avg(ServerSnapshot.total_online).label("avg"))
            .group_by("hour")
            .order_by("hour")
        )
        rows = (await session.execute(stmt)).all()
        return [(int(hour), float(avg or 0.0)) for hour, avg in rows]

    async def longest_sessions(self, session: AsyncSession, limit: int = 10) -> list[tuple[str, int, datetime]]:
        duration_expr = func.coalesce(
            Session.duration_seconds,
            func.extract("epoch", func.now() - Session.started_at),
        )
        stmt = (
            select(TS3Client.nickname, duration_expr.label("seconds"), Session.started_at)
            .join(Session, Session.ts3_client_id == TS3Client.id)
            .order_by(desc("seconds"))
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return [(name, int(seconds or 0), started_at) for name, seconds, started_at in rows]

    async def talkative_ratio(self, session: AsyncSession) -> list[tuple[str, float, int, int]]:
        duration_expr = func.coalesce(Session.duration_seconds, 0)
        voice_subq = (
            select(Session.ts3_client_id.label("client_id"), func.sum(duration_expr).label("voice_seconds"))
            .group_by(Session.ts3_client_id)
            .subquery()
        )
        msg_subq = (
            select(ChatMessage.ts3_client_id.label("client_id"), func.count(ChatMessage.id).label("msg_count"))
            .where(ChatMessage.ts3_client_id.is_not(None))
            .group_by(ChatMessage.ts3_client_id)
            .subquery()
        )

        stmt = (
            select(
                TS3Client.nickname,
                func.coalesce(voice_subq.c.voice_seconds, 0).label("voice_seconds"),
                func.coalesce(msg_subq.c.msg_count, 0).label("msg_count"),
                case(
                    (func.coalesce(msg_subq.c.msg_count, 0) == 0, func.coalesce(voice_subq.c.voice_seconds, 0)),
                    else_=func.coalesce(voice_subq.c.voice_seconds, 0) / func.coalesce(msg_subq.c.msg_count, 1),
                ).label("ratio"),
            )
            .outerjoin(voice_subq, voice_subq.c.client_id == TS3Client.id)
            .outerjoin(msg_subq, msg_subq.c.client_id == TS3Client.id)
            .order_by(desc("ratio"))
            .limit(30)
        )
        rows = (await session.execute(stmt)).all()
        return [
            (nickname, float(ratio or 0), int(voice_seconds or 0), int(msg_count or 0))
            for nickname, voice_seconds, msg_count, ratio in rows
        ]

    async def heatmap(self, session: AsyncSession) -> list[tuple[int, int, int]]:
        stmt = (
            select(
                extract("dow", Session.started_at).label("weekday"),
                extract("hour", Session.started_at).label("hour"),
                func.count(Session.id).label("cnt"),
            )
            .group_by("weekday", "hour")
            .order_by("weekday", "hour")
        )
        rows = (await session.execute(stmt)).all()
        return [(int(weekday), int(hour), int(cnt)) for weekday, hour, cnt in rows]
