"""Assemble scene images, narration and captions into a 1080x1920 MP4 with ffmpeg."""

from __future__ import annotations

from pathlib import Path

from .config import FPS, HEIGHT, WIDTH
from .media import run
from .models import AudioClip, ImageAsset


def scene_clip(image: ImageAsset, seconds: float, index: int, out: Path) -> None:
    """A slow zoom on one still image (alternating in and out so cuts don't feel identical)."""
    frames = max(1, round(seconds * FPS))
    zoom_in = index % 2 == 0
    z = f"1+0.10*on/{frames}" if zoom_in else f"1.10-0.10*on/{frames}"
    vf = (
        f"scale={WIDTH * 2}:{HEIGHT * 2},"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        "format=yuv420p"
    )
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(image.path), "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", str(out)])


def assemble(
    images: list[ImageAsset],
    audio: list[AudioClip],
    subtitles: Path,
    font: Path,
    workdir: Path,
    out: Path,
    bgm: Path | None = None,
) -> None:
    clips = []
    for i, (image, clip) in enumerate(zip(images, audio)):
        path = workdir / f"clip_{i:02d}.mp4"
        scene_clip(image, clip.duration, i, path)
        clips.append(path)

    video_list = workdir / "clips.txt"
    video_list.write_text("".join(f"file '{p.resolve()}'\n" for p in clips))
    video = workdir / "video.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(video_list), "-c", "copy", str(video)])

    narration = workdir / "narration.m4a"
    inputs = [arg for clip in audio for arg in ("-i", str(clip.path))]
    concat = "".join(f"[{i}:a]" for i in range(len(audio))) + f"concat=n={len(audio)}:v=0:a=1[a]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", concat, "-map", "[a]", "-c:a", "aac", "-b:a", "160k",
         str(narration)])

    subs = f"subtitles=filename='{subtitles.resolve()}':fontsdir='{font.parent}'"
    cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(narration)]
    if bgm:
        # Background music loops under the voice at low volume.
        cmd += ["-stream_loop", "-1", "-i", str(bgm), "-filter_complex",
                f"[0:v]{subs}[v];[2:a]volume=0.12[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-vf", subs, "-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
            "-shortest", "-movflags", "+faststart", str(out)]
    run(cmd)
