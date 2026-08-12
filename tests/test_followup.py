from app import followup
from app.digest import compose
from app.store import db

NOW = "2026-08-12T10:00:00Z"
BOT_ID = 777


class _User:
    def __init__(self, user_id):
        self.id = user_id


class _Message:
    def __init__(self, text=None, from_user=None, reply_to_message=None):
        self.text = text
        self.from_user = from_user
        self.reply_to_message = reply_to_message


def _deps():
    from app import bot

    return bot.Deps(
        conn=db.connect(":memory:"),
        gemini_client=object(),
        rubric="r",
        persona="p",
        work_dir="/tmp",
        now=lambda: NOW,
    )


def test_quoted_bot_text_returns_the_bots_message():
    bot_msg = _Message(text="רעיון 1... רעיון 2...", from_user=_User(BOT_ID))
    reply = _Message(text="תפתח רעיון 2", reply_to_message=bot_msg)

    assert followup.quoted_bot_text(reply, BOT_ID) == "רעיון 1... רעיון 2..."


def test_quoted_bot_text_is_none_for_a_plain_message():
    assert followup.quoted_bot_text(_Message(text="בוקר טוב"), BOT_ID) is None


def test_quoted_bot_text_is_none_when_replying_to_a_human():
    # Erez and Elik talking to each other in the group must never trigger the bot.
    human_msg = _Message(text="ראית את זה?", from_user=_User(123))
    reply = _Message(text="כן מטורף", reply_to_message=human_msg)

    assert followup.quoted_bot_text(reply, BOT_ID) is None


def test_continue_thread_answers_and_bills():
    deps = _deps()
    calls = []

    def fake_compose(quoted, reply, template, client):
        calls.append((quoted, reply, template))
        return compose.Written("הנה הפיתוח של רעיון 2", 0.002)

    out = followup.continue_thread(
        deps,
        quoted="רעיון 2: חייל חוזר",
        reply="תפתח רעיון 2",
        template="t",
        compose_fn=fake_compose,
    )

    assert out == "הנה הפיתוח של רעיון 2"
    assert calls == [("רעיון 2: חייל חוזר", "תפתח רעיון 2", "t")]
    row = deps.conn.execute(
        "SELECT cost_usd FROM provider_usage WHERE operation='follow_up'"
    ).fetchone()
    assert row["cost_usd"] == 0.002  # every paid call writes its row — no exceptions


def test_continue_thread_respects_the_monthly_cap():
    from app.store import usage

    deps = _deps()
    usage.record(deps.conn, "gemini", "x", 1, 999.0, now=NOW)

    def never_called(*a):
        raise AssertionError("must not spend when over budget")

    out = followup.continue_thread(
        deps, quoted="q", reply="r", template="t", compose_fn=never_called
    )

    assert "תקרת ההוצאה" in out


def test_compose_continue_thread_sends_both_sides_of_the_conversation():
    from tests.test_compose import _FakeClient

    client = _FakeClient("ממשיך את הרעיון")

    out = compose.continue_thread("רעיון 2: חייל", "תפתח רעיון 2", "תמשיך שיחה", client)

    assert out.text == "ממשיך את הרעיון"
    prompt = client.models.calls[0]["contents"][0]
    assert "תמשיך שיחה" in prompt  # the template rides in as the system preamble
    assert "רעיון 2: חייל" in prompt and "תפתח רעיון 2" in prompt
