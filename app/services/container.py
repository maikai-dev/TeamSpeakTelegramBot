from __future__ import annotations

from dataclasses import dataclass

from app.core.rate_limiter import RateLimiter
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.permission_service import PermissionService
from app.services.runtime_config_service import RuntimeConfigService
from app.services.stats_service import StatsService
from app.services.teamspeak.service import TeamSpeakService
from app.services.tts.service import TTSService
from app.services.user_service import UserService
from app.services.voice.service import VoiceService


@dataclass(slots=True)
class ServiceContainer:
    audit: AuditService
    permission: PermissionService
    users: UserService
    notifications: NotificationService
    teamspeak: TeamSpeakService
    stats: StatsService
    tts: TTSService
    voice: VoiceService
    runtime: RuntimeConfigService
    rate_limiter: RateLimiter
