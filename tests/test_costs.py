from app import bot
from app.store import db, usage


def test_costs_message_lists_providers_and_total():
    conn = db.connect(":memory:")
    usage.record(conn, "gemini", "analyze_video", 1, 0.02, now="2026-07-01T00:00:00Z")
    usage.record(conn, "claude", "write_digest", 1, 0.15, now="2026-07-02T00:00:00Z")

    msg = bot.costs_message(conn, month="2026-07")

    assert "gemini" in msg and "claude" in msg
    assert "0.17" in msg


def test_costs_message_when_nothing_spent():
    conn = db.connect(":memory:")

    msg = bot.costs_message(conn, month="2026-07")

    assert "עדיין לא" in msg
