from app import jobs
from app.analyze import fetch
from app.collect.base import Candidate
from app.digest import compose
from app.store import db

NOW = "2026-07-14T04:00:00Z"


class _FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)


class _FakeSource:
    name = "fake"

    def __init__(self, candidates, boom=False):
        self._candidates = candidates
        self._boom = boom

    def collect(self, watchlist, *, since):
        if self._boom:
            raise RuntimeError("vendor down")
        return self._candidates


def _candidate(cid="tiktok:1", caption=None):
    return Candidate(
        id=cid,
        platform="tiktok",
        native_id="1",
        url="https://x/1",
        creator="c",
        caption=caption,
        posted_at="2026-07-14T00:00:00Z",
        views=10_000,
        likes=None,
        comments=None,
        source="fake",
    )


def _settings():
    return {
        "digest": {"max_videos": 3, "deadman_minute": 30},
        "collect": {"lookback_hours": 48},
    }


def _deps(tmp_path):
    from app import bot
    from app.analyze import fetch

    return bot.Deps(
        conn=db.connect(":memory:"),
        gemini_client=object(),
        rubric="r",
        persona="p",
        work_dir=str(tmp_path),
        now=lambda: NOW,
        download=lambda url, dest, runner=None: fetch.FetchResult(
            path=str(tmp_path / "v.mp4"), duration_seconds=20.0
        ),
        analyze=lambda path, rubric, client: {"hook": "h", "why_it_worked": "w"},
        compose_reply=lambda a, p, c: "reply",
    )


def test_digest_analyzes_youtube_candidates_directly(tmp_path):
    # Digest candidates are YouTube videos; on Railway they cannot be downloaded
    # (datacenter-IP wall), so they must go through the direct-URL path.
    import json

    from app.analyze import gemini

    deps = _deps(tmp_path)
    deps.download = None  # any download attempt would crash — direct path must win
    deps.analyze_youtube = lambda url, rubric, client: gemini.RawAnalysis(
        json.dumps({"hook": "h"}), 0.005
    )
    yt = Candidate(
        id="youtube:zzz",
        platform="youtube",
        native_id="zzz",
        url="https://www.youtube.com/shorts/zzz",
        creator="c",
        caption=None,
        posted_at="2026-07-14T00:00:00Z",
        views=None,
        likes=None,
        comments=None,
        source="youtube",
    )
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([yt])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: compose.Written("דוח", 0.0),
        template="t",
        now=NOW,
    )

    assert body == "דוח"
    row = deps.conn.execute(
        "SELECT cost_usd FROM provider_usage WHERE operation='analyze_video'"
    ).fetchone()
    assert row["cost_usd"] == 0.005


def test_run_digest_sends_and_records(tmp_path):
    deps = _deps(tmp_path)
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([_candidate()])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: compose.Written("דוח הבוקר", 0.0),
        template="t",
        now=NOW,
    )

    assert body == "דוח הבוקר"
    assert len(notifier.sent) == 1
    row = deps.conn.execute("SELECT sent_at FROM digests WHERE for_date='2026-07-14'").fetchone()
    assert row["sent_at"] is not None


def test_run_digest_survives_a_dead_source(tmp_path):
    deps = _deps(tmp_path)
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([], boom=True), _FakeSource([_candidate()])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: compose.Written("דוח", 0.0),
        template="t",
        now=NOW,
    )

    assert body == "דוח"  # one vendor down must not kill the morning


def test_run_digest_survives_one_bad_analysis(tmp_path):
    # A Gemini hiccup on one video must not cost Erez the whole morning digest.
    deps = _deps(tmp_path)
    calls = []

    def flaky_analyze(path, rubric, client):
        calls.append(path)
        if len(calls) == 1:
            raise ValueError("Gemini returned non-JSON")
        return {"hook": "h", "why_it_worked": "w"}

    deps.download = lambda url, dest, runner=None: fetch.FetchResult(
        path=str(tmp_path / "v.mp4"), duration_seconds=20.0
    )
    deps.analyze = flaky_analyze
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([_candidate("tiktok:1"), _candidate("tiktok:2")])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: compose.Written("דוח", 0.0),
        template="t",
        now=NOW,
    )

    assert body == "דוח"  # the good video still makes the digest
    assert len(notifier.sent) == 1


