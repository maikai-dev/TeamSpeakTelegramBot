from __future__ import annotations

import asyncio
import contextlib

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import NotificationType
from app.core.logging import get_logger
from app.services.notification_service import NotificationService
from app.services.tts.service import TTSService
from app.services.voice.service import VoiceService


class TTSWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tts_service: TTSService,
        voice_service: VoiceService,
        notifications: NotificationService,
    ) -> None:
        self._session_factory = session_factory
        self._tts = tts_service
        self._voice = voice_service
        self._notifications = notifications
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._log = get_logger(component="tts_worker")

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="tts-worker")

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
                    jobs = await self._tts.list_pending_jobs(session, limit=3)
                    if not jobs:
                        await session.commit()
                    for job in jobs:
                        await self._process_job(session, job)
                    await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._log.warning("tts_worker_cycle_failed", error=str(exc))

            await asyncio.sleep(3)

    async def _process_job(self, session: AsyncSession, job) -> None:
        await self._tts.mark_processing(session, job)
        await session.flush()
        try:
            audio_path = await self._tts.synthesize_job(job)
            await self._voice.voice_join(job.channel_id)
            await self._voice.voice_play_tts(job.channel_id, job.text, audio_path)
            await self._voice.voice_leave()
            await self._tts.mark_done(session, job, audio_path=str(audio_path))
            await self._notifications.notify_admins(
                session,
                notification_type=NotificationType.CHAT,
                text=f"🔊 TTS job #{job.id} выполнен",
                dedupe_key=f"tts:done:{job.id}",
            )
        except Exception as exc:  # noqa: BLE001
            await self._tts.mark_failed(session, job, str(exc))
            self._log.warning("tts_job_failed", job_id=job.id, error=str(exc))
