"""The bot: Erez sends a link, gets Hebrew analysis back.

This ships before the digest on purpose. It needs no data vendor, and it proves
the one assumption everything else rests on: that the Hebrew analysis is good
enough that Erez wants more of it.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.analyze import fetch, gemini
from app.store import usage, videos

_URL_PATTERNS = [
    (re.compile(r"instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)"), "instagram"),
    (re.compile(r"tiktok\.com/.*?/video/(\d+)"), "tiktok"),
    (re.compile(r"(?:youtube\.com/shorts/|youtu\.be/)([A-Za-z0-9_-]+)"), "youtube"),
    (re.compile(r"youtube\.com/watch\?v=([A-Za-z0-9_-]+)"), "youtube"),
]

URL_RE = re.compile(r"https?://\S+")


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Deps:
    """Everything the pipeline needs, injected so tests need no keys and no network."""

    conn: object
    gemini_client: object
    claude_client: object
    rubric: str
    persona: str
    work_dir: str
    now: Callable[[], str] = utc_now
    download: Callable = fetch.download
    analyze: Callable = None
    compose_reply: Callable = None


def video_id_from_url(url: str) -> str | None:
    """Stable id across tracking params: 'instagram:DY2QmhAoF-z'."""
    for pattern, platform in _URL_PATTERNS:
        match = pattern.search(url)
        if match:
            return f"{platform}:{match.group(1)}"
    return None


def _store_video(deps: Deps, video_id: str, url: str) -> None:
    platform, native_id = video_id.split(":", 1)
    videos.upsert_video(
        deps.conn,
        {
            "id": video_id,
            "platform": platform,
            "native_id": native_id,
            "url": url,
            "creator": None,
            "caption": None,
            "posted_at": None,
            "views": None,
            "likes": None,
            "comments": None,
            "source": "on_demand",
        },
        now=deps.now(),
    )


def analyze_url(url: str, *, deps: Deps) -> str:
    """The whole on-demand path. Returns Hebrew text safe to send to Erez."""
    video_id = video_id_from_url(url)
    if video_id is None:
        return "לא זיהיתי את הלינק. שלח לי לינק לרילס, טיקטוק או שורטס."

    _store_video(deps, video_id, url)

    analysis = videos.get_analysis(deps.conn, video_id, gemini.RUBRIC_VERSION)
    if analysis is None:
        try:
            result = deps.download(url, deps.work_dir)
        except fetch.FetchError:
            return "לא הצלחתי להוריד את הסרטון. נסה לשלוח לי את הקובץ עצמו."

        analyze = deps.analyze or gemini.analyze_video
        analysis = analyze(result.path, deps.rubric, deps.gemini_client)
        videos.save_analysis(deps.conn, video_id, gemini.RUBRIC_VERSION, analysis, now=deps.now())
        usage.record(
            deps.conn,
            "gemini",
            "analyze_video",
            1,
            gemini.estimate_cost(result.duration_seconds),
            now=deps.now(),
        )

    from app.digest import compose

    compose_reply = deps.compose_reply or compose.reply_about_video
    return compose_reply(analysis, deps.persona, deps.claude_client)