def test_parse_excluded_formats_skips_comments_and_blanks():
    text = "# a comment\n\nשטיח אדום\nRed Carpet\n  \n# another\nMagic Booth\n"

    assert jobs.parse_excluded_formats(text) == ["שטיח אדום", "Red Carpet", "Magic Booth"]


def test_run_digest_skips_candidates_matching_excluded_formats(tmp_path):
    deps = _deps(tmp_path)
    notifier = _FakeNotifier()
    wanted = _candidate("tiktok:1", caption="Random act of kindness")
    excluded = _candidate("tiktok:2", caption="RedCarpetBoy walks the red carpet")

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([wanted, excluded])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: compose.Written("דוח", 0.0),
        template="t",
        now=NOW,
        excluded_formats=["red carpet"],
    )

    assert body == "דוח"
    row_ids = {r["id"] for r in deps.conn.execute("SELECT id FROM videos").fetchall()}
    assert row_ids == {"tiktok:1"}  # the excluded candidate never reaches analysis/storage


def test_run_digest_says_so_when_nothing_found(tmp_path):
    deps = _deps(tmp_path)
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: compose.Written("unused", 0.0),
        template="t",
        now=NOW,
    )

    assert body is None
    assert "לא מצאתי" in notifier.sent[0]  # degrade loudly, never silently


def test_deadman_alerts_admin_when_digest_missing():
    conn = db.connect(":memory:")
    admin = _FakeNotifier()

    jobs.deadman_check(conn=conn, admin_notifier=admin, for_date="2026-07-14", now=NOW)

    assert len(admin.sent) == 1
    assert "2026-07-14" in admin.sent[0]


def test_deadman_is_quiet_when_digest_was_sent():
    conn = db.connect(":memory:")
    conn.execute(
        "INSERT INTO digests (for_date, body_he, sent_at, created_at) VALUES (?,?,?,?)",
        ("2026-07-14", "x", NOW, NOW),
    )
    conn.commit()
    admin = _FakeNotifier()

    jobs.deadman_check(conn=conn, admin_notifier=admin, for_date="2026-07-14", now=NOW)

    assert admin.sent == []


def test_run_digest_leaves_sent_unset_when_delivery_fails(tmp_path):
    import pytest

    deps = _deps(tmp_path)

    class _BoomNotifier:
        def send(self, text):
            raise RuntimeError("telegram down")

    with pytest.raises(RuntimeError):
        jobs.run_digest(
            deps=deps,
            sources=[_FakeSource([_candidate()])],
            notifier=_BoomNotifier(),
            settings=_settings(),
            watchlist=None,
            compose_digest=lambda items, template, client: compose.Written("דוח", 0.0),
            template="t",
            now=NOW,
        )

    # A failed send must NOT record sent_at — else the dead-man's-switch stays silent.
    row = deps.conn.execute("SELECT sent_at FROM digests WHERE for_date='2026-07-14'").fetchone()
    assert row is None or row["sent_at"] is None


def test_run_digest_sends_a_plain_fallback_when_composing_fails(tmp_path):
    # We already paid for the analyses; a failed prose call must not cost the morning.
    deps = _deps(tmp_path)
    deps.analyze_youtube = lambda url, rubric, client: __import__(
        "app.analyze.gemini", fromlist=["RawAnalysis"]
    ).RawAnalysis('{"hook": "ילד רץ", "transferable_idea": "לצלם לפני ההפתעה"}', 0.005)
    yt = Candidate(
        id="youtube:q1",
        platform="youtube",
        native_id="q1",
        url="https://www.youtube.com/shorts/q1",
        creator="c",
        caption="כותרת",
        posted_at="2026-07-14T00:00:00Z",
        views=None,
        likes=None,
        comments=None,
        source="youtube",
    )
    notifier = _FakeNotifier()

    def boom_compose(items, template, client):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([yt])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=boom_compose,
        template="t",
        now=NOW,
    )

    assert body is not None
    assert "ילד רץ" in notifier.sent[0]  # the analysis we paid for still reaches Erez
    row = deps.conn.execute("SELECT sent_at FROM digests WHERE for_date='2026-07-14'").fetchone()
    assert row["sent_at"] is not None


