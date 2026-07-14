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
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        return _FakeResponse(self._payload)


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
