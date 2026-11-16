"""Topic -> script -> images + narration -> captions -> MP4, with a cost report."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import font_path
from .images import ImageProvider
from .models import AudioClip, ImageAsset, Script, Usage
from .render import assemble
from .subtitles import time_scene, write_ass
from .tts import TTSProvider

USD_TO_KRW = 1400


def save_script(script: Script, path: Path) -> None:
    path.write_text(script.model_dump_json(indent=2), encoding="utf-8")


def load_script(path: Path) -> Script:
    return Script.model_validate_json(path.read_text(encoding="utf-8"))


def build_video(
    script: Script,
    tts: TTSProvider,
    images: ImageProvider,
    outdir: Path,
    bgm: Path | None = None,
    prior_usage: list[Usage] | None = None,
    workers: int = 4,
) -> Path:
    """Render a script to outdir/final.mp4 and write outdir/report.json."""
    outdir.mkdir(parents=True, exist_ok=True)
    work = outdir / "work"
    work.mkdir(exist_ok=True)
    save_script(script, outdir / "script.json")
    usage: list[Usage] = list(prior_usage or [])

    # Narration and pictures don't depend on each other, so they run side by side.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        audio_jobs = [pool.submit(tts.synthesize, s.narration, work / f"voice_{i:02d}.mp3")
                      for i, s in enumerate(script.scenes)]
        image_jobs = [pool.submit(images.generate, s.image_prompt, work / f"image_{i:02d}.jpg")
                      for i, s in enumerate(script.scenes)]
        audio: list[AudioClip] = []
        pictures: list[ImageAsset] = []
        for job in audio_jobs:
            clip, u = job.result()
            audio.append(clip)
            usage.append(u)
        for job in image_jobs:
            asset, u = job.result()
            pictures.append(asset)
            usage.append(u)

    captions, t = [], 0.0
    for scene, clip in zip(script.scenes, audio):
        captions += time_scene(scene.narration, t, clip.duration)
        t += clip.duration

    font = font_path()
    ass = work / "captions.ass"
    write_ass(captions, script.title, t, font, ass)

    final = outdir / "final.mp4"
    assemble(pictures, audio, ass, font, work, final, bgm=bgm)
    write_report(usage, t, outdir / "report.json")
    return final


def write_report(usage: list[Usage], seconds: float, path: Path) -> dict:
    by_kind: dict[str, float] = {}
    for u in usage:
        by_kind[u.kind] = by_kind.get(u.kind, 0.0) + u.usd
    total = sum(by_kind.values())
    report = {
        "video_seconds": round(seconds, 2),
        "cost_usd": {k: round(v, 4) for k, v in by_kind.items()},
        "total_usd": round(total, 4),
        "total_krw": round(total * USD_TO_KRW),
        "calls": [u.model_dump() for u in usage],
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
