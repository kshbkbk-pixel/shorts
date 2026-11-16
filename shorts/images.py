"""Image providers behind one interface. Every image is 1080x1920 (9:16) after saving."""

from __future__ import annotations

import base64
import hashlib
import time
from io import BytesIO
from pathlib import Path
from typing import Protocol

import httpx
from PIL import Image, ImageDraw, ImageOps

from .config import HEIGHT, WIDTH, env, require
from .models import ImageAsset, Usage

# Approximate USD per image. Check each provider's pricing page.
PRICE_PER_IMAGE = {
    "mock": 0.0,
    "fal-schnell": 0.003,
    "fal-dev": 0.025,
    "openai": 0.04,
}

STYLE_SUFFIX = ", vertical 9:16 composition, cinematic lighting, detailed digital illustration, no text, no watermark"


class ImageProvider(Protocol):
    name: str

    def generate(self, prompt: str, out: Path) -> tuple[ImageAsset, Usage]: ...


def _save_vertical(data: bytes, out: Path) -> None:
    """Crop and scale whatever the provider returned to exactly 1080x1920."""
    image = Image.open(BytesIO(data)).convert("RGB")
    ImageOps.fit(image, (WIDTH, HEIGHT), Image.Resampling.LANCZOS).save(out, quality=92)


def _usage(name: str, started: float) -> Usage:
    return Usage(provider=name, kind="image", units=1, usd=PRICE_PER_IMAGE.get(name, 0.0),
                 seconds=time.monotonic() - started)


class MockImages:
    """Colored gradient placeholders, one color per prompt."""

    name = "mock"

    def generate(self, prompt: str, out: Path) -> tuple[ImageAsset, Usage]:
        started = time.monotonic()
        digest = hashlib.sha256(prompt.encode()).digest()
        top, bottom = digest[:3], digest[3:6]
        image = Image.new("RGB", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image)
        for y in range(HEIGHT):
            t = y / HEIGHT
            draw.line([(0, y), (WIDTH, y)], fill=tuple(int(a * (1 - t) + b * t) for a, b in zip(top, bottom)))
        image.save(out, quality=90)
        return ImageAsset(path=out), _usage(self.name, started)


class FalFlux:
    """FLUX on fal.ai. `variant` is "schnell" (cheap, fast) or "dev" (better, about 8x the price)."""

    def __init__(self, variant: str = "schnell"):
        self.key = require("FAL_KEY")
        self.variant = variant
        self.name = f"fal-{variant}"

    def generate(self, prompt: str, out: Path) -> tuple[ImageAsset, Usage]:
        started = time.monotonic()
        r = httpx.post(
            f"https://fal.run/fal-ai/flux/{self.variant}",
            headers={"Authorization": f"Key {self.key}"},
            json={"prompt": prompt + STYLE_SUFFIX, "image_size": "portrait_16_9", "num_images": 1},
            timeout=180,
        )
        r.raise_for_status()
        url = r.json()["images"][0]["url"]
        _save_vertical(httpx.get(url, timeout=120).content, out)
        return ImageAsset(path=out), _usage(self.name, started)


class OpenAIImages:
    name = "openai"

    def __init__(self):
        self.key = require("OPENAI_API_KEY")
        self.model = env("OPENAI_IMAGE_MODEL", "gpt-image-1")

    def generate(self, prompt: str, out: Path) -> tuple[ImageAsset, Usage]:
        started = time.monotonic()
        r = httpx.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {self.key}"},
            json={"model": self.model, "prompt": prompt + STYLE_SUFFIX, "size": "1024x1536"},
            timeout=180,
        )
        r.raise_for_status()
        _save_vertical(base64.b64decode(r.json()["data"][0]["b64_json"]), out)
        return ImageAsset(path=out), _usage(self.name, started)


def get_images(name: str) -> ImageProvider:
    if name == "mock":
        return MockImages()
    if name in ("fal-schnell", "fal-dev"):
        return FalFlux(name.split("-", 1)[1])
    if name == "openai":
        return OpenAIImages()
    raise ValueError(f"알 수 없는 이미지 생성기: {name} (가능: mock, fal-schnell, fal-dev, openai)")
