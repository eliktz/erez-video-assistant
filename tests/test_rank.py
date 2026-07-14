from app.collect.base import Candidate
from app.digest import rank

NOW = "2026-07-14T12:00:00Z"


def _c(cid, views, posted_at):
    return Candidate(
        id=cid, platform="tiktok", native_id=cid, url=f"https://x/{cid}",
        creator=None, caption=None, posted_at=posted_at, views=views,
        likes=None, comments=None, source="scraper",
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
    slow = _c("slow", 1_000, "2026-07-13T12:00:00Z")   # 24h -> ~42/h
    fast = _c("fast", 10_000, "2026-07-14T10:00:00Z")  # 2h  -> 5000/h
    got = rank.top_n([slow, fast, fast], n=2, now=NOW)

    assert [c.id for c in got] == ["fast", "slow"]
