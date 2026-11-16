"""Data shapes shared by every pipeline step."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Scene(BaseModel):
    """One scene: a line of narration and the picture shown while it plays."""

    narration: str = Field(description="한국어 내레이션 한두 문장")
    image_prompt: str = Field(description="English prompt for a vertical illustration of this scene")


class Script(BaseModel):
    title: str
    hook: str = Field(description="첫 2초에 나오는 한 문장. scenes[0].narration과 같아야 한다")
    scenes: list[Scene]

    @property
    def full_text(self) -> str:
        return " ".join(s.narration for s in self.scenes)


class AudioClip(BaseModel):
    path: Path
    duration: float  # seconds


class ImageAsset(BaseModel):
    path: Path


class Usage(BaseModel):
    """What one provider call consumed, so the run can report its cost."""

    provider: str
    kind: str  # "llm" | "tts" | "image"
    units: float  # characters for TTS, images for image, tokens for LLM
    usd: float
    seconds: float
