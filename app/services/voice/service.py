from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.voice.adapter import DisabledVoiceAdapter, VoiceAdapter
from app.services.voice.command_worker import CommandVoiceAdapter
from app.services.voice.ts3audiobot import TS3AudioBotVoiceAdapter


def build_voice_adapter(settings: Settings) -> VoiceAdapter:
    backend = settings.voice_backend.lower().strip()
    if backend == "command":
        return CommandVoiceAdapter(settings)
    if backend == "ts3audiobot":
        return TS3AudioBotVoiceAdapter(settings)
    return DisabledVoiceAdapter()


class VoiceService:
    def __init__(self, adapter: VoiceAdapter) -> None:
        self._adapter = adapter

    async def voice_join(self, channel_id: int) -> None:
        await self._adapter.voice_join(channel_id)

    async def voice_play_tts(self, channel_id: int, text: str, audio_path: Path) -> None:
        await self._adapter.voice_play_tts(channel_id, text, audio_path)

    async def voice_leave(self) -> None:
        await self._adapter.voice_leave()
