from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.core.enums import ChatMessageType, Ts3EventType
from app.core.logging import get_logger
from app.services.teamspeak.dto import TS3ChannelDTO, TS3ClientDTO, TS3EventDTO
from app.services.teamspeak.query_codec import encode_value, parse_data_lines, parse_error_line, parse_kv_segment


class TeamSpeakQueryError(RuntimeError):
    pass


class _ServerQueryConnection:
    def __init__(
        self,
        host: str,
        port: int,
        login: str,
        password: str,
        virtual_server_id: int,
        nickname: str,
        *,
        connection_name: str,
    ) -> None:
        self._host = host
        self._port = port
        self._login = login
        self._password = password
        self._virtual_server_id = virtual_server_id
        self._nickname = nickname
        self._name = connection_name
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._log = get_logger(component=f"ts3_conn_{connection_name}")

    @property
    def is_connected(self) -> bool:
        return self._reader is not None and self._writer is not None and not self._writer.is_closing()

    async def close(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    @retry(
        reraise=True,
        retry=retry_if_exception_type((OSError, TeamSpeakQueryError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(5),
    )
    async def connect(self) -> None:
        if self.is_connected:
            return
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

        await self._read_until_error_line()
        await self.command(
            f"login client_login_name={encode_value(self._login)} client_login_password={encode_value(self._password)}"
        )
        await self.command(f"use sid={self._virtual_server_id}")
        await self.command(f"clientupdate client_nickname={encode_value(self._nickname)}")
        self._log.info("ts3_connected")

    async def command(self, command: str) -> list[dict[str, str]]:
        if not self.is_connected:
            await self.connect()

        async with self._lock:
            assert self._writer is not None
            self._writer.write((command + "\n").encode("utf-8"))
            await self._writer.drain()
            lines = await self._read_until_error_line()
            data_lines = [line for line in lines if line and not line.startswith("notify") and not line.startswith("error")]
            error_line = next((line for line in reversed(lines) if line.startswith("error")), "error id=0 msg=ok")
            error_id, msg = parse_error_line(error_line)
            if error_id != 0:
                raise TeamSpeakQueryError(f"TS3 command failed: {command}, id={error_id}, msg={msg}")
            return parse_data_lines(data_lines)

    async def read_line(self) -> str:
        if not self.is_connected:
            raise TeamSpeakQueryError("connection not ready")
        assert self._reader is not None
        raw = await self._reader.readline()
        if not raw:
            raise TeamSpeakQueryError("TS3 connection closed")
        return raw.decode("utf-8", errors="ignore").strip()

    async def _read_until_error_line(self) -> list[str]:
        lines: list[str] = []
        while True:
            line = await self.read_line()
            lines.append(line)
            if line.startswith("error"):
                return lines


class TeamSpeakServerQueryAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._command_conn = _ServerQueryConnection(
            host=settings.ts3_host,
            port=settings.ts3_query_port,
            login=settings.ts3_query_login,
            password=settings.ts3_query_password,
            virtual_server_id=settings.ts3_virtual_server_id,
            nickname=settings.ts3_query_nickname,
            connection_name="command",
        )
        self._event_conn = _ServerQueryConnection(
            host=settings.ts3_host,
            port=settings.ts3_query_port,
            login=settings.ts3_query_login,
            password=settings.ts3_query_password,
            virtual_server_id=settings.ts3_virtual_server_id,
            nickname=f"{settings.ts3_query_nickname}-events",
            connection_name="events",
        )
        self._events_queue: asyncio.Queue[TS3EventDTO] = asyncio.Queue(maxsize=settings.ts3_event_queue_size)
        self._listener_task: asyncio.Task[None] | None = None
        self._channels_cache: dict[int, str] = {}
        self._log = get_logger(component="ts3_adapter")

    async def connect(self) -> None:
        await self._command_conn.connect()
        await self._event_conn.connect()
        await self._register_events()
        if not self._listener_task or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._event_listener_loop(), name="ts3-event-listener")

    async def ensure_connected(self) -> None:
        if not self._command_conn.is_connected or not self._event_conn.is_connected:
            await self.connect()

    async def disconnect(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
        await self._command_conn.close()
        await self._event_conn.close()

    async def get_channels(self) -> list[TS3ChannelDTO]:
        await self.ensure_connected()
        rows = await self._command_conn.command("channellist")
        channels = [
            TS3ChannelDTO(channel_id=int(row.get("cid", 0)), name=row.get("channel_name", "Unknown"))
            for row in rows
        ]
        self._channels_cache = {ch.channel_id: ch.name for ch in channels}
        return channels

    async def get_online_clients(self) -> list[TS3ClientDTO]:
        await self.ensure_connected()
        if not self._channels_cache:
            await self.get_channels()

        rows = await self._command_conn.command("clientlist -uid -away -voice -times -groups -info")
        clients: list[TS3ClientDTO] = []
        for row in rows:
            if int(row.get("client_type", 0)) == 1:
                continue
            channel_id = int(row.get("cid", 0))
            clients.append(
                TS3ClientDTO(
                    clid=int(row.get("clid", 0)),
                    uid=row.get("client_unique_identifier", ""),
                    nickname=row.get("client_nickname", "Unknown"),
                    channel_id=channel_id,
                    channel_name=self._channels_cache.get(channel_id, f"Channel {channel_id}"),
                    client_database_id=int(row["client_database_id"]) if row.get("client_database_id") else None,
                    is_query_client=int(row.get("client_type", 0)) == 1,
                    is_muted=bool(int(row.get("client_input_muted", 0))),
                    is_deaf=bool(int(row.get("client_output_muted", 0))),
                    server_groups=row.get("client_servergroups"),
                    channel_joined_seconds=int(row.get("client_idle_time", 0)) // 1000,
                )
            )
        return clients

    async def get_client_info(self, clid: int) -> dict[str, str]:
        await self.ensure_connected()
        rows = await self._command_conn.command(f"clientinfo clid={clid}")
        return rows[0] if rows else {}

    async def kick_client(self, clid: int, reason: str) -> None:
        await self.ensure_connected()
        await self._command_conn.command(f"clientkick clid={clid} reasonid=5 reasonmsg={encode_value(reason)}")

    async def ban_client(self, clid: int, duration_seconds: int, reason: str) -> None:
        await self.ensure_connected()
        await self._command_conn.command(
            f"banclient clid={clid} time={duration_seconds} banreason={encode_value(reason)}"
        )

    async def move_client(self, clid: int, channel_id: int) -> None:
        await self.ensure_connected()
        await self._command_conn.command(f"clientmove clid={clid} cid={channel_id}")

    async def poke_client(self, clid: int, message: str) -> None:
        await self.ensure_connected()
        await self._command_conn.command(f"clientpoke clid={clid} msg={encode_value(message)}")

    async def send_private_message(self, clid: int, message: str) -> None:
        await self.ensure_connected()
        await self._command_conn.command(
            f"sendtextmessage targetmode=1 target={clid} msg={encode_value(message)}"
        )

    async def set_client_mute(self, clid: int, muted: bool) -> None:
        await self.ensure_connected()
        mute_value = 1 if muted else 0
        await self._command_conn.command(f"clientedit clid={clid} client_input_muted={mute_value}")

    async def assign_server_group(self, client_database_id: int, sgid: int) -> None:
        await self.ensure_connected()
        await self._command_conn.command(f"servergroupaddclient sgid={sgid} cldbid={client_database_id}")

    async def remove_server_group(self, client_database_id: int, sgid: int) -> None:
        await self.ensure_connected()
        await self._command_conn.command(f"servergroupdelclient sgid={sgid} cldbid={client_database_id}")

    async def find_online_clients(self, pattern: str) -> list[TS3ClientDTO]:
        clients = await self.get_online_clients()
        lowered = pattern.lower()
        return [
            client
            for client in clients
            if lowered in client.nickname.lower() or lowered in client.uid.lower() or lowered == str(client.clid)
        ]

    async def drain_events(self, limit: int = 200) -> list[TS3EventDTO]:
        items: list[TS3EventDTO] = []
        for _ in range(limit):
            if self._events_queue.empty():
                break
            items.append(self._events_queue.get_nowait())
        return items

    async def _register_events(self) -> None:
        await self._event_conn.command("servernotifyregister event=server")
        await self._event_conn.command("servernotifyregister event=channel id=0")
        await self._event_conn.command("servernotifyregister event=textserver")
        await self._event_conn.command("servernotifyregister event=textchannel")
        await self._event_conn.command("servernotifyregister event=textprivate")

    async def _event_listener_loop(self) -> None:
        self._log.info("ts3_event_listener_started")
        while True:
            try:
                line = await self._event_conn.read_line()
                if not line or line.startswith("error"):
                    continue
                if not line.startswith("notify"):
                    continue
                event = self._parse_notify_line(line)
                if event is not None:
                    await self._queue_event(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._log.warning("ts3_event_listener_error", error=str(exc))
                await asyncio.sleep(2)
                await self._event_conn.close()
                await self._event_conn.connect()
                await self._register_events()

    async def _queue_event(self, event: TS3EventDTO) -> None:
        if self._events_queue.full():
            _ = self._events_queue.get_nowait()
        self._events_queue.put_nowait(event)

    def _parse_notify_line(self, line: str) -> TS3EventDTO | None:
        if " " in line:
            event_name, payload_raw = line.split(" ", 1)
        else:
            event_name, payload_raw = line, ""
        payload = parse_kv_segment(payload_raw)
        now = datetime.utcnow()

        if event_name == "notifycliententerview":
            return TS3EventDTO(
                event_type=Ts3EventType.JOIN,
                timestamp=now,
                client_uid=payload.get("client_unique_identifier"),
                client_nickname=payload.get("client_nickname"),
                to_channel_id=int(payload.get("ctid", payload.get("cid", 0)) or 0),
                raw=payload,
            )

        if event_name == "notifyclientleftview":
            return TS3EventDTO(
                event_type=Ts3EventType.LEAVE,
                timestamp=now,
                client_uid=payload.get("client_unique_identifier"),
                client_nickname=payload.get("client_nickname"),
                from_channel_id=int(payload.get("cfid", payload.get("cid", 0)) or 0),
                raw=payload,
            )

        if event_name == "notifyclientmoved":
            return TS3EventDTO(
                event_type=Ts3EventType.MOVE,
                timestamp=now,
                client_uid=payload.get("client_unique_identifier"),
                client_nickname=payload.get("client_nickname"),
                from_channel_id=int(payload.get("cfid", 0) or 0),
                to_channel_id=int(payload.get("ctid", 0) or 0),
                raw=payload,
            )

        if event_name == "notifytextmessage":
            mode = int(payload.get("targetmode", "0"))
            message_type = {
                1: ChatMessageType.PRIVATE,
                2: ChatMessageType.CHANNEL,
                3: ChatMessageType.SERVER,
            }.get(mode, ChatMessageType.SERVER)
            return TS3EventDTO(
                event_type=Ts3EventType.MESSAGE,
                timestamp=now,
                message_type=message_type,
                message_text=payload.get("msg", ""),
                invoker_uid=payload.get("invokeruid"),
                invoker_name=payload.get("invokername"),
                to_channel_id=int(payload.get("ctid", payload.get("target", 0)) or 0) if mode == 2 else None,
                raw=payload,
            )

        return None
