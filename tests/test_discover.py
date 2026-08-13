from app.collect import discover
from tests.test_collect import _FakeResponse


class _RoutedHttp:
    """Route each request to a payload by URL + params — /discover mixes channel
    searches, a channels.list stats call, and per-channel standout searches."""

    def __init__(self, router):
        self._router = router
        self.calls = []

    def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        return _FakeResponse(self._router(url, params))


def _channel_item(cid):
    return {"id": {"channelId": cid}, "snippet": {"title": f"t-{cid}"}}


def _info(cid, title, handle, subs):
    return {
        "id": cid,
        "snippet": {"title": title, "customUrl": handle},
        "statistics": {"subscriberCount": str(subs)},
    }


def _router(channel_search, channels_info):
    def route(url, params):
        if url == discover._SEARCH_URL and params.get("type") == "channel":
            return channel_search
        if url == discover._SEARCH_URL and params.get("type") == "video":
            return {"items": [{"id": {"videoId": "vid9"}, "snippet": {"title": "Best short"}}]}
        if url == discover._CHANNELS_URL:
            return channels_info
        raise AssertionError(f"unexpected call: {url} {params}")

    return route


def test_find_maps_channels_and_fetches_a_standout_short():
    http = _RoutedHttp(
        _router(
            {"items": [_channel_item("UC1")]},
            {"items": [_info("UC1", "Kindness Man", "@kindnessman", 500_000)]},
        )
    )
    finder = discover.ChannelDiscovery("KEY", http=http)

    got = finder.find(["actsofkindness"])

    assert len(got) == 1
    assert got[0].title == "Kindness Man"
    assert got[0].subscribers == 500_000
    assert got[0].url == "https://www.youtube.com/channel/UC1"
    assert got[0].standout_url == "https://www.youtube.com/shorts/vid9"
    standout = [c for c in http.calls if (c["params"] or {}).get("type") == "video"]
    assert standout[0]["params"]["order"] == "viewCount"  # judge by their best, not newest


def test_find_skips_channels_erez_already_tracks():
    http = _RoutedHttp(
        _router(
            {"items": [_channel_item("UC1"), _channel_item("UC2")]},
            {
                "items": [
                    _info("UC1", "Andrew", "@Andr3w_Wave", 11_600_000),
                    _info("UC2", "New Face", "@newface", 90_000),
                ]
            },
        )
    )
    finder = discover.ChannelDiscovery("KEY", http=http)

    got = finder.find(["kindness"], known_handles=["andr3w_wave"])

    assert [c.title for c in got] == ["New Face"]  # already-tracked is dropped, case-insensitive


def test_find_filters_small_channels_and_sorts_biggest_first():
    http = _RoutedHttp(
        _router(
            {"items": [_channel_item("UC1"), _channel_item("UC2"), _channel_item("UC3")]},
            {
                "items": [
                    _info("UC1", "Small", "@small", 900),
                    _info("UC2", "Mid", "@mid", 50_000),
                    _info("UC3", "Big", "@big", 2_000_000),
                ]
            },
        )
    )
    finder = discover.ChannelDiscovery("KEY", http=http)

    got = finder.find(["kindness"], min_subscribers=10_000)

    assert [c.title for c in got] == ["Big", "Mid"]


def test_find_fetches_standouts_only_for_the_final_picks():
    # Each standout lookup is a search.list call — the expensive quota unit.
    http = _RoutedHttp(
        _router(
            {"items": [_channel_item(f"UC{i}") for i in range(5)]},
            {"items": [_info(f"UC{i}", f"c{i}", f"@c{i}", 100_000 + i) for i in range(5)]},
        )
    )
    finder = discover.ChannelDiscovery("KEY", http=http)

    got = finder.find(["kindness"], limit=2)

    standouts = [c for c in http.calls if (c["params"] or {}).get("type") == "video"]
    assert len(got) == 2 and len(standouts) == 2


def test_find_dedupes_channels_across_hashtags():
    http = _RoutedHttp(
        _router(
            {"items": [_channel_item("UC1")]},  # both hashtags return the same channel
            {"items": [_info("UC1", "Once", "@once", 100_000)]},
        )
    )
    finder = discover.ChannelDiscovery("KEY", http=http)

    got = finder.find(["kindness", "heartwarming"])

    assert len(got) == 1
    searches = [c for c in http.calls if (c["params"] or {}).get("type") == "channel"]
    assert len(searches) == 2  # one search per hashtag, but one merged candidate


def test_message_lists_candidates_and_keeps_the_human_in_the_loop():
    out = discover.message(
        [
            discover.ChannelCandidate(
                channel_id="UC1",
                title="Kindness Man",
                handle="@kindnessman",
                subscribers=500_000,
                url="https://www.youtube.com/channel/UC1",
                standout_title="Best short",
                standout_url="https://www.youtube.com/shorts/vid9",
            )
        ]
    )

    assert "Kindness Man" in out and "500,000" in out
    assert "https://www.youtube.com/shorts/vid9" in out
    assert "watchlist.yaml" in out  # approving/adding stays Erez's step, never automatic


def test_message_when_nothing_found():
    assert "לא מצאתי" in discover.message([])


def test_load_watchlist_reads_the_discovery_block(tmp_path):
    from app import config

    path = tmp_path / "w.yaml"
    path.write_text(
        "creators: []\ntopics: []\n"
        "discovery:\n  min_subscribers: 5000\n  hashtags:\n    - kindness\n",
        encoding="utf-8",
    )

    watchlist = config.load_watchlist(str(path))

    assert watchlist.discovery.hashtags == ["kindness"]
    assert watchlist.discovery.min_subscribers == 5000


def test_load_watchlist_defaults_discovery_when_absent(tmp_path):
    from app import config

    path = tmp_path / "w.yaml"
    path.write_text("creators: []\ntopics: []\n", encoding="utf-8")

    watchlist = config.load_watchlist(str(path))

    assert watchlist.discovery.hashtags == []
    assert watchlist.discovery.min_subscribers == 10_000
