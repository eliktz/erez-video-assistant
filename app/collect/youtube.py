"""YouTube Data API — free, official, permanent.

Quota: 100 search.list calls/day, which is far more than one creator list needs.
This source keeps working even when a paid scraper breaks.
"""

import httpx

from app.collect.base import Candidate
from app.config import Watchlist

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


class YouTubeSource:
    name = "youtube"

    def __init__(self, api_key: str, *, http: httpx.Client | None = None):
        self._api_key = api_key
        self._http = http or httpx.Client(timeout=30)

    def _search_channel(self, handle: str, since: str) -> list[Candidate]:
        response = self._http.get(
            _SEARCH_URL,
            params={
                "key": self._api_key,
                "channelId": handle,
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
            found.extend(self._search_channel(creator.handle, since))
        return found
