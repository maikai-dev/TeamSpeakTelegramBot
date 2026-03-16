from __future__ import annotations

from pathlib import Path

import httpx

from app.core.config import Settings
from app.services.voice.adapter import VoiceAdapter


class TS3AudioBotVoiceAdapter(VoiceAdapter):
    """
    Интеграция с внешним TS3AudioBot API.
    Ожидаемые endpoints задаются в .env.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.ts3audiobot_base_url:
            raise ValueError("TS3AudioBot base URL не задан")
        self._base_url = settings.ts3audiobot_base_url.rstrip("/")
        self._api_key = settings.ts3audiobot_api_key
        self._join_endpoint = settings.ts3audiobot_join_endpoint
        self._play_endpoint = settings.ts3audiobot_play_endpoint
        self._leave_endpoint = settings.ts3audiobot_leave_endpoint

    async def voice_join(self, channel_id: int) -> None:
        await self._post(self._join_endpoint, {"channel_id": channel_id})

    async def voice_play_tts(self, channel_id: int, text: str, audio_path: Path) -> None:
        payload = {
            "channel_id": channel_id,
            "text": text,
            "audio_path": str(audio_path),
        }
        await self._post(self._play_endpoint, payload)

    async def voice_leave(self) -> None:
        await self._post(self._leave_endpoint, {})

    async def _post(self, endpoint: str, payload: dict) -> None:
        url = f"{self._base_url}{endpoint}"
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
