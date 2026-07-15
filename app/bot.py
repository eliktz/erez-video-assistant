"""The bot: Erez sends a link, gets Hebrew analysis back.

This ships before the digest on purpose. It needs no data vendor, and it proves
the one assumption everything else rests on: that the Hebrew analysis is good
enough that Erez wants more of it.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from app.analyze import fetch, gemini
from app.store import usage, videos

# Only these hosts are real video platforms. Anything else is not ours to fetch.
_ALLOWED_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}

_URL_PATTERNS = [
    (re.compile(r"instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)"), "instagram"),
    (re.compile(r"tiktok\.com/.*?/video/(\d+)"), "tiktok"),
    (re.compile(r"(?:youtube\.com/shorts/|youtu\.be/)([A-Za-z0-9_-]+)"), "youtube"),
    (re.compile(r"youtube\.com/watch\?v=([A-Za-z0-9_-]+)"), "youtube"),
]

URL_RE = re.compile(r"https?://\S+")


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_authorized(chat_id: int, allowed_chat_ids) -> bool:
    """Only Erez (and Elik, for admin) may use the bot. Everyone else is ignored.

    A Telegram bot answers whoever messages it. Without this check, anyone who
    finds the bot's handle could send it links and spend our Gemini and Claude
    budget — and read our spend with /costs.
    """
    return chat_id in allowed_chat_ids


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


def _host_is_a_platform(url: str) -> bool:
    """Is this really Instagram/TikTok/YouTube, or just a URL shaped like one?"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    return (parsed.hostname or "").lower() in _ALLOWED_HOSTS


def video_id_from_url(url: str) -> str | None:
    """Stable id across tracking params: 'instagram:DY2QmhAoF-z'.

    The host is checked first, on purpose. The patterns below match anywhere in the
    string, so 'http://127.0.0.1:6379/youtube.com/shorts/x' looks like a Short — and
    we hand the ORIGINAL url to yt-dlp, which would happily fetch it. Checking the
    host keeps us from being told to make requests to somewhere we should not.
    """
    if not _host_is_a_platform(url):
        return None
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


def costs_message(conn, *, month: str) -> str:
    """Spend so far this month, in chat, before the credit card says anything."""
    rows = usage.month_to_date(conn, month)
    if not rows:
        return f"עדיין לא הוצאנו כלום ב-{month}."
    lines = [f"💰 ההוצאות ב-{month}:", ""]
    total = 0.0
    for row in rows:
        total += row["cost_usd"]
        lines.append(f"  {row['provider']}: ${row['cost_usd']:.2f} ({row['calls']} קריאות)")
    lines += ["", f"סה״כ: ${total:.2f}"]
    return "\n".join(lines)
