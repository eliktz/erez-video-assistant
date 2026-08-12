import json
from pathlib import Path

from app.collect import base, youtube
from app.config import Creator, Watchlist


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeHttp:
    """Returns `payload` for every call, unless `by_url` maps a URL to its own
    payload — lets one test fake both channels.list and search.list at once."""

    def __init__(self, payload=None, *, by_url=None):
        self._payload = payload
        self._by_url = by_url or {}
        self.calls = []

    def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        payload = self._by_url[url] if url in self._by_url else self._payload
        return _FakeResponse(payload)


def test_candidate_as_row_matches_store_schema():
    c = base.Candidate(
        id="youtube:abc",
        platform="youtube",
        native_id="abc",
        url="https://youtube.com/shorts/abc",
        creator="someone",
        caption="hi",
        posted_at="2026-07-13T10:00:00Z",
        views=10,
        likes=1,
        comments=0,
        source="youtube",
    )
    row = c.as_row()

    assert set(row) == {
        "id",
        "platform",
        "native_id",
        "url",
        "creator",
        "caption",
        "posted_at",
        "views",
        "likes",
        "comments",
        "source",
    }


def test_youtube_source_maps_search_results():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(by_url={youtube._SEARCH_URL: payload, youtube._VIDEOS_URL: {"items": []}})
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "UCxyz")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert len(got) == 1
    assert got[0].id == "youtube:abc123"
    assert got[0].url == "https://www.youtube.com/shorts/abc123"
    assert got[0].creator == "Kindness Daily"
    assert http.calls[0]["params"]["publishedAfter"] == "2026-07-12T00:00:00Z"


def test_youtube_source_skips_non_youtube_creators():
    http = _FakeHttp({"items": []})
    source = youtube.YouTubeSource("KEY", http=http)

    source.collect(
        Watchlist(creators=[Creator("instagram", "erez.v1")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert http.calls == []


def test_youtube_source_resolves_a_handle_before_searching():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(
        by_url={
            youtube._CHANNELS_URL: {"items": [{"id": "UCxyz"}]},
            youtube._SEARCH_URL: payload,
            youtube._VIDEOS_URL: {"items": []},
        }
    )
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "@andrejko.epta")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert len(got) == 1
    channels_call, search_call = http.calls[:2]
    assert channels_call["url"] == youtube._CHANNELS_URL
    assert channels_call["params"]["forHandle"] == "andrejko.epta"
    assert search_call["params"]["channelId"] == "UCxyz"


def test_youtube_source_skips_channels_lookup_for_a_UC_id():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(by_url={youtube._SEARCH_URL: payload, youtube._VIDEOS_URL: {"items": []}})
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "UCxyz")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert len(got) == 1
    urls = [c["url"] for c in http.calls]
    assert youtube._CHANNELS_URL not in urls  # no channels.list for a UC... id
    assert urls[0] == youtube._SEARCH_URL


def test_youtube_source_searches_topics_for_trending_shorts():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(by_url={youtube._SEARCH_URL: payload, youtube._VIDEOS_URL: {"items": []}})
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[], topics=["random acts of kindness"]),
        since="2026-07-12T00:00:00Z",
    )

    assert len(got) == 1
    params = http.calls[0]["params"]
    assert params["q"] == "random acts of kindness"
    assert params["videoDuration"] == "short"
    assert params["order"] == "viewCount"  # trend discovery: already climbing, not just new
    assert params["publishedAfter"] == "2026-07-12T00:00:00Z"


def test_youtube_source_skips_an_unresolvable_handle_without_raising():
    http = _FakeHttp(
        by_url={
            youtube._CHANNELS_URL: {"items": []},
        }
    )
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "@nobody")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert got == []
    assert len(http.calls) == 1  # never got to search.list


def test_collect_fills_real_view_counts():
    # search.list never returns statistics; a follow-up videos.list must fill them —
    # otherwise ranking degenerates to collection order (Erez's PR #15 diagnosis).
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    stats = {
        "items": [
            {
                "id": "abc123",
                "statistics": {"viewCount": "120000", "likeCount": "500", "commentCount": "20"},
            }
        ]
    }
    http = _FakeHttp(by_url={youtube._SEARCH_URL: payload, youtube._VIDEOS_URL: stats})
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "UCxyz")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert got[0].views == 120000
    assert got[0].likes == 500
    assert got[0].comments == 20
    videos_call = next(c for c in http.calls if c["url"] == youtube._VIDEOS_URL)
    assert videos_call["params"]["part"] == "statistics"
    assert "abc123" in videos_call["params"]["id"]


def test_fill_statistics_batches_fifty_ids_per_call():
    http = _FakeHttp(by_url={youtube._VIDEOS_URL: {"items": []}})
    source = youtube.YouTubeSource("KEY", http=http)
    many = [
        base.Candidate(
            id=f"youtube:v{i}",
            platform="youtube",
            native_id=f"v{i}",
            url=f"https://www.youtube.com/shorts/v{i}",
            creator=None,
            caption=None,
            posted_at=None,
            views=None,
            likes=None,
            comments=None,
            source="youtube",
        )
        for i in range(60)
    ]

    source._fill_statistics(many)

    videos_calls = [c for c in http.calls if c["url"] == youtube._VIDEOS_URL]
    assert len(videos_calls) == 2  # 60 unique ids -> 50 + 10


def test_a_video_with_no_stats_keeps_none_and_sinks_in_ranking():
    from app.digest import rank

    http = _FakeHttp(by_url={youtube._VIDEOS_URL: {"items": []}})
    source = youtube.YouTubeSource("KEY", http=http)
    candidate = base.Candidate(
        id="youtube:gone",
        platform="youtube",
        native_id="gone",
        url="https://www.youtube.com/shorts/gone",
        creator=None,
        caption=None,
        posted_at="2026-07-12T00:00:00Z",
        views=None,
        likes=None,
        comments=None,
        source="youtube",
    )

    (filled,) = source._fill_statistics([candidate])

    assert filled.views is None
    assert rank.velocity(filled, now="2026-07-12T10:00:00Z") == 0.0
