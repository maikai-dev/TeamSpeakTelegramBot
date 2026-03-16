from __future__ import annotations

from enum import Enum


class RoleName(str, Enum):
    ADMIN = "admin"
    USER = "user"


class Ts3EventType(str, Enum):
    JOIN = "join"
    LEAVE = "leave"
    MOVE = "move"
    MESSAGE = "message"


class ChatMessageType(str, Enum):
    SERVER = "server"
    CHANNEL = "channel"
    PRIVATE = "private"


class NotificationType(str, Enum):
    JOIN = "join"
    LEAVE = "leave"
    MOVE = "move"
    CHAT = "chat"
    SUBSCRIPTION = "subscription"
    DAILY_REPORT = "daily_report"
    WEEKLY_REPORT = "weekly_report"
    LONG_ONLINE = "long_online"
    CHANNEL_ALERT = "channel_alert"


class AdminActionType(str, Enum):
    KICK = "kick"
    BAN = "ban"
    MOVE = "move"
    MUTE = "mute"
    UNMUTE = "unmute"
    POKE = "poke"
    ASSIGN_GROUP = "assign_group"
    REMOVE_GROUP = "remove_group"
    TTS = "tts"
    CHATWATCH_TOGGLE = "chatwatch_toggle"
    RELOAD_CONFIG = "reload_config"


class SubscriptionType(str, Enum):
    USER_ONLINE = "user_online"
    CHANNEL_ACTIVITY = "channel_activity"


class TTSJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class PeriodType(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"
