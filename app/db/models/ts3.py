from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ChatMessageType, Ts3EventType
from app.db.base import Base


class TS3Client(Base):
    __tablename__ = "ts3_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_uid: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    client_database_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("User", lazy="joined")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts3_client_id: Mapped[int] = mapped_column(ForeignKey("ts3_clients.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(Integer, index=True)
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    client = relationship("TS3Client", lazy="joined")


class ChannelEvent(Base):
    __tablename__ = "channel_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts3_client_id: Mapped[int | None] = mapped_column(ForeignKey("ts3_clients.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[Ts3EventType] = mapped_column(Enum(Ts3EventType, name="ts3_event_type"), nullable=False)
    from_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    from_channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    client = relationship("TS3Client", lazy="joined")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts3_client_id: Mapped[int | None] = mapped_column(ForeignKey("ts3_clients.id", ondelete="SET NULL"), index=True)
    message_type: Mapped[ChatMessageType] = mapped_column(
        Enum(ChatMessageType, name="chat_message_type"),
        nullable=False,
    )
    channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoker_name: Mapped[str] = mapped_column(String(255), nullable=False)
    message_text: Mapped[str] = mapped_column(String(2048), nullable=False)
    is_bot_message: Mapped[bool] = mapped_column(default=False, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    client = relationship("TS3Client", lazy="joined")


class ServerSnapshot(Base):
    __tablename__ = "server_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    total_online: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class StatsCache(Base):
    __tablename__ = "stats_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
