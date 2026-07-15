"""Turn structured analysis into Hebrew Erez wants to read.

Gemini understands the video; Claude writes the words. Both adversarial judges
flagged bland Hebrew prose as the single likeliest reason Erez stops opening the
digest — which would kill the project. That is why a second vendor is here.
"""

import json
from dataclasses import dataclass

MODEL = "claude-opus-4-8"

# Verified 2026-07-13: claude-opus-4-8 is $5/1M input, $25/1M output.
_USD_PER_INPUT_TOKEN = 5.0 / 1_000_000
_USD_PER_OUTPUT_TOKEN = 25.0 / 1_000_000


def estimate_cost(usage) -> float:
    """Cost of one Claude call from its usage object."""
    return usage.input_tokens * _USD_PER_INPUT_TOKEN + usage.output_tokens * _USD_PER_OUTPUT_TOKEN


def _text_of(message) -> str:
    """Pull the text out of a response. content is a list of typed blocks."""
    for block in message.content:
        if block.type == "text":
            return block.text
    return ""


def _ask(client, *, system: str, prompt: str, max_tokens: int):
    return client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
    )


@dataclass(frozen=True)
class Written:
    """What Claude wrote, and what that call cost — so the caller can record the spend."""

    text: str
    cost_usd: float


def _write(client, *, system: str, prompt: str, max_tokens: int) -> Written:
    message = _ask(client, system=system, prompt=prompt, max_tokens=max_tokens)
    return Written(text=_text_of(message), cost_usd=estimate_cost(message.usage))


def reply_about_video(analysis: dict, persona: str, client) -> Written:
    """One video's analysis -> a Hebrew chat reply in Erez's bot's voice."""
    prompt = "הנה הניתוח הגולמי של הסרטון. תסביר לארז בעברית מה מעניין פה.\n\n" + json.dumps(
        analysis, ensure_ascii=False, indent=2
    )
    return _write(client, system=persona, prompt=prompt, max_tokens=2000)


def write_digest(items: list[dict], template: str, client) -> Written:
    """The morning digest: several analyses -> one Hebrew report."""
    prompt = "הנה הסרטונים של הבוקר עם הניתוח של כל אחד.\n\n" + json.dumps(
        items, ensure_ascii=False, indent=2
    )
    return _write(client, system=template, prompt=prompt, max_tokens=4000)


def build_client(api_key: str):
    import anthropic

    return anthropic.Anthropic(api_key=api_key)
