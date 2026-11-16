"""Settings read from the environment (see .env.example)."""

from __future__ import annotations

import os
from pathlib import Path

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
]

WIDTH, HEIGHT, FPS = 1080, 1920, 30


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value else default


def require(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"환경변수 {name} 가 필요합니다 (.env.example 참고)")
    return value


def font_path() -> Path:
    """A font with Hangul glyphs for subtitles. SHORTS_FONT wins if set."""
    override = env("SHORTS_FONT")
    if override:
        return Path(override)
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return Path(candidate)
    raise RuntimeError("한글 폰트를 찾지 못했습니다. SHORTS_FONT 에 .ttf/.otf 경로를 지정하세요")
