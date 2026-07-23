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


def test_recent_analyses_returns_newest_first():
    conn = _conn()
    for i, when in enumerate(["2026-07-10T00:00:00Z", "2026-07-12T00:00:00Z"]):
        vid = f"youtube:v{i}"
        videos.upsert_video(
            conn,
            {
                "id": vid, "platform": "youtube", "native_id": f"v{i}",
                "url": f"https://youtube.com/shorts/v{i}", "creator": None, "caption": None,
                "posted_at": None, "views": 0, "likes": 0, "comments": 0, "source": "youtube",
            },
            now=when,
        )
        videos.save_analysis(conn, vid, "v1", {"hook": f"hook{i}"}, now=when)

    out = videos.recent_analyses(conn, limit=10)

    assert [a["hook"] for a in out] == ["hook1", "hook0"]


def test_recent_analyses_respects_limit():
    conn = _conn()
    for i in range(3):
        vid = f"youtube:v{i}"
        videos.upsert_video(
            conn,
            {
                "id": vid, "platform": "youtube", "native_id": f"v{i}",
                "url": f"https://youtube.com/shorts/v{i}", "creator": None, "caption": None,
                "posted_at": None, "views": 0, "likes": 0, "comments": 0, "source": "youtube",
            },
            now=NOW,
        )
        videos.save_analysis(conn, vid, "v1", {"hook": f"hook{i}"}, now=NOW)

    assert len(videos.recent_analyses(conn, limit=2)) == 2


def test_connection_is_usable_from_another_thread():
    # APScheduler runs the digest job in a worker thread that shares this connection.
    import threading

    conn = db.connect(":memory:")
    errors = []

    def worker():
        try:
            conn.execute("SELECT 1").fetchone()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert errors == []
