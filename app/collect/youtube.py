"""YouTube Data API — free, official, permanent.

Quota: 100 search.list calls/day, which is far more than one creator list needs.
This source keeps working even when a paid scraper breaks.
"""

import logging

import httpx

from app.collect.base import Candidate
from app.config import Watchlist

log = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


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

    def collect(self, watchlist: Watchlist, *, since: str) -> list[Candidate]:
        found: list[Candidate] = []
        for creator in watchlist.creators:
            if creator.platform != "youtube":
                continue
            channel_id = self._resolve_channel_id(creator.handle)
            if channel_id is None:
                continue
            found.extend(self._search_channel(channel_id, since))
        return found
