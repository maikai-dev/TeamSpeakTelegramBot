from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = Field(default="dev", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    bot_token: str = Field(alias="BOT_TOKEN")
    bot_admin_ids: list[int] = Field(default_factory=list, alias="BOT_ADMIN_IDS")
    bot_rate_limit_per_minute: int = Field(default=25, alias="BOT_RATE_LIMIT_PER_MINUTE")
    bot_sensitive_rate_limit_per_minute: int = Field(default=6, alias="BOT_SENSITIVE_RATE_LIMIT_PER_MINUTE")
    bot_max_tts_text_length: int = Field(default=280, alias="BOT_MAX_TTS_TEXT_LENGTH")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    ts3_host: str = Field(alias="TS3_HOST")
    ts3_query_port: int = Field(default=10011, alias="TS3_QUERY_PORT")
    ts3_query_login: str = Field(alias="TS3_QUERY_LOGIN")
    ts3_query_password: str = Field(alias="TS3_QUERY_PASSWORD")
    ts3_virtual_server_id: int = Field(default=1, alias="TS3_VIRTUAL_SERVER_ID")
    ts3_query_nickname: str = Field(default="tg-control-bot", alias="TS3_QUERY_NICKNAME")
    ts3_poll_interval_seconds: int = Field(default=8, alias="TS3_POLL_INTERVAL_SECONDS")
    ts3_event_queue_size: int = Field(default=2000, alias="TS3_EVENT_QUEUE_SIZE")
    ts3_channel_alert_ids: list[int] = Field(default_factory=list, alias="TS3_CHANNEL_ALERT_IDS")

    chatwatch_enabled_by_default: bool = Field(default=True, alias="CHATWATCH_ENABLED_BY_DEFAULT")
    chatwatch_allowed_types: list[str] = Field(
        default_factory=lambda: ["server", "channel", "private"],
        alias="CHATWATCH_ALLOWED_TYPES",
    )
    chatwatch_channel_whitelist: list[int] = Field(default_factory=list, alias="CHATWATCH_CHANNEL_WHITELIST")
    chatwatch_ignore_query_clients: bool = Field(default=True, alias="CHATWATCH_IGNORE_QUERY_CLIENTS")

    notify_antispam_seconds: int = Field(default=20, alias="NOTIFY_ANTISPAM_SECONDS")
    notify_quiet_hours: str | None = Field(default=None, alias="NOTIFY_QUIET_HOURS")

    tts_provider: str = Field(default="gtts", alias="TTS_PROVIDER")
    tts_language: str = Field(default="ru", alias="TTS_LANGUAGE")
    tts_audio_dir: str = Field(default="/tmp/tts-audio", alias="TTS_AUDIO_DIR")

    voice_backend: str = Field(default="command", alias="VOICE_BACKEND")
    voice_worker_cmd: str = Field(default="python docker/voice_worker_example.py", alias="VOICE_WORKER_CMD")
    voice_command_timeout_seconds: int = Field(default=45, alias="VOICE_COMMAND_TIMEOUT_SECONDS")

    ts3audiobot_base_url: str | None = Field(default=None, alias="TS3_AUDIOBOT_BASE_URL")
    ts3audiobot_api_key: str | None = Field(default=None, alias="TS3_AUDIOBOT_API_KEY")
    ts3audiobot_join_endpoint: str = Field(default="/api/bot/join", alias="TS3_AUDIOBOT_JOIN_ENDPOINT")
    ts3audiobot_play_endpoint: str = Field(default="/api/bot/play_tts", alias="TS3_AUDIOBOT_PLAY_ENDPOINT")
    ts3audiobot_leave_endpoint: str = Field(default="/api/bot/leave", alias="TS3_AUDIOBOT_LEAVE_ENDPOINT")

    daily_report_hour_msk: int = Field(default=10, alias="DAILY_REPORT_HOUR_MSK")
    weekly_report_weekday: int = Field(default=1, alias="WEEKLY_REPORT_WEEKDAY")

    bootstrap_admin_tg_ids: list[int] = Field(default_factory=list, alias="BOOTSTRAP_ADMIN_TG_IDS")

    @field_validator(
        "bot_admin_ids",
        "bootstrap_admin_tg_ids",
        "ts3_channel_alert_ids",
        "chatwatch_channel_whitelist",
        mode="before",
    )
    @classmethod
    def _parse_int_list(cls, value: Any) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, str):
            return [int(chunk.strip()) for chunk in value.split(",") if chunk.strip()]
        raise ValueError("Ожидался список чисел")

    @field_validator("chatwatch_allowed_types", mode="before")
    @classmethod
    def _parse_str_list(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            return [chunk.strip() for chunk in value.split(",") if chunk.strip()]
        raise ValueError("Ожидался список строк")


@lru_cache(1)
def get_settings() -> Settings:
    return Settings()
