from __future__ import annotations

import asyncio
import shlex
from pathlib import Path

from app.core.config import Settings
from app.services.voice.adapter import VoiceAdapter


class CommandVoiceAdapter(VoiceAdapter):
    """
    Реалистичный интерфейс для внешнего voice-sidecar.

    VOICE_WORKER_CMD должен поддерживать режимы:
      <cmd> join --channel <id>
      <cmd> play --channel <id> --text "..." --audio /path/file.mp3
      <cmd> leave
    """

    def __init__(self, settings: Settings) -> None:
        self._base_cmd = settings.voice_worker_cmd
        self._timeout = settings.voice_command_timeout_seconds

    async def voice_join(self, channel_id: int) -> None:
        await self._run(f"join --channel {channel_id}")

    async def voice_play_tts(self, channel_id: int, text: str, audio_path: Path) -> None:
        safe_text = shlex.quote(text)
        safe_audio = shlex.quote(str(audio_path))
        await self._run(f"play --channel {channel_id} --text {safe_text} --audio {safe_audio}")

    async def voice_leave(self) -> None:
        await self._run("leave")

    async def _run(self, suffix: str) -> None:
        cmd = f"{self._base_cmd} {suffix}"
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
        except TimeoutError as exc:
            process.kill()
            raise RuntimeError("Voice worker timeout") from exc

        if process.returncode != 0:
            error_text = stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"Voice worker failed: {error_text.strip()}")

        _ = stdout
