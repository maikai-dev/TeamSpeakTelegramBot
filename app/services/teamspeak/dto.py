from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.core.enums import ChatMessageType, Ts3EventType


@dataclass(slots=True)
class TS3ChannelDTO:
    channel_id: int
    name: str


@dataclass(slots=True)
class TS3ClientDTO:
    clid: int
    uid: str
    nickname: str
    channel_id: int
    channel_name: str
    client_database_id: int | None = None
    is_query_client: bool = False
    is_muted: bool = False
    is_deaf: bool = False
    server_groups: str | None = None
    channel_joined_seconds: int = 0


@dataclass(slots=True)
class TS3EventDTO:
    event_type: Ts3EventType
    timestamp: datetime
    client_uid: str | None = None
    client_nickname: str | None = None
    from_channel_id: int | None = None
    from_channel_name: str | None = None
    to_channel_id: int | None = None
    to_channel_name: str | None = None
    message_type: ChatMessageType | None = None
    message_text: str | None = None
    invoker_uid: str | None = None
    invoker_name: str | None = None
    raw: dict[str, str] = field(default_factory=dict)
