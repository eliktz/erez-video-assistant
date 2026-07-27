"""Turn structured analysis into Hebrew Erez wants to read.

Gemini both understands the video AND writes the words. We checked on 2026-07-16,
against one of Erez's own reels, that its Hebrew is good enough that a second vendor
is not needed — one model, one key, one bill. It also means Erez's dev bot works with
just the spend-capped Gemini key, and nothing here needs an Anthropic account.
"""

import json
from dataclasses import dataclass

from app.analyze import gemini


@dataclass(frozen=True)
class Written:
    """What Gemini wrote, and what that call cost — so the caller can record the spend."""

    text: str
    cost_usd: float


def estimate_cost(usage) -> float:
    """Cost of one Gemini text call from its usage_metadata.

    Delegates to gemini.cost_from_usage — one place owns the rates, and it already
    counts thinking tokens (billed at the output rate, reported separately).
    """
    return gemini.cost_from_usage(usage)


# What Erez sees if Gemini returns no usable text (a safety block or a truncated reply).
_NO_TEXT = "לא הצלחתי לנסח תשובה על הסרטון הזה. נסה שוב, או שלח סרטון אחר."


def _text_of(response) -> str:
    """Gemini's .text is None (or raises) when a response carries no text part. Never let
    that reach Erez as an empty message — which python-telegram-bot rejects anyway."""
    try:
        return (response.text or "").strip()
    except Exception:
        return ""


def _write(client, *, system: str, prompt: str) -> Written:
    """One Gemini text call. system + prompt go in as one turn, like the spike proved.

    Goes through gemini.generate so an overloaded model falls back instead of failing.
    """
    response = gemini.generate(client, [f"{system}\n\n{prompt}"])
    text = _text_of(response) or _NO_TEXT
    return Written(text=text, cost_usd=estimate_cost(response.usage_metadata))


def reply_about_video(analysis: dict, persona: str, client) -> Written:
    """One video's analysis -> a Hebrew chat reply in Erez's bot's voice."""
    prompt = "הנה הניתוח הגולמי של הסרטון. תסביר לארז בעברית מה מעניין פה.\n\n" + json.dumps(
        analysis, ensure_ascii=False, indent=2
    )
    return _write(client, system=persona, prompt=prompt)


def write_digest(items: list[dict], template: str, client) -> Written:
    """The morning digest: several analyses -> one Hebrew report."""
    prompt = "הנה הסרטונים של הבוקר עם הניתוח של כל אחד.\n\n" + json.dumps(
        items, ensure_ascii=False, indent=2
    )
    return _write(client, system=template, prompt=prompt)


def pitch_ideas(analyses: list[dict], template: str, client) -> Written:
    """/idea: recent video analyses -> concrete Hebrew video ideas for Erez."""
    prompt = "הנה ניתוחים של סרטונים מרגשים/ויראליים שראיתי לאחרונה.\n\n" + json.dumps(
        analyses, ensure_ascii=False, indent=2
    )
    return _write(client, system=template, prompt=prompt)
