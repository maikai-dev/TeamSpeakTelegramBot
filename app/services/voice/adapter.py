from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class VoiceAdapter(ABC):
    @abstractmethod
    async def voice_join(self, channel_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def voice_play_tts(self, channel_id: int, text: str, audio_path: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    async def voice_leave(self) -> None:
        raise NotImplementedError


class DisabledVoiceAdapter(VoiceAdapter):
    async def voice_join(self, channel_id: int) -> None:
        raise RuntimeError("Voice backend отключен")

    async def voice_play_tts(self, channel_id: int, text: str, audio_path: Path) -> None:
        raise RuntimeError("Voice backend отключен")

    async def voice_leave(self) -> None:
        return None
