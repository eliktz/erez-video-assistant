from app.collect import trending
from tests.test_collect import _FakeHttp


def _chart_payload():
    return {
        "items": [
            {
                "id": "trend1",
                "snippet": {
                    "publishedAt": "2026-08-11T06:00:00Z",
                    "channelTitle": "Some Channel",
                    "title": "A song everyone uses",
                },
                "statistics": {
                    "viewCount": "1000000",
                    "likeCount": "5000",
                    "commentCount": "300",
                },
            }
        ]
    }


def test_chart_maps_items_to_candidates():
    http = _FakeHttp(_chart_payload())
    source = trending.TrendingChart("KEY", region="IL", http=http)

    got = source.chart()

    assert len(got) == 1
    assert got[0].id == "youtube:trend1"
    assert got[0].url == "https://www.youtube.com/watch?v=trend1"
    assert got[0].views == 1_000_000  # statistics ride in the same call — no follow-up
    assert got[0].posted_at == "2026-08-11T06:00:00Z"
    assert got[0].source == "trending"


def test_chart_asks_for_the_regions_own_chart():
    http = _FakeHttp(_chart_payload())

    trending.TrendingChart("KEY", region="IL", http=http).chart()

    params = http.calls[0]["params"]
    assert params["chart"] == "mostPopular"
    assert params["regionCode"] == "IL"
    assert "statistics" in params["part"]


def test_chart_without_region_omits_the_region_param():
    # "World" = no regionCode: YouTube then serves its default chart, the
    # closest free thing to a global one.
    http = _FakeHttp(_chart_payload())

    trending.TrendingChart("KEY", http=http).chart()

    assert "regionCode" not in http.calls[0]["params"]
