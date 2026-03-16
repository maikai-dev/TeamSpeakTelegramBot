from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.enums import NotificationType, PeriodType
from app.core.logging import get_logger
from app.services.notification_service import NotificationService
from app.services.stats_service import StatsService


class ReportsWorker:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        stats_service: StatsService,
        notifications: NotificationService,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._stats = stats_service
        self._notifications = notifications
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._log = get_logger(component="reports_worker")

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="reports-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        last_daily_sent: str | None = None
        last_weekly_sent: str | None = None

        while not self._stop_event.is_set():
            now = datetime.now()
            date_key = now.strftime("%Y-%m-%d")
            week_key = now.strftime("%Y-%W")

            try:
                async with self._session_factory() as session:
                    if now.hour == self._settings.daily_report_hour_msk and date_key != last_daily_sent:
                        summary = await self._stats.server_stats_full(session, period=PeriodType.DAY)
                        await self._notifications.notify_admins(
                            session,
                            notification_type=NotificationType.DAILY_REPORT,
                            text=f"📬 Ежедневный отчет\n{summary}",
                            dedupe_key=f"daily_report:{date_key}",
                        )
                        last_daily_sent = date_key

                    if (
                        now.weekday() == self._settings.weekly_report_weekday
                        and now.hour == self._settings.daily_report_hour_msk
                        and week_key != last_weekly_sent
                    ):
                        summary = await self._stats.server_stats_full(session, period=PeriodType.WEEK)
                        await self._notifications.notify_admins(
                            session,
                            notification_type=NotificationType.WEEKLY_REPORT,
                            text=f"📬 Еженедельный отчет\n{summary}",
                            dedupe_key=f"weekly_report:{week_key}",
                        )
                        last_weekly_sent = week_key

                    await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._log.warning("reports_cycle_failed", error=str(exc))

            await asyncio.sleep(60)
