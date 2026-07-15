from app import jobs
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


def _candidate(cid="tiktok:1"):
    return Candidate(
        id=cid,
        platform="tiktok",
        native_id="1",
        url="https://x/1",
        creator="c",
        caption=None,
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
        claude_client=object(),
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
    row = deps.conn.execute(
        "SELECT sent_at FROM digests WHERE for_date='2026-07-14'"
    ).fetchone()
    assert row is None or row["sent_at"] is None
