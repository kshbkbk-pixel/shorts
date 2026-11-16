"""Split narration into short caption lines and write them as an ASS subtitle file.

Timing is proportional to character count inside each scene's audio. That is close enough
for short Korean phrases; word-level timestamps from the TTS provider can replace it later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from .config import HEIGHT, WIDTH

MAX_CHARS = 14  # characters per caption line on a 1080-wide frame at the template's font size


@dataclass
class Caption:
    start: float
    end: float
    text: str


def chunk(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Break a sentence into caption pieces at spaces, keeping each piece under max_chars."""
    words = re.sub(r"\s+", " ", text.strip()).split(" ")
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = candidate
        if current.endswith((".", "?", "!", ",")) and len(current) >= max_chars // 2:
            pieces.append(current)
            current = ""
    if current:
        pieces.append(current)
    return pieces


def time_scene(text: str, start: float, length: float) -> list[Caption]:
    pieces = chunk(text)
    weights = [max(1, len(p.replace(" ", ""))) for p in pieces]
    total = sum(weights)
    captions, t = [], start
    for piece, weight in zip(pieces, weights):
        span = length * weight / total
        captions.append(Caption(start=t, end=t + span, text=piece.rstrip(".,")))
        t += span
    return captions


def _ts(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def font_family(font: Path) -> str:
    return ImageFont.truetype(str(font), 20).getname()[0]


def write_ass(captions: list[Caption], title: str, total: float, font: Path, out: Path) -> None:
    """Template "bold-center": title box at the top, large outlined captions in the lower third."""
    family = font_family(font)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{family},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,560,1
Style: Highlight,{family},92,&H0000E5FF,&H0000E5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,560,1
Style: Title,{family},72,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,0,0,3,18,0,8,60,60,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 0,{_ts(0)},{_ts(total)},Title,,0,0,0,,{_escape(title)}"]
    for i, c in enumerate(captions):
        style = "Highlight" if i == 0 else "Caption"  # the hook's first line stands out
        lines.append(f"Dialogue: 1,{_ts(c.start)},{_ts(c.end)},{style},,0,0,0,,{_escape(c.text)}")
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")
