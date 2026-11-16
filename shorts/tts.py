"""Text-to-speech providers behind one interface, so they can be compared on the same script.

Request shapes follow each provider's public REST API as of 2026; verify against their docs
before relying on them in production.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Protocol

import httpx

from .config import env, require
from .media import duration, run
from .models import AudioClip, Usage

# Approximate USD per 1,000 characters. Check each provider's pricing page.
PRICE_PER_1K_CHARS = {
    "mock": 0.0,
    "openai": 0.015,
    "google": 0.016,
    "elevenlabs": 0.18,
}


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, out: Path) -> tuple[AudioClip, Usage]: ...


def _usage(name: str, text: str, started: float) -> Usage:
    chars = len(text)
    return Usage(
        provider=name,
        kind="tts",
        units=chars,
        usd=chars / 1000 * PRICE_PER_1K_CHARS.get(name, 0.0),
        seconds=time.monotonic() - started,
    )


def _finish(name: str, text: str, out: Path, started: float) -> tuple[AudioClip, Usage]:
    return AudioClip(path=out, duration=duration(out)), _usage(name, text, started)


class MockTTS:
    """Silent audio sized like Korean speech (about 7 characters a second)."""

    name = "mock"

    def synthesize(self, text: str, out: Path) -> tuple[AudioClip, Usage]:
        started = time.monotonic()
        seconds = max(1.0, len(text.replace(" ", "")) / 7)
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{seconds:.2f}",
             "-c:a", "libmp3lame", "-q:a", "6", str(out)])
        return _finish(self.name, text, out, started)


class OpenAITTS:
    name = "openai"

    def __init__(self):
        self.key = require("OPENAI_API_KEY")
        self.model = env("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
        self.voice = env("OPENAI_TTS_VOICE", "alloy")

    def synthesize(self, text: str, out: Path) -> tuple[AudioClip, Usage]:
        started = time.monotonic()
        r = httpx.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {self.key}"},
            json={"model": self.model, "voice": self.voice, "input": text, "response_format": "mp3"},
            timeout=120,
        )
        r.raise_for_status()
        out.write_bytes(r.content)
        return _finish(self.name, text, out, started)


class GoogleTTS:
    name = "google"

    def __init__(self):
        self.key = require("GOOGLE_TTS_API_KEY")
        self.voice = env("GOOGLE_TTS_VOICE", "ko-KR-Neural2-A")

    def synthesize(self, text: str, out: Path) -> tuple[AudioClip, Usage]:
        started = time.monotonic()
        r = httpx.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            params={"key": self.key},
            json={
                "input": {"text": text},
                "voice": {"languageCode": "ko-KR", "name": self.voice},
                "audioConfig": {"audioEncoding": "MP3"},
            },
            timeout=120,
        )
        r.raise_for_status()
        out.write_bytes(base64.b64decode(r.json()["audioContent"]))
        return _finish(self.name, text, out, started)


class ElevenLabsTTS:
    name = "elevenlabs"

    def __init__(self):
        self.key = require("ELEVENLABS_API_KEY")
        self.voice_id = require("ELEVENLABS_VOICE_ID")
        self.model = env("ELEVENLABS_MODEL", "eleven_multilingual_v2")

    def synthesize(self, text: str, out: Path) -> tuple[AudioClip, Usage]:
        started = time.monotonic()
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            headers={"xi-api-key": self.key},
            json={"text": text, "model_id": self.model},
            timeout=120,
        )
        r.raise_for_status()
        out.write_bytes(r.content)
        return _finish(self.name, text, out, started)


PROVIDERS = {"mock": MockTTS, "openai": OpenAITTS, "google": GoogleTTS, "elevenlabs": ElevenLabsTTS}


def get_tts(name: str) -> TTSProvider:
    if name not in PROVIDERS:
        raise ValueError(f"알 수 없는 TTS: {name} (가능: {', '.join(PROVIDERS)})")
    return PROVIDERS[name]()
