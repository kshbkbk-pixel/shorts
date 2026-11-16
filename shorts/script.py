"""Turn a topic into a 60-second script split into scenes."""

from __future__ import annotations

import json
import time
from typing import Protocol

from .config import env
from .models import Scene, Script, Usage

# USD per million tokens. Approximate; check the provider's pricing page.
CLAUDE_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

SYSTEM_PROMPT = """너는 한국어 유튜브 쇼츠(세로 60초) 대본 작가다.

규칙:
- 전체 내레이션은 공백 포함 350~450자. 읽으면 50~60초가 된다.
- 장면은 8~12개. 장면 하나는 한두 문장, 장면 길이는 비슷하게.
- 첫 장면은 2초 안에 궁금증을 만드는 훅이다. hook 필드에도 같은 문장을 넣는다.
- 마지막 장면은 결론이나 반전으로 끝낸다. "구독과 좋아요" 같은 상투적 마무리는 쓰지 않는다.
- 사실 주장은 널리 확인된 것만 쓰고, 불확실하면 "~라고 알려져 있다"처럼 표현한다.
- 같은 주제라도 뻔한 나열 대신 하나의 관점이나 이야기 흐름을 잡는다.
- image_prompt는 영어로, 그 장면을 보여주는 세로 일러스트 묘사다. 실존 인물, 브랜드 로고, 화면 속 글자는 넣지 않는다."""

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "image_prompt": {"type": "string"},
                },
                "required": ["narration", "image_prompt"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "hook", "scenes"],
    "additionalProperties": False,
}


class ScriptWriter(Protocol):
    name: str

    def write(self, topic: str, genre: str = "", tone: str = "") -> tuple[Script, Usage]: ...


class ClaudeScriptWriter:
    """Writes the script with Claude, returning schema-valid JSON."""

    def __init__(self, model: str | None = None, effort: str | None = None):
        import anthropic  # imported here so mock runs need no API package

        self.model = model or env("SHORTS_LLM_MODEL", "claude-opus-5-5")
        self.effort = effort or env("SHORTS_LLM_EFFORT", "low")
        self.client = anthropic.Anthropic()
        self.name = f"claude:{self.model}"

    def write(self, topic: str, genre: str = "", tone: str = "") -> tuple[Script, Usage]:
        request = f"주제: {topic}"
        if genre:
            request += f"\n장르: {genre}"
        if tone:
            request += f"\n톤: {tone}"

        started = time.monotonic()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": request}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA},
            },
            # If a safety classifier declines, the API retries on a fallback model in the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        elapsed = time.monotonic() - started

        if response.stop_reason == "refusal":
            raise RuntimeError(f"대본 생성이 거절되었습니다: {response.stop_details}")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("대본이 max_tokens 에서 잘렸습니다")

        text = next(block.text for block in response.content if block.type == "text")
        script = Script.model_validate(json.loads(text))

        in_price, out_price = CLAUDE_PRICES.get(self.model, (0.0, 0.0))
        usd = (response.usage.input_tokens * in_price + response.usage.output_tokens * out_price) / 1e6
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return script, Usage(provider=self.name, kind="llm", units=tokens, usd=usd, seconds=elapsed)


class MockScriptWriter:
    """Offline writer for tests and pipeline checks. Makes a fixed 4-scene script."""

    name = "mock"

    def write(self, topic: str, genre: str = "", tone: str = "") -> tuple[Script, Usage]:
        lines = [
            f"{topic}, 사실 대부분이 잘못 알고 있습니다.",
            "처음 이 이야기가 퍼진 건 아주 오래전입니다.",
            "그런데 실제로 확인해 보면 전혀 다른 결과가 나옵니다.",
            "결국 중요한 건 숫자가 아니라 맥락이었습니다.",
        ]
        scenes = [Scene(narration=line, image_prompt=f"illustration, scene {i + 1}") for i, line in enumerate(lines)]
        script = Script(title=topic, hook=lines[0], scenes=scenes)
        return script, Usage(provider=self.name, kind="llm", units=0, usd=0.0, seconds=0.0)


def get_writer(name: str) -> ScriptWriter:
    if name == "mock":
        return MockScriptWriter()
    if name == "claude":
        return ClaudeScriptWriter()
    raise ValueError(f"알 수 없는 대본 생성기: {name}")
