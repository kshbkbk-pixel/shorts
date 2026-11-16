"""Run the same script through several TTS and image providers and write one page to judge them by ear and eye."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .images import get_images
from .models import Script
from .tts import get_tts


def compare(script: Script, tts_names: list[str], image_names: list[str], outdir: Path, scenes: int = 3) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    picked = script.scenes[:scenes]
    text = " ".join(s.narration for s in picked)
    rows: list[dict] = []

    for name in tts_names:
        row = {"kind": "tts", "provider": name}
        try:
            path = outdir / f"tts_{name}.mp3"
            clip, usage = get_tts(name).synthesize(text, path)
            row.update(file=path.name, seconds=round(usage.seconds, 2), usd=usage.usd,
                       audio_seconds=round(clip.duration, 2), chars=len(text))
        except Exception as error:  # one provider failing should not stop the comparison
            row["error"] = str(error)
        rows.append(row)

    for name in image_names:
        provider = None
        for i, scene in enumerate(picked):
            row = {"kind": "image", "provider": name, "scene": i + 1}
            try:
                provider = provider or get_images(name)
                path = outdir / f"img_{name}_{i + 1}.jpg"
                _, usage = provider.generate(scene.image_prompt, path)
                row.update(file=path.name, seconds=round(usage.seconds, 2), usd=usage.usd)
            except Exception as error:
                row["error"] = str(error)
            rows.append(row)

    (outdir / "compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    page = outdir / "index.html"
    page.write_text(_page(script, text, rows), encoding="utf-8")
    return page


def _page(script: Script, text: str, rows: list[dict]) -> str:
    def cell(row: dict) -> str:
        if "error" in row:
            return f"<p class='err'>실패: {html.escape(row['error'][:300])}</p>"
        if row["kind"] == "tts":
            return (f"<audio controls src='{row['file']}'></audio>"
                    f"<p>{row['audio_seconds']}초 음성 · 생성 {row['seconds']}초 · ${row['usd']:.4f}</p>")
        return f"<img src='{row['file']}'><p>생성 {row['seconds']}초 · ${row['usd']:.3f}</p>"

    tts = "".join(f"<div class='card'><h3>{html.escape(r['provider'])}</h3>{cell(r)}</div>"
                  for r in rows if r["kind"] == "tts")
    providers = sorted({r["provider"] for r in rows if r["kind"] == "image"})
    images = "".join(
        f"<h3>{html.escape(p)}</h3><div class='row'>"
        + "".join(f"<div class='card'>{cell(r)}</div>" for r in rows if r["kind"] == "image" and r["provider"] == p)
        + "</div>"
        for p in providers
    )
    return f"""<!doctype html><meta charset="utf-8"><title>모델 비교</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;max-width:1100px;color:#222}}
.row{{display:flex;gap:12px;flex-wrap:wrap}} .card{{border:1px solid #ddd;border-radius:8px;padding:12px;margin:8px 0}}
img{{width:240px;border-radius:6px}} .err{{color:#b00}} p{{margin:6px 0;font-size:14px}}
</style>
<h1>{html.escape(script.title)}</h1>
<p><b>비교 문장:</b> {html.escape(text)}</p>
<h2>음성 (TTS)</h2><div class='row'>{tts}</div>
<h2>이미지</h2>{images}
<p>가격은 코드에 적힌 근사 단가로 계산한 추정치입니다.</p>
"""
