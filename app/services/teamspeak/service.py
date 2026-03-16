from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import ChatMessageType, NotificationType, Ts3EventType
from app.core.logging import get_logger
from app.db.repositories.notifications import NotificationRepository
from app.db.repositories.ts3 import TS3Repository
from app.services.notification_service import NotificationService
from app.services.runtime_config_service import RuntimeConfigService
from app.services.teamspeak.adapter import TeamSpeakServerQueryAdapter
from app.services.teamspeak.dto import TS3ClientDTO, TS3EventDTO


@dataclass(slots=True)
class PresenceState:
    uid: str
    nickname: str
    channel_id: int
    channel_name: str
    clid: int


class TeamSpeakService:
    def __init__(
        self,
        settings: Settings,
        adapter: TeamSpeakServerQueryAdapter,
        ts3_repo: TS3Repository,
        notification_repo: NotificationRepository,
        notification_service: NotificationService,
        runtime_config: RuntimeConfigService,
    ) -> None:
        self._settings = settings
        self._adapter = adapter
        self._repo = ts3_repo
        self._notification_repo = notification_repo
        self._notifications = notification_service
        self._runtime_config = runtime_config
        self._presence: dict[str, PresenceState] = {}
        self._bootstrapped = False
        self._log = get_logger(component="teamspeak_service")

    async def connect(self) -> None:
        await self._adapter.connect()

    async def get_online_clients(self) -> list[TS3ClientDTO]:
        return await self._adapter.get_online_clients()

    async def get_channels(self):
        return await self._adapter.get_channels()

    async def find_online_clients(self, pattern: str) -> list[TS3ClientDTO]:
        return await self._adapter.find_online_clients(pattern)

    async def kick_client(self, clid: int, reason: str) -> None:
        await self._adapter.kick_client(clid, reason)

    async def ban_client(self, clid: int, duration_seconds: int, reason: str) -> None:
        await self._adapter.ban_client(clid, duration_seconds, reason)

    async def move_client(self, clid: int, channel_id: int) -> None:
        await self._adapter.move_client(clid, channel_id)

    async def poke_client(self, clid: int, message: str) -> None:
        await self._adapter.poke_client(clid, message)

    async def send_private_message(self, clid: int, message: str) -> None:
        await self._adapter.send_private_message(clid, message)

    async def set_client_mute(self, clid: int, muted: bool) -> None:
        await self._adapter.set_client_mute(clid, muted)

    async def assign_group(self, client_database_id: int, sgid: int) -> None:
        await self._adapter.assign_server_group(client_database_id, sgid)

    async def remove_group(self, client_database_id: int, sgid: int) -> None:
        await self._adapter.remove_server_group(client_database_id, sgid)

    async def get_client_info(self, clid: int) -> dict[str, str]:
        return await self._adapter.get_client_info(clid)

    async def assign_group_by_clid(self, clid: int, sgid: int) -> None:
        info = await self.get_client_info(clid)
        cldbid = int(info.get("client_database_id", 0) or 0)
        if not cldbid:
            raise RuntimeError("Не удалось получить client_database_id")
        await self.assign_group(cldbid, sgid)

    async def remove_group_by_clid(self, clid: int, sgid: int) -> None:
        info = await self.get_client_info(clid)
        cldbid = int(info.get("client_database_id", 0) or 0)
        if not cldbid:
            raise RuntimeError("Не удалось получить client_database_id")
        await self.remove_group(cldbid, sgid)

    async def sync_presence(self, session: AsyncSession) -> None:
        now = datetime.utcnow()
        await self._adapter.ensure_connected()
        online_clients = await self._adapter.get_online_clients()
        current: dict[str, PresenceState] = {}

        for client in online_clients:
            current[client.uid] = PresenceState(
                uid=client.uid,
                nickname=client.nickname,
                channel_id=client.channel_id,
                channel_name=client.channel_name,
                clid=client.clid,
            )

        # upsert клиентов до обработки событий
        uid_to_db_id: dict[str, int] = {}
        for client in online_clients:
            db_client = await self._repo.upsert_client(
                session=session,
                client_uid=client.uid,
                nickname=client.nickname,
                client_database_id=client.client_database_id,
                channel_id=client.channel_id,
                channel_name=client.channel_name,
            )
            uid_to_db_id[client.uid] = db_client.id

        if not self._bootstrapped:
            alive_db_ids = list(uid_to_db_id.values())
            await self._repo.close_stale_sessions(session, alive_client_ids=alive_db_ids, ended_at=now)
            for client in online_clients:
                db_id = uid_to_db_id[client.uid]
                open_session = await self._repo.get_open_session(session, db_id)
                if open_session is None:
                    await self._repo.start_session(
                        session=session,
                        ts3_client_id=db_id,
                        channel_id=client.channel_id,
                        channel_name=client.channel_name,
                        started_at=now,
                    )
                await self._repo.add_channel_event(
                    session=session,
                    ts3_client_id=db_id,
                    event_type=Ts3EventType.JOIN,
                    occurred_at=now,
                    to_channel_id=client.channel_id,
                    to_channel_name=client.channel_name,
                )
            self._bootstrapped = True
            self._presence = current
            await self._repo.add_server_snapshot(
                session=session,
                captured_at=now,
                total_online=len(online_clients),
                payload={
                    "clients": [
                        {
                            "uid": c.uid,
                            "nickname": c.nickname,
                            "channel_id": c.channel_id,
                            "channel_name": c.channel_name,
                        }
                        for c in online_clients
                    ]
                },
            )
            return

        previous_uids = set(self._presence.keys())
        current_uids = set(current.keys())

        joined = current_uids - previous_uids
        left = previous_uids - current_uids
        same = current_uids & previous_uids

        for uid in joined:
            state = current[uid]
            db_id = uid_to_db_id[uid]
            await self._repo.start_session(
                session=session,
                ts3_client_id=db_id,
                channel_id=state.channel_id,
                channel_name=state.channel_name,
                started_at=now,
            )
            await self._repo.add_channel_event(
                session=session,
                ts3_client_id=db_id,
                event_type=Ts3EventType.JOIN,
                occurred_at=now,
                to_channel_id=state.channel_id,
                to_channel_name=state.channel_name,
            )
            text = f"🟢 JOIN: {state.nickname} → {state.channel_name}"
            await self._notifications.notify_admins(
                session,
                notification_type=NotificationType.JOIN,
                text=text,
                dedupe_key=f"join:{uid}:{state.channel_id}",
            )
            await self._notifications.notify_subscription(
                session,
                target_ts3_client_id=db_id,
                message=f"🔔 Ваш подписанный пользователь {state.nickname} зашел в TS3 ({state.channel_name}).",
            )
            if state.channel_id in self._settings.ts3_channel_alert_ids:
                await self._notifications.notify_admins(
                    session,
                    notification_type=NotificationType.CHANNEL_ALERT,
                    text=f"⚠️ Alert-канал: {state.nickname} вошел в {state.channel_name}",
                    dedupe_key=f"channel_alert:{uid}:{state.channel_id}",
                )

        for uid in left:
            prev = self._presence[uid]
            db_client = await self._repo.get_client_by_uid(session, uid)
            db_id = db_client.id if db_client else None
            if db_id:
                await self._repo.close_open_session(session, db_id, ended_at=now)
                await self._repo.add_channel_event(
                    session=session,
                    ts3_client_id=db_id,
                    event_type=Ts3EventType.LEAVE,
                    occurred_at=now,
                    from_channel_id=prev.channel_id,
                    from_channel_name=prev.channel_name,
                )
            await self._notifications.notify_admins(
                session,
                notification_type=NotificationType.LEAVE,
                text=f"🔴 LEAVE: {prev.nickname} вышел из TS3 (был в {prev.channel_name})",
                dedupe_key=f"leave:{uid}:{prev.channel_id}",
            )

        for uid in same:
            prev = self._presence[uid]
            cur = current[uid]
            if prev.channel_id != cur.channel_id:
                db_client = await self._repo.get_client_by_uid(session, uid)
                db_id = db_client.id if db_client else None
                if db_id:
                    await self._repo.close_open_session(session, db_id, ended_at=now)
                    await self._repo.start_session(
                        session=session,
                        ts3_client_id=db_id,
                        channel_id=cur.channel_id,
                        channel_name=cur.channel_name,
                        started_at=now,
                    )
                    await self._repo.add_channel_event(
                        session=session,
                        ts3_client_id=db_id,
                        event_type=Ts3EventType.MOVE,
                        occurred_at=now,
                        from_channel_id=prev.channel_id,
                        from_channel_name=prev.channel_name,
                        to_channel_id=cur.channel_id,
                        to_channel_name=cur.channel_name,
                    )
                await self._notifications.notify_admins(
                    session,
                    notification_type=NotificationType.MOVE,
                    text=f"🟡 MOVE: {cur.nickname}: {prev.channel_name} → {cur.channel_name}",
                    dedupe_key=f"move:{uid}:{prev.channel_id}:{cur.channel_id}",
                )
                if cur.channel_id in self._settings.ts3_channel_alert_ids:
                    await self._notifications.notify_channel_subscriptions(
                        session,
                        channel_id=cur.channel_id,
                        message=f"📢 В избранный канал {cur.channel_name} зашел {cur.nickname}",
                    )

        await self._repo.add_server_snapshot(
            session=session,
            captured_at=now,
            total_online=len(online_clients),
            payload={
                "clients": [
                    {
                        "uid": c.uid,
                        "nickname": c.nickname,
                        "channel_id": c.channel_id,
                        "channel_name": c.channel_name,
                    }
                    for c in online_clients
                ]
            },
        )
        self._presence = current

    async def process_chat_events(self, session: AsyncSession) -> int:
        chatwatch_enabled = await self._runtime_config.is_chatwatch_enabled()
        if not chatwatch_enabled:
            await self._adapter.drain_events(limit=100)
            return 0

        processed = 0
        events = await self._adapter.drain_events(limit=300)
        for event in events:
            if event.event_type != Ts3EventType.MESSAGE:
                continue

            message_type = event.message_type or ChatMessageType.SERVER
            if message_type.value not in self._settings.chatwatch_allowed_types:
                continue

            channel_id = event.to_channel_id
            if self._settings.chatwatch_channel_whitelist:
                if not channel_id or channel_id not in self._settings.chatwatch_channel_whitelist:
                    continue

            is_bot = False
            if self._settings.chatwatch_ignore_query_clients and event.invoker_name:
                is_bot = event.invoker_name.lower().startswith(self._settings.ts3_query_nickname.lower())
            if is_bot:
                continue

            ts3_client_id: int | None = None
            if event.invoker_uid:
                db_client = await self._repo.upsert_client(
                    session=session,
                    client_uid=event.invoker_uid,
                    nickname=event.invoker_name or "Unknown",
                    client_database_id=None,
                    channel_id=channel_id,
                    channel_name=event.to_channel_name,
                )
                ts3_client_id = db_client.id

            await self._repo.add_chat_message(
                session=session,
                ts3_client_id=ts3_client_id,
                message_type=message_type,
                channel_id=channel_id,
                channel_name=event.to_channel_name,
                invoker_name=event.invoker_name or "Unknown",
                message_text=event.message_text or "",
                occurred_at=event.timestamp,
                is_bot_message=is_bot,
            )

            await self._notifications.notify_admins(
                session,
                notification_type=NotificationType.CHAT,
                text=(
                    f"💬 TS3 chat\n"
                    f"Тип: {message_type.value}\n"
                    f"Автор: {event.invoker_name or 'Unknown'}\n"
                    f"Канал: {event.to_channel_name or event.to_channel_id or '-'}\n"
                    f"Время: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Текст: {event.message_text or ''}"
                ),
            )
            processed += 1

        return processed

    async def whois(self, session: AsyncSession, pattern: str) -> str:
        online = await self.find_online_clients(pattern)
        if online:
            lines = ["🔎 Найден онлайн:"]
            for client in online:
                lines.append(f"- {client.nickname} ({client.uid}) в {client.channel_name}")
            return "\n".join(lines)

        db_client = await self._repo.find_last_seen(session, pattern)
        if not db_client:
            return "Пользователь не найден."

        return (
            f"🔎 Пользователь в офлайне\n"
            f"Ник: {db_client.nickname}\n"
            f"UID: {db_client.client_uid}\n"
            f"Последний онлайн: {db_client.last_seen_at}"
        )

    async def find_client_for_subscription(
        self,
        session: AsyncSession,
        pattern: str,
    ) -> tuple[int | None, str]:
        online = await self.find_online_clients(pattern)
        if online:
            candidate = online[0]
            db_client = await self._repo.upsert_client(
                session=session,
                client_uid=candidate.uid,
                nickname=candidate.nickname,
                client_database_id=candidate.client_database_id,
                channel_id=candidate.channel_id,
                channel_name=candidate.channel_name,
            )
            return db_client.id, db_client.nickname

        db_client = await self._repo.find_last_seen(session, pattern)
        if db_client:
            return db_client.id, db_client.nickname

        return None, pattern
