"""Command line entry point.

    python -m shorts script  --topic "..." --out runs/demo            # 1) 대본만 생성 → script.json 수정
    python -m shorts render  --script runs/demo/script.json            # 2) 수정한 대본으로 영상 생성
    python -m shorts make    --topic "..." --out runs/demo             # 대본부터 영상까지 한 번에
    python -m shorts compare --script runs/demo/script.json --tts openai,google --images fal-schnell,openai
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compare import compare
from .images import get_images
from .pipeline import build_video, load_script, save_script
from .script import get_writer
from .tts import get_tts


def _load_dotenv() -> None:
    env_file = Path(".env")
    if not env_file.exists():
        return
    import os

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def main(argv: list[str] | None = None) -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(prog="shorts", description="주제 한 줄로 60초 쇼츠 만들기")
    sub = parser.add_subparsers(dest="command", required=True)

    p_script = sub.add_parser("script", help="대본만 생성")
    p_make = sub.add_parser("make", help="대본 생성부터 렌더까지")
    for p in (p_script, p_make):
        p.add_argument("--topic", required=True)
        p.add_argument("--genre", default="")
        p.add_argument("--tone", default="")
        p.add_argument("--writer", default="claude", help="claude | mock")
        p.add_argument("--out", type=Path, default=Path("runs/latest"))

    p_render = sub.add_parser("render", help="script.json 으로 영상 생성")
    p_render.add_argument("--script", type=Path, required=True)
    p_render.add_argument("--out", type=Path)

    for p in (p_make, p_render):
        p.add_argument("--tts", default="google", help="mock | openai | google | elevenlabs")
        p.add_argument("--images", default="fal-schnell", help="mock | fal-schnell | fal-dev | openai")
        p.add_argument("--bgm", type=Path, help="저작권이 확보된 배경음악 파일")

    p_cmp = sub.add_parser("compare", help="같은 대본으로 TTS·이미지 공급자 비교")
    p_cmp.add_argument("--script", type=Path, required=True)
    p_cmp.add_argument("--tts", default="openai,google,elevenlabs")
    p_cmp.add_argument("--images", default="fal-schnell,fal-dev,openai")
    p_cmp.add_argument("--scenes", type=int, default=3)
    p_cmp.add_argument("--out", type=Path, default=Path("runs/compare"))

    args = parser.parse_args(argv)

    if args.command in ("script", "make"):
        script, usage = get_writer(args.writer).write(args.topic, args.genre, args.tone)
        args.out.mkdir(parents=True, exist_ok=True)
        save_script(script, args.out / "script.json")
        print(f"대본: {args.out / 'script.json'} (장면 {len(script.scenes)}개, {len(script.full_text)}자, ${usage.usd:.4f})")
        if args.command == "script":
            return
        final = build_video(script, get_tts(args.tts), get_images(args.images), args.out, args.bgm, [usage])
        _print_result(final)
    elif args.command == "render":
        out = args.out or args.script.parent
        final = build_video(load_script(args.script), get_tts(args.tts), get_images(args.images), out, args.bgm)
        _print_result(final)
    elif args.command == "compare":
        page = compare(load_script(args.script), _split(args.tts), _split(args.images), args.out, args.scenes)
        print(f"비교 페이지: {page}")


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _print_result(final: Path) -> None:
    report = json.loads((final.parent / "report.json").read_text(encoding="utf-8"))
    print(f"영상: {final} ({report['video_seconds']}초)")
    print(f"원가: ${report['total_usd']} (약 {report['total_krw']}원) {report['cost_usd']}")


if __name__ == "__main__":
    main()
