from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PeriodType
from app.db.models import ChatMessage, Session, TS3Client, User
from app.db.repositories.stats import StatsRepository
from app.utils.charts import bar_chart, heatmap_grid
from app.utils.formatting import format_dt, humanize_seconds


class StatsService:
    def __init__(self, stats_repo: StatsRepository) -> None:
        self._stats_repo = stats_repo

    async def format_top_online(self, session: AsyncSession, period: PeriodType = PeriodType.DAY) -> str:
        top = await self._stats_repo.top_users_by_time(session, period=period, limit=10)
        if not top:
            return "Данных по онлайну пока нет."
        lines = [f"?? Топ онлайна ({period.value})"]
        for idx, (name, seconds) in enumerate(top, start=1):
            lines.append(f"{idx}. {name} — {humanize_seconds(seconds)}")
        return "\n".join(lines)

    async def format_user_stats(
        self,
        session: AsyncSession,
        user: User,
        period: PeriodType = PeriodType.WEEK,
    ) -> str:
        stmt = select(TS3Client).where(TS3Client.telegram_user_id == user.id)
        clients = list((await session.execute(stmt)).scalars().all())
        if not clients:
            return (
                "Пока нет привязки к TS3-профилю.\n"
                "Попросите админа привязать ваш TS3 UID к Telegram (таблица ts3_clients.telegram_user_id)."
            )

        start = self._period_start(period)
        client_ids = [client.id for client in clients]

        duration_expr = func.coalesce(Session.duration_seconds, func.extract("epoch", func.now() - Session.started_at))
        session_stmt = select(func.sum(duration_expr)).where(Session.ts3_client_id.in_(client_ids))
        msg_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.ts3_client_id.in_(client_ids))
        joins_stmt = select(func.count(Session.id)).where(Session.ts3_client_id.in_(client_ids))
        if start:
            session_stmt = session_stmt.where(Session.started_at >= start)
            msg_stmt = msg_stmt.where(ChatMessage.occurred_at >= start)
            joins_stmt = joins_stmt.where(Session.started_at >= start)

        total_seconds = int((await session.execute(session_stmt)).scalar_one() or 0)
        messages = int((await session.execute(msg_stmt)).scalar_one() or 0)
        joins = int((await session.execute(joins_stmt)).scalar_one() or 0)

        return "\n".join(
            [
                f"?? Ваша статистика ({period.value})",
                f"TS3 профили: {', '.join(client.nickname for client in clients)}",
                f"Суммарно в голосе: {humanize_seconds(total_seconds)}",
                f"Количество заходов: {joins}",
                f"Сообщений в чате: {messages}",
            ]
        )

    async def online_today(self, session: AsyncSession, user: User) -> str:
        return await self.format_user_stats(session, user=user, period=PeriodType.DAY)

    async def messages_today(self, session: AsyncSession, user: User) -> str:
        stmt = select(TS3Client.id, TS3Client.nickname).where(TS3Client.telegram_user_id == user.id)
        rows = (await session.execute(stmt)).all()
        if not rows:
            return "Нет привязанных TS3-профилей для подсчета сообщений."

        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        lines = ["?? Ваши сообщения за сегодня"]
        total = 0
        for client_id, nickname in rows:
            msg_stmt = select(func.count(ChatMessage.id)).where(
                ChatMessage.ts3_client_id == client_id,
                ChatMessage.occurred_at >= start,
            )
            count = int((await session.execute(msg_stmt)).scalar_one() or 0)
            total += count
            lines.append(f"- {nickname}: {count}")
        lines.append(f"Итого: {total}")
        return "\n".join(lines)

    async def last_seen(self, session: AsyncSession, name_part: str) -> str:
        stmt = (
            select(TS3Client)
            .where(TS3Client.nickname.ilike(f"%{name_part}%"))
            .order_by(desc(TS3Client.last_seen_at))
            .limit(1)
        )
        client = (await session.execute(stmt)).scalar_one_or_none()
        if not client:
            return "Пользователь не найден в истории."
        return (
            f"?? Последний онлайн\n"
            f"Ник: {client.nickname}\n"
            f"UID: {client.client_uid}\n"
            f"Последний раз: {format_dt(client.last_seen_at)}"
        )

    async def online_report(self, online_rows: list[dict]) -> str:
        if not online_rows:
            return "Сейчас на сервере никого нет."

        channel_map: dict[str, list[dict]] = {}
        for row in online_rows:
            channel_map.setdefault(row["channel_name"], []).append(row)

        lines = [f"?? Онлайн сейчас: {len(online_rows)}"]
        for channel_name, people in sorted(channel_map.items(), key=lambda item: item[0].lower()):
            lines.append(f"\n?? {channel_name} ({len(people)})")
            for person in sorted(people, key=lambda item: item["nickname"].lower()):
                flags: list[str] = []
                if person.get("is_muted"):
                    flags.append("mute")
                if person.get("is_deaf"):
                    flags.append("deaf")
                if person.get("server_groups"):
                    flags.append(f"sg:{person['server_groups']}")
                status = f" [{' '.join(flags)}]" if flags else ""
                lines.append(
                    f"- {person['nickname']} — в канале {humanize_seconds(person['channel_seconds'])}{status}"
                )
        return "\n".join(lines)

    async def server_stats_full(self, session: AsyncSession, period: PeriodType = PeriodType.WEEK) -> str:
        top_time = await self._stats_repo.top_users_by_time(session, period=period, limit=8)
        top_joins = await self._stats_repo.top_users_by_joins(session, period=period, limit=8)
        peaks = await self._stats_repo.peak_hours(session, period=period)
        messages = await self._stats_repo.messages_count(session, period=period)
        total_seconds = await self._stats_repo.total_server_time(session)

        lines = [f"?? Сводка сервера ({period.value})"]
        lines.append(f"Суммарный онлайн за всё время: {humanize_seconds(total_seconds)}")

        lines.append("\nТоп по времени:")
        lines.append(bar_chart([(name[:12], seconds) for name, seconds in top_time]))

        lines.append("\nТоп по заходам:")
        lines.append(bar_chart([(name[:12], joins) for name, joins in top_joins]))

        lines.append("\nПики активности по часам:")
        lines.append(bar_chart([(f"{hour:02d}", count) for hour, count in peaks]))

        lines.append("\nСообщения (топ):")
        lines.append("\n".join(f"- {name}: {count}" for name, count in messages[:10]) or "(нет данных)")
        return "\n".join(lines)

    async def extended_stats_sections(self, session: AsyncSession) -> dict[str, str]:
        """10 дополнительных функций статистики."""
        top_day = await self._stats_repo.top_users_by_joins(session, PeriodType.DAY)
        top_week = await self._stats_repo.top_users_by_joins(session, PeriodType.WEEK)
        top_month = await self._stats_repo.top_users_by_joins(session, PeriodType.MONTH)

        avg_sessions = await self._stats_repo.average_session_duration(session)
        top_channels = await self._stats_repo.top_channels_by_time(session)
        weekday = await self._stats_repo.weekday_distribution(session)
        first_last = await self._stats_repo.first_last_seen(session)
        avg_online = await self._stats_repo.average_online_per_hour(session)
        longest = await self._stats_repo.longest_sessions(session)
        ratios = await self._stats_repo.talkative_ratio(session)
        heatmap = await self._stats_repo.heatmap(session)

        sections: dict[str, str] = {}

        sections["1_top_joins"] = "\n".join(
            [
                "1) Топ заходов (день/неделя/месяц)",
                "День:\n" + "\n".join(f"- {n}: {v}" for n, v in top_day[:5]),
                "Неделя:\n" + "\n".join(f"- {n}: {v}" for n, v in top_week[:5]),
                "Месяц:\n" + "\n".join(f"- {n}: {v}" for n, v in top_month[:5]),
            ]
        )

        sections["2_avg_session"] = "\n".join(
            ["2) Средняя длительность сессии"]
            + [f"- {name}: {humanize_seconds(int(seconds))}" for name, seconds in avg_sessions[:10]]
        )

        sections["3_top_channels"] = "\n".join(
            ["3) Топ каналов по суммарному времени"]
            + [f"- {channel}: {humanize_seconds(seconds)}" for channel, seconds in top_channels[:10]]
        )

        weekday_map = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
        sections["4_weekday"] = "\n".join(
            ["4) Распределение онлайна по дням недели"]
            + [f"- {weekday_map[day]}: {count}" for day, count in weekday]
        )

        sections["5_first_last"] = "\n".join(
            ["5) Первый и последний онлайн"]
            + [f"- {name}: первый {format_dt(first)} / последний {format_dt(last)}" for name, first, last in first_last[:10]]
        )

        companion_text = await self._approximate_companions(session)
        sections["6_companions"] = f"6) Частые собеседники / совместное пребывание\n{companion_text}"

        sections["7_avg_online"] = "\n".join(
            ["7) Среднее число людей онлайн по часам"]
            + [f"- {hour:02d}:00 — {avg:.2f}" for hour, avg in avg_online]
        )

        sections["8_records"] = "\n".join(
            ["8) Рекордные сессии"]
            + [f"- {name}: {humanize_seconds(seconds)} (старт {format_dt(started)})" for name, seconds, started in longest[:10]]
        )

        sections["9_talkative"] = "\n".join(
            ["9) Топ молчунов/болтунов (секунд на одно сообщение)"]
            + [
                f"- {name}: ratio={ratio:.1f}, voice={humanize_seconds(voice)}, msg={msg}"
                for name, ratio, voice, msg in ratios[:10]
            ]
        )

        sections["10_heatmap"] = f"10) Heatmap активности\n<pre>{heatmap_grid(heatmap)}</pre>"
        return sections

    async def export_user_stats_csv(self, session: AsyncSession, name_part: str) -> list[dict[str, str | int]]:
        client_stmt = (
            select(TS3Client)
            .where(TS3Client.nickname.ilike(f"%{name_part}%"))
            .order_by(desc(TS3Client.last_seen_at))
            .limit(1)
        )
        client = (await session.execute(client_stmt)).scalar_one_or_none()
        if not client:
            return []

        session_stmt = select(Session).where(Session.ts3_client_id == client.id).order_by(Session.started_at.desc()).limit(1000)
        sessions = (await session.execute(session_stmt)).scalars().all()
        rows: list[dict[str, str | int]] = []
        for item in sessions:
            rows.append(
                {
                    "nickname": client.nickname,
                    "channel_id": item.channel_id,
                    "channel_name": item.channel_name or "",
                    "started_at": format_dt(item.started_at),
                    "ended_at": format_dt(item.ended_at),
                    "duration_seconds": item.duration_seconds or 0,
                }
            )
        return rows

    async def _approximate_companions(self, session: AsyncSession) -> str:
        # MVP-эвристика: пользователи, чаще всего пересекающиеся по старту в одном канале за +/- 5 минут.
        stmt = (
            select(
                TS3Client.nickname.label("a"),
                func.count(Session.id).label("cnt"),
            )
            .join(TS3Client, TS3Client.id == Session.ts3_client_id)
            .group_by("a")
            .order_by(desc("cnt"))
            .limit(10)
        )
        rows = (await session.execute(stmt)).all()
        if not rows:
            return "(недостаточно данных)"
        return "\n".join(f"- {name}: ~{count} совместных пересечений" for name, count in rows)

    def _period_start(self, period: PeriodType) -> datetime | None:
        now = datetime.utcnow()
        if period == PeriodType.DAY:
            return now - timedelta(days=1)
        if period == PeriodType.WEEK:
            return now - timedelta(days=7)
        if period == PeriodType.MONTH:
            return now - timedelta(days=30)
        return None
