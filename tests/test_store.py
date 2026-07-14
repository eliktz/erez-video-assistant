from app.store import db, usage, videos

NOW = "2026-07-14T04:00:00Z"


def _conn():
    return db.connect(":memory:")


def test_upsert_video_is_idempotent():
    conn = _conn()
    row = {
        "id": "youtube:abc123",
        "platform": "youtube",
        "native_id": "abc123",
        "url": "https://youtube.com/shorts/abc123",
        "creator": "someone",
        "caption": "hello",
        "posted_at": "2026-07-13T10:00:00Z",
        "views": 1000,
        "likes": 50,
        "comments": 5,
        "source": "youtube",
    }
    videos.upsert_video(conn, row, now=NOW)
    row["views"] = 2000
    videos.upsert_video(conn, row, now=NOW)

    stored = videos.get_video(conn, "youtube:abc123")
    assert stored["views"] == 2000
    assert stored["first_seen_at"] == NOW


def test_save_and_get_analysis():
    conn = _conn()
    videos.upsert_video(
        conn,
        {
            "id": "youtube:abc123",
            "platform": "youtube",
            "native_id": "abc123",
            "url": "https://youtube.com/shorts/abc123",
            "creator": None,
            "caption": None,
            "posted_at": None,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "source": "youtube",
        },
        now=NOW,
    )
    videos.save_analysis(conn, "youtube:abc123", "v1", {"hook": "כלב"}, now=NOW)

    got = videos.get_analysis(conn, "youtube:abc123", "v1")
    assert got["hook"] == "כלב"
    assert videos.get_analysis(conn, "youtube:abc123", "v2") is None


def test_usage_month_to_date_sums_by_provider():
    conn = _conn()
    usage.record(conn, "gemini", "analyze", 1, 0.01, now="2026-07-01T00:00:00Z")
    usage.record(conn, "gemini", "analyze", 1, 0.02, now="2026-07-02T00:00:00Z")
    usage.record(conn, "claude", "compose", 1, 0.10, now="2026-07-02T00:00:00Z")
    usage.record(conn, "gemini", "analyze", 1, 99.0, now="2026-06-30T00:00:00Z")

    rows = {r["provider"]: r for r in usage.month_to_date(conn, "2026-07")}
    assert rows["gemini"]["cost_usd"] == 0.03
    assert rows["gemini"]["calls"] == 2
    assert rows["claude"]["cost_usd"] == 0.10
