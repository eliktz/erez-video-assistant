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
        "id", "platform", "native_id", "url", "creator", "caption",
        "posted_at", "views", "likes", "comments", "source",
    }


def test_youtube_source_maps_search_results():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(payload)
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
        }
    )
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "@andrejko.epta")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert len(got) == 1
    channels_call, search_call = http.calls
    assert channels_call["url"] == youtube._CHANNELS_URL
    assert channels_call["params"]["forHandle"] == "andrejko.epta"
    assert search_call["params"]["channelId"] == "UCxyz"


def test_youtube_source_skips_channels_lookup_for_a_UC_id():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(payload)
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "UCxyz")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert len(got) == 1
    assert len(http.calls) == 1  # only the search call, no channels.list
    assert http.calls[0]["url"] == youtube._SEARCH_URL


def test_youtube_source_searches_topics_for_trending_shorts():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(payload)
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
