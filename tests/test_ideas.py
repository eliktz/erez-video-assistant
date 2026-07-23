from app import bot, ideas
from app.store import db, usage, videos


class _FakeUsage:
    prompt_token_count = 100
    candidates_token_count = 50
    thoughts_token_count = 0


class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = _FakeUsage()


class _FakeModels:
    def generate_content(self, **kwargs):
        return _FakeResponse("3 רעיונות בשבילך")


class _FakeClient:
    """Shaped after google-genai, like tests/test_compose.py's fake."""

    models = _FakeModels()


def _deps(conn, **overrides):
    defaults = dict(
        conn=conn,
        gemini_client=_FakeClient(),
        rubric="rubric",
        persona="persona",
        work_dir="/tmp",
        now=lambda: "2026-07-23T05:00:00Z",
    )
    defaults.update(overrides)
    return bot.Deps(**defaults)


def _seed_one_analysis(conn):
    videos.upsert_video(
        conn,
        {
            "id": "youtube:v1", "platform": "youtube", "native_id": "v1",
            "url": "https://youtube.com/shorts/v1", "creator": None, "caption": None,
            "posted_at": None, "views": 0, "likes": 0, "comments": 0, "source": "youtube",
        },
        now="2026-07-23T04:00:00Z",
    )
    videos.save_analysis(
        conn, "youtube:v1", "v1", {"hook": "מישהו רועד לא מצליח לאכול"}, now="2026-07-23T04:00:00Z"
    )


def test_pitch_returns_ideas_and_bills_gemini():
    conn = db.connect(":memory:")
    _seed_one_analysis(conn)
    deps = _deps(conn)

    out = ideas.pitch(deps, template="תציע רעיונות")

    assert out == "3 רעיונות בשבילך"
    rows = usage.month_to_date(conn, "2026-07")
    assert rows[0]["provider"] == "gemini"
    assert rows[0]["calls"] == 1


def test_pitch_asks_for_videos_first_when_none_analyzed():
    conn = db.connect(":memory:")
    deps = _deps(conn)

    out = ideas.pitch(deps, template="תציע רעיונות")

    assert "עוד לא ניתחתי" in out


def test_pitch_refuses_and_bills_nothing_when_over_budget():
    conn = db.connect(":memory:")
    _seed_one_analysis(conn)
    usage.record(conn, "gemini", "analyze_video", 1, 40.0, now="2026-07-23T04:00:00Z")
    deps = _deps(conn)

    out = ideas.pitch(deps, template="תציע רעיונות")

    assert "תקרת ההוצאה" in out
    rows = usage.month_to_date(conn, "2026-07")
    assert sum(r["calls"] for r in rows) == 1  # only the seeded row above
