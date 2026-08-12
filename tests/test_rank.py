from app.collect.base import Candidate
from app.digest import rank

NOW = "2026-07-14T12:00:00Z"


def _c(cid, views, posted_at):
    return Candidate(
        id=cid,
        platform="tiktok",
        native_id=cid,
        url=f"https://x/{cid}",
        creator=None,
        caption=None,
        posted_at=posted_at,
        views=views,
        likes=None,
        comments=None,
        source="scraper",
    )


def test_velocity_is_views_per_hour():
    c = _c("a", 12_000, "2026-07-14T00:00:00Z")  # 12 hours old
    assert rank.velocity(c, now=NOW) == 1000.0


def test_velocity_of_brand_new_video_does_not_divide_by_zero():
    c = _c("a", 500, NOW)
    assert rank.velocity(c, now=NOW) > 0


def test_velocity_is_zero_without_data():
    assert rank.velocity(_c("a", None, NOW), now=NOW) == 0.0
    assert rank.velocity(_c("a", 100, None), now=NOW) == 0.0


def test_top_n_ranks_by_velocity_and_dedupes():
    slow = _c("slow", 1_000, "2026-07-13T12:00:00Z")  # 24h -> ~42/h
    fast = _c("fast", 10_000, "2026-07-14T10:00:00Z")  # 2h  -> 5000/h
    got = rank.top_n([slow, fast, fast], n=2, now=NOW)

    assert [c.id for c in got] == ["fast", "slow"]


def test_ranking_orders_collector_shaped_candidates_by_velocity():
    # Erez's PR #15 test-plan ask: rank candidates AS THE COLLECTOR PRODUCES them,
    # not hand-built ones. A topic-search hit climbing fast must beat a fresh
    # watchlist-creator video with few views — collection order must not matter.
    import json
    from pathlib import Path

    from app.collect import youtube
    from app.config import Creator, Watchlist
    from tests.test_collect import _FakeHttp

    creator_search = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    topic_search = {
        "items": [
            {
                "id": {"videoId": "viral9"},
                "snippet": {
                    "publishedAt": "2026-07-13T22:00:00Z",
                    "channelTitle": "Unknown Creator",
                    "title": "Kindness video blowing up",
                },
            }
        ]
    }
    stats = {
        "items": [
            {"id": "abc123", "statistics": {"viewCount": "300"}},  # watchlist creator, slow
            {"id": "viral9", "statistics": {"viewCount": "2000000"}},  # topic hit, climbing
        ]
    }

    class _TwoSearchHttp(_FakeHttp):
        """First search.list call gets the creator payload, the second the topic's."""

        def __init__(self):
            super().__init__(by_url={youtube._VIDEOS_URL: stats})
            self._searches = [creator_search, topic_search]

        def get(self, url, params=None):
            if url == youtube._SEARCH_URL:
                self.calls.append({"url": url, "params": params})
                return type(self)._resp(self._searches.pop(0))
            return super().get(url, params)

        @staticmethod
        def _resp(payload):
            from tests.test_collect import _FakeResponse

            return _FakeResponse(payload)

    source = youtube.YouTubeSource("KEY", http=_TwoSearchHttp())
    got = source.collect(
        Watchlist(creators=[Creator("youtube", "UCxyz")], topics=["kindness"]),
        since="2026-07-12T00:00:00Z",
    )
    picked = rank.top_n(got, n=1, now="2026-07-14T00:00:00Z")

    # The creator video was collected FIRST; the topic video must still win on velocity.
    assert picked[0].id == "youtube:viral9"
