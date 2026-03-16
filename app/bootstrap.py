from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.bot.factory import create_bot, create_dispatcher
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limiter import RateLimiter
from app.db.repositories import (
    AdminRepository,
    NotificationRepository,
    StatsRepository,
    TS3Repository,
    TTSRepository,
    UserRepository,
)
from app.db.session import create_engine, create_session_factory
from app.services.audit_service import AuditService
from app.services.container import ServiceContainer
from app.services.notification_service import NotificationService
from app.services.permission_service import PermissionService
from app.services.runtime_config_service import RuntimeConfigService
from app.services.stats_service import StatsService
from app.services.teamspeak.adapter import TeamSpeakServerQueryAdapter
from app.services.teamspeak.service import TeamSpeakService
from app.services.tts.providers import GTTSProvider
from app.services.tts.service import TTSService
from app.services.user_service import UserService
from app.services.voice.service import VoiceService, build_voice_adapter
from app.workers import ReportsWorker, TS3MonitorWorker, TTSWorker


@dataclass(slots=True)
class AppContext:
    settings: Settings
    bot: Bot
    dp: Dispatcher
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis | None
    services: ServiceContainer
    ts3_monitor: TS3MonitorWorker
    tts_worker: TTSWorker
    reports_worker: ReportsWorker


async def create_app_context() -> AppContext:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger(component="bootstrap")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    redis: Redis | None = None
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=False)
        await redis.ping()
    except Exception as exc:  # noqa: BLE001
        log.warning("redis_unavailable_using_fallback", error=str(exc))
        redis = None

    user_repo = UserRepository()
    notification_repo = NotificationRepository()
    ts3_repo = TS3Repository()
    stats_repo = StatsRepository()
    tts_repo = TTSRepository()
    admin_repo = AdminRepository()

    bot = create_bot(settings)

    permission = PermissionService(settings=settings, user_repo=user_repo)
    users = UserService(user_repo=user_repo, permission=permission)

    runtime = RuntimeConfigService(redis=redis, chatwatch_default=settings.chatwatch_enabled_by_default)

    notifications = NotificationService(
        bot=bot,
        settings=settings,
        user_repo=user_repo,
        notification_repo=notification_repo,
        redis=redis,
    )

    ts3_adapter = TeamSpeakServerQueryAdapter(settings)
    teamspeak = TeamSpeakService(
        settings=settings,
        adapter=ts3_adapter,
        ts3_repo=ts3_repo,
        notification_repo=notification_repo,
        notification_service=notifications,
        runtime_config=runtime,
    )

    stats = StatsService(stats_repo)

    tts_provider = GTTSProvider(language=settings.tts_language)
    tts_service = TTSService(settings=settings, repo=tts_repo, provider=tts_provider)

    voice_adapter = build_voice_adapter(settings)
    voice_service = VoiceService(voice_adapter)

    audit = AuditService(admin_repo)

    rate_limiter = RateLimiter(redis)

    services = ServiceContainer(
        audit=audit,
        permission=permission,
        users=users,
        notifications=notifications,
        teamspeak=teamspeak,
        stats=stats,
        tts=tts_service,
        voice=voice_service,
        runtime=runtime,
        rate_limiter=rate_limiter,
    )

    dp = create_dispatcher(
        settings=settings,
        services=services,
        session_factory=session_factory,
        redis=redis,
    )

    ts3_monitor = TS3MonitorWorker(settings=settings, session_factory=session_factory, teamspeak_service=teamspeak)
    tts_worker = TTSWorker(
        session_factory=session_factory,
        tts_service=tts_service,
        voice_service=voice_service,
        notifications=notifications,
    )
    reports_worker = ReportsWorker(
        settings=settings,
        session_factory=session_factory,
        stats_service=stats,
        notifications=notifications,
    )

    return AppContext(
        settings=settings,
        bot=bot,
        dp=dp,
        engine=engine,
        session_factory=session_factory,
        redis=redis,
        services=services,
        ts3_monitor=ts3_monitor,
        tts_worker=tts_worker,
        reports_worker=reports_worker,
    )
