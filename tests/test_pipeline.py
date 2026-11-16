"""Offline checks: mock providers only, no API keys or network."""

from __future__ import annotations

import json

from shorts.cli import main
from shorts.compare import compare
from shorts.images import MockImages
from shorts.media import probe
from shorts.models import Script
from shorts.pipeline import build_video, load_script
from shorts.script import SCRIPT_SCHEMA, MockScriptWriter
from shorts.subtitles import MAX_CHARS, chunk, time_scene
from shorts.tts import MockTTS


def test_chunk_keeps_lines_short_and_loses_no_words():
    text = "조선 시대 왕들은 하루에 다섯 끼를 먹었다고 알려져 있지만, 실제 기록은 조금 다릅니다."
    pieces = chunk(text)
    assert all(len(p) <= MAX_CHARS or " " not in p for p in pieces)
    assert " ".join(pieces).split() == text.split()


def test_captions_fill_the_scene_exactly():
    captions = time_scene("첫 문장입니다. 두 번째 문장은 조금 더 깁니다.", start=2.0, length=4.0)
    assert captions[0].start == 2.0
    assert abs(captions[-1].end - 6.0) < 1e-9
    assert all(a.end == b.start for a, b in zip(captions, captions[1:]))


def test_schema_matches_model():
    # The JSON schema sent to Claude and the pydantic model must accept the same shape.
    sample = {"title": "t", "hook": "h", "scenes": [{"narration": "n", "image_prompt": "p"}]}
    assert set(SCRIPT_SCHEMA["required"]) == set(sample)
    Script.model_validate(sample)


def test_mock_pipeline_renders_vertical_video(tmp_path):
    script, usage = MockScriptWriter().write("라면 끓이는 순서")
    final = build_video(script, MockTTS(), MockImages(), tmp_path, prior_usage=[usage])

    info = probe(final)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in info["streams"])

    report = json.loads((tmp_path / "report.json").read_text())
    assert abs(float(info["format"]["duration"]) - report["video_seconds"]) < 0.5
    assert load_script(tmp_path / "script.json") == script


def test_cli_make_then_render_edited_script(tmp_path):
    out = tmp_path / "run"
    main(["make", "--topic", "고양이가 상자를 좋아하는 이유", "--writer", "mock",
          "--tts", "mock", "--images", "mock", "--out", str(out)])
    assert (out / "final.mp4").exists()

    # The user edits the script, then renders again from the edited file.
    script = load_script(out / "script.json")
    script.scenes[1].narration = "사실 상자는 고양이에게 안전한 은신처입니다."
    (out / "script.json").write_text(script.model_dump_json(), encoding="utf-8")
    main(["render", "--script", str(out / "script.json"), "--tts", "mock", "--images", "mock",
          "--out", str(tmp_path / "edited")])
    assert load_script(tmp_path / "edited" / "script.json").scenes[1].narration.startswith("사실 상자는")


def test_compare_reports_failures_without_stopping(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    script, _ = MockScriptWriter().write("비교")
    page = compare(script, ["mock", "openai"], ["mock"], tmp_path, scenes=2)
    rows = json.loads((tmp_path / "compare.json").read_text())
    assert {r["provider"] for r in rows if r["kind"] == "tts" and "error" not in r} == {"mock"}
    assert any(r["provider"] == "openai" and "error" in r for r in rows)
    assert page.exists()
