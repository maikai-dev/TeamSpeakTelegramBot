from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from gtts import gTTS


class BaseTTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError


class GTTSProvider(BaseTTSProvider):
    def __init__(self, language: str = "ru") -> None:
        self._language = language

    async def synthesize(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _write() -> None:
            tts = gTTS(text=text, lang=self._language)
            tts.save(str(output_path))

        await asyncio.to_thread(_write)
        return output_path
