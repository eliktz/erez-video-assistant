"""Send a whole video to Gemini and get back structured analysis.

Gemini is the only cheap model that ingests video directly, and it handles Hebrew.
Roughly half a cent per 60-second video.
"""

import json
import time

# gemini-2.5-flash was retired for new API keys (it 404s: "no longer available to new users").
# gemini-3.5-flash is the current cheap flash that ingests whole video and handles Hebrew well —
# verified live on 2026-07-16 against a real reel. If this ever 404s, list live models with
# `client.models.list()` and pick a current *-flash that supports generateContent.
MODEL = "gemini-3.5-flash"
RUBRIC_VERSION = "v1"

# Gemini accepts a video upload instantly, then processes it in the background. Calling
# generate_content while the file is still PROCESSING returns 400 FAILED_PRECONDITION,
# so every real video must be waited on. Fakes return no state and skip this entirely.
_POLL_SECONDS = 2
_POLL_TIMEOUT_SECONDS = 180

# Verified 2026-07-13: $0.30 per 1M input tokens on gemini-2.5-flash.
# Video tokenizes at roughly 100-300 tokens/sec depending on resolution; 263 is
# mid-range. Treat the result as order-of-magnitude, not an invoice.
_USD_PER_INPUT_TOKEN = 0.30 / 1_000_000
_TOKENS_PER_SECOND = 263


def estimate_cost(seconds: float) -> float:
    """Rough input cost for analyzing a video of this length."""
    return seconds * _TOKENS_PER_SECOND * _USD_PER_INPUT_TOKEN


def _strip_fences(text: str) -> str:
    """Models sometimes wrap JSON in ```json fences. Take the JSON either way."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _state_of(uploaded) -> str:
    """The SDK reports state as an enum; be tolerant of a plain string too."""
    state = getattr(uploaded, "state", None)
    if state is None:
        return ""
    return getattr(state, "name", None) or str(state)


def _wait_until_active(client, uploaded, *, sleep=time.sleep):
    """Wait for Gemini to finish processing the upload before we ask about it."""
    waited = 0
    while _state_of(uploaded) == "PROCESSING":
        if waited >= _POLL_TIMEOUT_SECONDS:
            raise RuntimeError(f"Gemini still processing {uploaded.name} after {waited}s")
        sleep(_POLL_SECONDS)
        waited += _POLL_SECONDS
        uploaded = client.files.get(name=uploaded.name)
    if _state_of(uploaded) == "FAILED":
        raise RuntimeError(f"Gemini could not process the video: {uploaded.name}")
    return uploaded


def analyze_video(video_path: str, rubric: str, client) -> dict:
    """Analyze one video against the rubric. Returns the parsed JSON payload.

    `client` is a google.genai Client (injected so tests need no API key).
    Positional-or-keyword by design: callers inject a stand-in with the same shape.
    """
    uploaded = _wait_until_active(client, client.files.upload(file=video_path))
    response = client.models.generate_content(
        model=MODEL,
        contents=[uploaded, rubric],
    )
    return json.loads(_strip_fences(response.text))


def build_client(api_key: str):
    """Real client. Kept separate so every other function stays testable."""
    from google import genai

    return genai.Client(api_key=api_key)
