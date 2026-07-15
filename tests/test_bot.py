import json
from pathlib import Path

import pytest

from app import bot
from app.analyze import fetch
from app.digest import compose
from app.store import db, usage


def _deps(tmp_path, *, analysis=None, reply="ניתוח בעברית", fail=False, analyze=None):
    sample = analysis or json.loads(
        Path("tests/fixtures/analysis_sample.json").read_text(encoding="utf-8")
    )

    def fake_download(url, dest, runner=None):
        if fail:
            raise fetch.FetchError("HTTP 403 blocked")
        return fetch.FetchResult(path=str(tmp_path / "v.mp4"), duration_seconds=30.0)

    return bot.Deps(
        conn=db.connect(":memory:"),
        gemini_client=object(),
        claude_client=object(),
        rubric="rubric",
        persona="persona",
        work_dir=str(tmp_path),
        now=lambda: "2026-07-14T05:00:00Z",
        download=fake_download,
        analyze=analyze or (lambda path, rubric, client: sample),
        compose_reply=lambda analysis, persona, client: compose.Written(reply, 0.0),
    )


def test_analyze_url_returns_hebrew_and_stores_everything(tmp_path):
    deps = _deps(tmp_path)

    out = bot.analyze_url("https://www.instagram.com/reel/DY2QmhAoF-z/", deps=deps)

    assert out == "ניתוח בעברית"
    rows = deps.conn.execute("SELECT id, platform FROM videos").fetchall()
    assert rows[0]["platform"] == "instagram"
    assert deps.conn.execute("SELECT COUNT(*) c FROM analyses").fetchone()["c"] == 1
    spend = usage.month_to_date(deps.conn, "2026-07")
    assert spend[0]["provider"] == "gemini"


def test_analyze_url_reuses_stored_analysis(tmp_path):
    deps = _deps(tmp_path)
    url = "https://www.instagram.com/reel/DY2QmhAoF-z/"

    bot.analyze_url(url, deps=deps)
    bot.analyze_url(url, deps=deps)

    # Second call must not pay Gemini again.
    calls = deps.conn.execute(
        "SELECT COUNT(*) c FROM provider_usage WHERE provider='gemini'"
    ).fetchone()["c"]
    assert calls == 1


def test_analyze_url_returns_friendly_hebrew_on_download_failure(tmp_path):
    deps = _deps(tmp_path, fail=True)

    out = bot.analyze_url("https://www.tiktok.com/@x/video/1", deps=deps)

    assert "לא הצלחתי" in out


def test_video_id_from_url_is_stable():
    a = bot.video_id_from_url("https://www.instagram.com/reel/DY2QmhAoF-z/")
    b = bot.video_id_from_url("https://www.instagram.com/reel/DY2QmhAoF-z/?igsh=xyz")
    assert a == b == "instagram:DY2QmhAoF-z"


def test_video_id_from_url_rejects_lookalike_hosts():
    # The patterns match anywhere in the string and we hand the ORIGINAL url to
    # yt-dlp, so a platform-shaped path on a foreign host must not be accepted.
    assert bot.video_id_from_url("http://127.0.0.1:6379/youtube.com/shorts/abc") is None
    assert bot.video_id_from_url("https://evil.example/instagram.com/reel/abc") is None
    assert bot.video_id_from_url("file:///etc/passwd#youtube.com/shorts/abc") is None
    # ...but the real thing still works.
    assert bot.video_id_from_url("https://www.youtube.com/shorts/abc") == "youtube:abc"


def test_analyze_url_bills_the_claude_call(tmp_path):
    deps = _deps(tmp_path)
    deps.compose_reply = lambda analysis, persona, client: compose.Written("תשובה", 0.0175)

    bot.analyze_url("https://www.instagram.com/reel/DY2QmhAoF-z/", deps=deps)

    rows = deps.conn.execute(
        "SELECT * FROM provider_usage WHERE provider='claude'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["cost_usd"] == pytest.approx(0.0175)


def test_analyze_url_bills_gemini_even_when_the_reply_wont_parse(tmp_path):
    def boom_analyze(path, rubric, client):
        raise ValueError("Gemini returned non-JSON")

    deps = _deps(tmp_path, analyze=boom_analyze)

    with pytest.raises(ValueError):
        bot.analyze_url("https://www.instagram.com/reel/DY2QmhAoF-z/", deps=deps)

    rows = deps.conn.execute(
        "SELECT * FROM provider_usage WHERE provider='gemini'"
    ).fetchall()
    assert len(rows) == 1


def test_over_budget_true_when_spend_reaches_the_cap():
    conn = db.connect(":memory:")
    usage.record(conn, "gemini", "analyze_video", 1, 40.0, now="2026-07-14T05:00:00Z")

    assert bot.over_budget(conn, 40.0, "2026-07") is True


def test_over_budget_false_when_under_the_cap():
    conn = db.connect(":memory:")
    usage.record(conn, "gemini", "analyze_video", 1, 10.0, now="2026-07-14T05:00:00Z")

    assert bot.over_budget(conn, 40.0, "2026-07") is False


def test_analyze_url_refuses_and_bills_nothing_when_over_budget(tmp_path):
    deps = _deps(tmp_path)
    usage.record(deps.conn, "gemini", "analyze_video", 1, 40.0, now="2026-07-14T05:00:00Z")

    out = bot.analyze_url("https://www.instagram.com/reel/DY2QmhAoF-z/", deps=deps)

    assert "תקרת ההוצאה" in out
    rows_before = usage.month_to_date(deps.conn, "2026-07")
    assert sum(r["calls"] for r in rows_before) == 1  # only the seeded row above


def test_is_authorized_allows_only_listed_chats():
    # The bot answers whoever messages it; only this check keeps strangers from
    # spending our Gemini/Claude budget and reading /costs.
    allowed = {111, 222}

    assert bot.is_authorized(111, allowed) is True
    assert bot.is_authorized(222, allowed) is True
    assert bot.is_authorized(999, allowed) is False
