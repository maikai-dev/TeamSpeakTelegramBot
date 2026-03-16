from __future__ import annotations

import asyncio
import contextlib

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.teamspeak.service import TeamSpeakService


class TS3MonitorWorker:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        teamspeak_service: TeamSpeakService,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._service = teamspeak_service
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._log = get_logger(component="ts3_monitor_worker")

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="ts3-monitor-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                async with self._session_factory() as session:
                    await self._service.sync_presence(session)
                    await self._service.process_chat_events(session)
                    await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._log.warning("ts3_monitor_cycle_failed", error=str(exc))

            await asyncio.sleep(self._settings.ts3_poll_interval_seconds)
