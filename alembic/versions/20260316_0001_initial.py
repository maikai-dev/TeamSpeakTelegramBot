"""initial schema

Revision ID: 20260316_0001
Revises: 
Create Date: 2026-03-16 23:59:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260316_0001"
down_revision = None
branch_labels = None
depends_on = None


role_name = sa.Enum("admin", "user", name="role_name")
ts3_event_type = sa.Enum("join", "leave", "move", "message", name="ts3_event_type")
chat_message_type = sa.Enum("server", "channel", "private", name="chat_message_type")
notification_type = sa.Enum(
    "join",
    "leave",
    "move",
    "chat",
    "subscription",
    "daily_report",
    "weekly_report",
    "long_online",
    "channel_alert",
    name="notification_type",
)
subscription_type = sa.Enum("user_online", "channel_activity", name="subscription_type")
admin_action_type = sa.Enum(
    "kick",
    "ban",
    "move",
    "mute",
    "unmute",
    "poke",
    "assign_group",
    "remove_group",
    "tts",
    "chatwatch_toggle",
    "reload_config",
    name="admin_action_type",
)
tts_job_status = sa.Enum("pending", "processing", "done", "failed", name="tts_job_status")


def upgrade() -> None:
    bind = op.get_bind()
    role_name.create(bind, checkfirst=True)
    ts3_event_type.create(bind, checkfirst=True)
    chat_message_type.create(bind, checkfirst=True)
    notification_type.create(bind, checkfirst=True)
    subscription_type.create(bind, checkfirst=True)
    admin_action_type.create(bind, checkfirst=True)
    tts_job_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", role_name, nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "ts3_clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_uid", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=255), nullable=False),
        sa.Column("client_database_id", sa.Integer(), nullable=True),
        sa.Column("telegram_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_channel_id", sa.Integer(), nullable=True),
        sa.Column("last_channel_name", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("client_uid", name="uq_ts3_clients_client_uid"),
    )
    op.create_index("ix_ts3_clients_client_uid", "ts3_clients", ["client_uid"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts3_client_id", sa.Integer(), sa.ForeignKey("ts3_clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("channel_name", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_sessions_ts3_client_id", "sessions", ["ts3_client_id"])
    op.create_index("ix_sessions_started_at", "sessions", ["started_at"])
    op.create_index("ix_sessions_ended_at", "sessions", ["ended_at"])

    op.create_table(
        "channel_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts3_client_id", sa.Integer(), sa.ForeignKey("ts3_clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", ts3_event_type, nullable=False),
        sa.Column("from_channel_id", sa.Integer(), nullable=True),
        sa.Column("from_channel_name", sa.String(length=255), nullable=True),
        sa.Column("to_channel_id", sa.Integer(), nullable=True),
        sa.Column("to_channel_name", sa.String(length=255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_channel_events_ts3_client_id", "channel_events", ["ts3_client_id"])
    op.create_index("ix_channel_events_occurred_at", "channel_events", ["occurred_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts3_client_id", sa.Integer(), sa.ForeignKey("ts3_clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_type", chat_message_type, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("channel_name", sa.String(length=255), nullable=True),
        sa.Column("invoker_name", sa.String(length=255), nullable=False),
        sa.Column("message_text", sa.String(length=2048), nullable=False),
        sa.Column("is_bot_message", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_messages_ts3_client_id", "chat_messages", ["ts3_client_id"])
    op.create_index("ix_chat_messages_occurred_at", "chat_messages", ["occurred_at"])

    op.create_table(
        "notification_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quiet_hours_start", sa.Integer(), nullable=True),
        sa.Column("quiet_hours_end", sa.Integer(), nullable=True),
        sa.Column("mute_until", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "notification_type", name="uq_notification_settings_user_type"),
    )
    op.create_index("ix_notification_settings_user_id", "notification_settings", ["user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscriber_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_type", subscription_type, nullable=False),
        sa.Column("target_ts3_client_id", sa.Integer(), sa.ForeignKey("ts3_clients.id", ondelete="CASCADE"), nullable=True),
        sa.Column("target_label", sa.String(length=255), nullable=True),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_subscriptions_subscriber_user_id", "subscriptions", ["subscriber_user_id"])
    op.create_index("ix_subscriptions_subscription_type", "subscriptions", ["subscription_type"])
    op.create_index("ix_subscriptions_target_ts3_client_id", "subscriptions", ["target_ts3_client_id"])

    op.create_table(
        "admin_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", admin_action_type, nullable=False),
        sa.Column("target_ts3_client_id", sa.Integer(), sa.ForeignKey("ts3_clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_label", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_admin_actions_admin_user_id", "admin_actions", ["admin_user_id"])

    op.create_table(
        "tts_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("channel_name", sa.String(length=255), nullable=True),
        sa.Column("text", sa.String(length=1024), nullable=False),
        sa.Column("status", tts_job_status, nullable=False),
        sa.Column("audio_path", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tts_jobs_requested_by_user_id", "tts_jobs", ["requested_by_user_id"])
    op.create_index("ix_tts_jobs_channel_id", "tts_jobs", ["channel_id"])

    op.create_table(
        "server_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_online", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_server_snapshots_captured_at", "server_snapshots", ["captured_at"])

    op.create_table(
        "stats_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("cache_key", name="uq_stats_cache_cache_key"),
    )
    op.create_index("ix_stats_cache_cache_key", "stats_cache", ["cache_key"])


def downgrade() -> None:
    op.drop_index("ix_stats_cache_cache_key", table_name="stats_cache")
    op.drop_table("stats_cache")

    op.drop_index("ix_server_snapshots_captured_at", table_name="server_snapshots")
    op.drop_table("server_snapshots")

    op.drop_index("ix_tts_jobs_channel_id", table_name="tts_jobs")
    op.drop_index("ix_tts_jobs_requested_by_user_id", table_name="tts_jobs")
    op.drop_table("tts_jobs")

    op.drop_index("ix_admin_actions_admin_user_id", table_name="admin_actions")
    op.drop_table("admin_actions")

    op.drop_index("ix_subscriptions_target_ts3_client_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_subscription_type", table_name="subscriptions")
    op.drop_index("ix_subscriptions_subscriber_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_notification_settings_user_id", table_name="notification_settings")
    op.drop_table("notification_settings")

    op.drop_index("ix_chat_messages_occurred_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_ts3_client_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_channel_events_occurred_at", table_name="channel_events")
    op.drop_index("ix_channel_events_ts3_client_id", table_name="channel_events")
    op.drop_table("channel_events")

    op.drop_index("ix_sessions_ended_at", table_name="sessions")
    op.drop_index("ix_sessions_started_at", table_name="sessions")
    op.drop_index("ix_sessions_ts3_client_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_ts3_clients_client_uid", table_name="ts3_clients")
    op.drop_table("ts3_clients")

    op.drop_table("user_roles")
    op.drop_table("roles")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")

    tts_job_status.drop(op.get_bind(), checkfirst=True)
    admin_action_type.drop(op.get_bind(), checkfirst=True)
    subscription_type.drop(op.get_bind(), checkfirst=True)
    notification_type.drop(op.get_bind(), checkfirst=True)
    chat_message_type.drop(op.get_bind(), checkfirst=True)
    ts3_event_type.drop(op.get_bind(), checkfirst=True)
    role_name.drop(op.get_bind(), checkfirst=True)
