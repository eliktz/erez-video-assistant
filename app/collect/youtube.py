"""YouTube Data API — free, official, permanent.

Quota: 100 search.list calls/day, which is far more than one creator list needs.
This source keeps working even when a paid scraper breaks.
"""

import logging
from dataclasses import replace

import httpx

from app.collect.base import Candidate
from app.config import Watchlist

log = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeSource:
    name = "youtube"

    def __init__(self, api_key: str, *, http: httpx.Client | None = None):
        self._api_key = api_key
        self._http = http or httpx.Client(timeout=30)
        self._channel_id_cache: dict[str, str | None] = {}

    def _resolve_channel_id(self, handle: str) -> str | None:
        """Erez's watchlist documents `handle` as the @name, not a UC... id.

        Accept both: a UC... id is used as-is; anything else is resolved once
        via channels.list and cached, so one creator costs one lookup per run.
        """
        if handle.startswith("UC"):
            return handle
        if handle in self._channel_id_cache:
            return self._channel_id_cache[handle]

        response = self._http.get(
            _CHANNELS_URL,
            params={"key": self._api_key, "forHandle": handle.lstrip("@"), "part": "id"},
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        channel_id = items[0]["id"] if items else None
        if channel_id is None:
            log.warning("Could not resolve YouTube handle %r to a channel; skipping it", handle)
        self._channel_id_cache[handle] = channel_id
        return channel_id

    def _search_channel(self, channel_id: str, since: str) -> list[Candidate]:
        response = self._http.get(
            _SEARCH_URL,
            params={
                "key": self._api_key,
                "channelId": channel_id,
                "part": "snippet",
                "type": "video",
                "order": "date",
                "publishedAfter": since,
                "maxResults": 10,
            },
        )
        response.raise_for_status()
        return [self._to_candidate(item) for item in response.json().get("items", [])]

    @staticmethod
    def _to_candidate(item: dict) -> Candidate:
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        return Candidate(
            id=f"youtube:{video_id}",
            platform="youtube",
            native_id=video_id,
            url=f"https://www.youtube.com/shorts/{video_id}",
            creator=snippet.get("channelTitle"),
            caption=snippet.get("title"),
            posted_at=snippet.get("publishedAt"),
            views=None,
            likes=None,
            comments=None,
            source="youtube",
        )

    def _search_topic(self, topic: str, since: str) -> list[Candidate]:
        """Trend discovery: the most-viewed shorts about a topic in the window.

        Ordered by viewCount on purpose — the digest wants what is already
        taking off, not just what is newest.
        """
        response = self._http.get(
            _SEARCH_URL,
            params={
                "key": self._api_key,
                "q": topic,
                "part": "snippet",
                "type": "video",
                "videoDuration": "short",
                "order": "viewCount",
                "publishedAfter": since,
                "maxResults": 10,
            },
        )
        response.raise_for_status()
        return [self._to_candidate(item) for item in response.json().get("items", [])]

    def _fill_statistics(self, candidates: list[Candidate]) -> list[Candidate]:
        """Real view counts for every candidate, batched 50 per call (1 quota unit).

        search.list never returns statistics, so without this every candidate had
        views=None, velocity tied at 0.0, and ranking degenerated to collection
        order — the bug where the digest only ever showed watchlist creators and
        no topic result could reach it (Erez's diagnosis, follow-ups #1).
        A video with no stats (deleted, private) keeps views=None and sinks.
        """
        stats: dict[str, dict] = {}
        ids = list({c.native_id for c in candidates})
        for start in range(0, len(ids), 50):
            response = self._http.get(
                _VIDEOS_URL,
                params={
                    "key": self._api_key,
                    "id": ",".join(ids[start : start + 50]),
                    "part": "statistics",
                },
            )
            response.raise_for_status()
            for item in response.json().get("items", []):
                stats[item["id"]] = item.get("statistics", {})
        return [self._with_stats(c, stats.get(c.native_id)) for c in candidates]

    @staticmethod
    def _with_stats(candidate: Candidate, stat: dict | None) -> Candidate:
        if not stat:
            return candidate

        def as_int(key: str) -> int | None:
            value = stat.get(key)
            return int(value) if value is not None else None

        return replace(
            candidate,
            views=as_int("viewCount"),
            likes=as_int("likeCount"),
            comments=as_int("commentCount"),
        )

    def collect(self, watchlist: Watchlist, *, since: str) -> list[Candidate]:
        found: list[Candidate] = []
        for creator in watchlist.creators:
            if creator.platform != "youtube":
                continue
            channel_id = self._resolve_channel_id(creator.handle)
            if channel_id is None:
                continue
            found.extend(self._search_channel(channel_id, since))
        for topic in watchlist.topics:
            found.extend(self._search_topic(topic, since))
        return self._fill_statistics(found) if found else found
