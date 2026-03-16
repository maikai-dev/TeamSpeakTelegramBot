from __future__ import annotations

from datetime import datetime

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TTSJobStatus
from app.db.models import TTSJob


class TTSRepository:
    async def create_job(
        self,
        session: AsyncSession,
        requested_by_user_id: int,
        channel_id: int,
        channel_name: str | None,
        text: str,
    ) -> TTSJob:
        job = TTSJob(
            requested_by_user_id=requested_by_user_id,
            channel_id=channel_id,
            channel_name=channel_name,
            text=text,
            status=TTSJobStatus.PENDING,
            attempt_count=0,
        )
        session.add(job)
        await session.flush()
        return job

    async def list_pending_jobs(self, session: AsyncSession, limit: int = 10) -> list[TTSJob]:
        stmt = (
            select(TTSJob)
            .where(TTSJob.status == TTSJobStatus.PENDING)
            .order_by(asc(TTSJob.created_at))
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def mark_processing(self, session: AsyncSession, job: TTSJob) -> None:
        job.status = TTSJobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.attempt_count += 1

    async def mark_done(self, session: AsyncSession, job: TTSJob, audio_path: str | None = None) -> None:
        job.status = TTSJobStatus.DONE
        job.audio_path = audio_path
        job.finished_at = datetime.utcnow()

    async def mark_failed(self, session: AsyncSession, job: TTSJob, error_message: str) -> None:
        job.status = TTSJobStatus.FAILED
        job.error_message = error_message[:1024]
        job.finished_at = datetime.utcnow()

    async def get_by_id(self, session: AsyncSession, job_id: int) -> TTSJob | None:
        stmt = select(TTSJob).where(TTSJob.id == job_id)
        return (await session.execute(stmt)).scalar_one_or_none()
