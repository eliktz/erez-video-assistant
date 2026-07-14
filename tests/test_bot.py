import json
from pathlib import Path

from app import bot
from app.analyze import fetch
from app.store import db, usage


def _deps(tmp_path, *, analysis=None, reply="ניתוח בעברית", fail=False):
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
        analyze=lambda path, rubric, client: sample,
        compose_reply=lambda analysis, persona, client: reply,
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
