"""Find new creators in the style Erez already tracks (Track 4, plan 2026-07-25).

Automates the hunt he does by hand: search the hashtags his tracked creators
use in their captions, check each result channel's size, show one standout
video. The bot only SUGGESTS — nothing joins config/watchlist.yaml until Erez
approves it and adds it there himself (or asks Elik). That human approval step
is how andr3w_wave and KINDNESS MAN were found; the bot just does the searching.
"""

import logging
from dataclasses import dataclass, replace

import httpx

log = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


@dataclass(frozen=True)
class ChannelCandidate:
    channel_id: str
    title: str
    handle: str | None  # the @name, e.g. "@andr3w_wave"
    subscribers: int | None
    url: str
    standout_title: str | None
    standout_url: str | None


def _candidate(info: dict) -> ChannelCandidate:
    snippet = info.get("snippet", {})
    subs = info.get("statistics", {}).get("subscriberCount")
    return ChannelCandidate(
        channel_id=info["id"],
        title=snippet.get("title") or "",
        handle=snippet.get("customUrl"),
        subscribers=int(subs) if subs is not None else None,
        url=f"https://www.youtube.com/channel/{info['id']}",
        standout_title=None,
        standout_url=None,
    )


class ChannelDiscovery:
    def __init__(self, api_key: str, *, http: httpx.Client | None = None):
        self._api_key = api_key
        self._http = http or httpx.Client(timeout=30)

    def _get(self, url: str, params: dict) -> dict:
        response = self._http.get(url, params={"key": self._api_key, **params})
        response.raise_for_status()
        return response.json()

    def _channel_ids(self, hashtag: str) -> list[str]:
        data = self._get(
            _SEARCH_URL,
            {
                "q": f"#{hashtag.lstrip('#')}",
                "part": "snippet",
                "type": "channel",
                "maxResults": 5,
            },
        )
        return [item["id"]["channelId"] for item in data.get("items", [])]

    def _channels_info(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        data = self._get(_CHANNELS_URL, {"id": ",".join(ids), "part": "snippet,statistics"})
        return data.get("items", [])

    def _standout(self, channel_id: str) -> tuple[str | None, str | None]:
        """The channel's most-viewed short — the fastest way to judge a creator."""
        data = self._get(
            _SEARCH_URL,
            {
                "channelId": channel_id,
                "part": "snippet",
                "type": "video",
                "order": "viewCount",
                "videoDuration": "short",
                "maxResults": 1,
            },
        )
        items = data.get("items", [])
        if not items:
            return None, None
        video_id = items[0]["id"]["videoId"]
        return items[0]["snippet"].get("title"), f"https://www.youtube.com/shorts/{video_id}"

    def _with_standout(self, candidate: ChannelCandidate) -> ChannelCandidate:
        title, url = self._standout(candidate.channel_id)
        return replace(candidate, standout_title=title, standout_url=url)

    def find(
        self, hashtags, *, known_handles=(), min_subscribers: int = 0, limit: int = 5
    ) -> list[ChannelCandidate]:
        """Up to `limit` channels worth showing Erez, biggest first.

        Channels already in the watchlist are dropped (matched on the @handle),
        and standout videos are fetched only for the final picks — each of
        those is a whole search.list call, the expensive YouTube quota unit.
        """
        ids: list[str] = []
        for hashtag in hashtags:
            ids += [i for i in self._channel_ids(hashtag) if i not in ids]
        known = {h.lstrip("@").lower() for h in known_handles}
        found = []
        for info in self._channels_info(ids):
            candidate = _candidate(info)
            handle = (candidate.handle or "").lstrip("@").lower()
            if handle in known or (candidate.subscribers or 0) < min_subscribers:
                continue
            found.append(candidate)
        found.sort(key=lambda c: c.subscribers or 0, reverse=True)
        return [self._with_standout(c) for c in found[:limit]]


def message(candidates: list[ChannelCandidate]) -> str:
    """The chat reply. Suggests only — adding to the watchlist stays a human step."""
    if not candidates:
        return (
            "לא מצאתי הפעם ערוצים חדשים ששווים הצעה. "
            "נסה שוב מחר, או תוסיף האשטגים ב-config/watchlist.yaml."
        )
    lines = ["מצאתי ערוצים בסגנון שאתה עוקב אחריו 🔎", ""]
    for c in candidates:
        subs = f"{c.subscribers:,}" if c.subscribers is not None else "?"
        lines.append(f"🎬 {c.title} — {subs} מנויים")
        if c.standout_url:
            lines.append(f"   הסרטון הבולט: {c.standout_title or ''}")
            lines.append(f"   {c.standout_url}")
        lines.append(f"   הערוץ: {c.url}")
        lines.append("")
    lines.append("רוצה לעקוב אחרי אחד מהם? תוסיף אותו ל-config/watchlist.yaml, או תבקש מאליק.")
    return "\n".join(lines)
