from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import TTSJobStatus
from app.core.logging import get_logger
from app.db.models import TTSJob
from app.db.repositories.tts import TTSRepository
from app.services.tts.providers import BaseTTSProvider


class TTSService:
    def __init__(self, settings: Settings, repo: TTSRepository, provider: BaseTTSProvider) -> None:
        self._settings = settings
        self._repo = repo
        self._provider = provider
        self._log = get_logger(component="tts_service")

    async def create_job(
        self,
        session: AsyncSession,
        requested_by_user_id: int,
        channel_id: int,
        channel_name: str | None,
        text: str,
    ) -> TTSJob:
        return await self._repo.create_job(
            session=session,
            requested_by_user_id=requested_by_user_id,
            channel_id=channel_id,
            channel_name=channel_name,
            text=text,
        )

    async def list_pending_jobs(self, session: AsyncSession, limit: int = 5) -> list[TTSJob]:
        return await self._repo.list_pending_jobs(session, limit=limit)

    async def mark_processing(self, session: AsyncSession, job: TTSJob) -> None:
        await self._repo.mark_processing(session, job)

    async def mark_done(self, session: AsyncSession, job: TTSJob, audio_path: str | None) -> None:
        await self._repo.mark_done(session, job, audio_path=audio_path)

    async def mark_failed(self, session: AsyncSession, job: TTSJob, error_message: str) -> None:
        await self._repo.mark_failed(session, job, error_message=error_message)

    async def synthesize_job(self, job: TTSJob) -> Path:
        output_dir = Path(self._settings.tts_audio_dir)
        output = output_dir / f"tts_job_{job.id}.mp3"
        self._log.info("tts_synthesis_started", job_id=job.id)
        result = await self._provider.synthesize(job.text, output)
        self._log.info("tts_synthesis_done", job_id=job.id, output=str(result))
        return result