class _FakeChart:
    def __init__(self, candidates):
        self._candidates = candidates

    def chart(self):
        return self._candidates


def _yt(cid, views=1_000, posted_at="2026-07-14T00:00:00Z"):
    return Candidate(
        id=f"youtube:{cid}",
        platform="youtube",
        native_id=cid,
        url=f"https://www.youtube.com/watch?v={cid}",
        creator="c",
        caption=None,
        posted_at=posted_at,
        views=views,
        likes=None,
        comments=None,
        source="trending",
    )


def _radar_deps(tmp_path):
    """Deps whose fake Gemini marks any video with 'emo' in its URL as Erez's genre."""
    import json

    from app.analyze import gemini

    deps = _deps(tmp_path)
    deps.download = None  # chart videos are YouTube — the direct path must carry everything
    deps.analyze_youtube = lambda url, rubric, client: gemini.RawAnalysis(
        json.dumps({"hook": "h", "fits_erez_style": "emo" in url}), 0.001
    )
    return deps


def test_run_digest_with_radar_builds_erezs_2x2(tmp_path):
    deps = _radar_deps(tmp_path)
    composed = {}

    def fake_compose(items, template, client):
        composed["items"] = items
        return compose.Written("דוח", 0.0)

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([])],
        notifier=_FakeNotifier(),
        settings=_settings(),
        watchlist=None,
        compose_digest=fake_compose,
        template="t",
        now=NOW,
        trending={
            "israel": _FakeChart([_yt("emo-il"), _yt("gen-il")]),
            "world": _FakeChart([_yt("emo-w"), _yt("gen-w")]),
        },
    )

    assert body == "דוח"
    got = {(i["native_id"], i["section"]) for i in composed["items"]}
    assert got == {
        ("emo-il", "israel"),
        ("gen-il", "israel"),
        ("emo-w", "world"),
        ("gen-w", "world"),
    }
    light = {i["native_id"] for i in composed["items"] if i["analysis"] is None}
    assert light == {"gen-il", "gen-w"}  # general trends stay one-liners — no invented analysis


def test_run_digest_radar_lets_topic_finds_win_world_slots(tmp_path):
    # The watchlist/topic pool competes with the world chart for the world slots.
    deps = _radar_deps(tmp_path)
    settings = _settings()
    settings["digest"]["radar"] = {"emotional_per_region": 1, "general_per_region": 1}
    fast_topic_find = _yt("emo-fast", views=10_000_000, posted_at="2026-07-14T02:00:00Z")
    composed = {}

    def fake_compose(items, template, client):
        composed["items"] = items
        return compose.Written("דוח", 0.0)

    jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([fast_topic_find])],
        notifier=_FakeNotifier(),
        settings=settings,
        watchlist=None,
        compose_digest=fake_compose,
        template="t",
        now=NOW,
        trending={"world": _FakeChart([_yt("emo-slow", views=100)])},
    )

    deep = {(i["native_id"], i["section"]) for i in composed["items"] if i["analysis"]}
    assert deep == {("emo-fast", "world")}  # the climbing topic find beat the chart video


def test_plain_digest_includes_link_and_analysis():
    out = jobs.plain_digest(
        [
            {
                "url": "https://x/1",
                "caption": "כותרת",
                "analysis": {"hook": "הוק", "why_it_worked": "סיבה"},
            }
        ]
    )

    assert "הוק" in out and "סיבה" in out and "https://x/1" in out
