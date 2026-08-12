"""YouTube's own trending chart — what is hot regardless of topic.

The keyword search in youtube.py only finds what we ask about. Erez's trend
radar (2026-07-24) also wants what is trending, period — a song, a challenge,
a news moment. `videos.list(chart=mostPopular)` is YouTube's own chart: one
call, no keywords, and statistics arrive in the same response, so no
follow-up call is needed.
"""

import httpx

from app.collect.base import Candidate

_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class TrendingChart:
    """One region's trending chart.

    region="IL" asks for Israel's chart. region=None omits the filter, so
    YouTube serves its default (US) chart — the closest free thing to a
    "world" chart the API offers. Erez wants the two kept separate: mixing
    them buries the local signal inside the global one.
    """

    def __init__(
        self, api_key: str, *, region: str | None = None, http: httpx.Client | None = None
    ):
        self._api_key = api_key
        self._region = region
        self._http = http or httpx.Client(timeout=30)

    def chart(self, *, max_results: int = 10) -> list[Candidate]:
        params = {
            "key": self._api_key,
            "chart": "mostPopular",
            "part": "snippet,statistics",
            "maxResults": max_results,
        }
        if self._region:
            params["regionCode"] = self._region
        response = self._http.get(_VIDEOS_URL, params=params)
        response.raise_for_status()
        return [self._to_candidate(item) for item in response.json().get("items", [])]

    @staticmethod
    def _to_candidate(item: dict) -> Candidate:
        # Unlike search.list, videos.list returns the id as a plain string.
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        def as_int(key: str) -> int | None:
            value = stats.get(key)
            return int(value) if value is not None else None

        return Candidate(
            id=f"youtube:{item['id']}",
            platform="youtube",
            native_id=item["id"],
            url=f"https://www.youtube.com/watch?v={item['id']}",
            creator=snippet.get("channelTitle"),
            caption=snippet.get("title"),
            posted_at=snippet.get("publishedAt"),
            views=as_int("viewCount"),
            likes=as_int("likeCount"),
            comments=as_int("commentCount"),
            source="trending",
        )
