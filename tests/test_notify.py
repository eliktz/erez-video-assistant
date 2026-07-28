from app.notify import telegram


class _FakeResponse:
    def __init__(self, status_code=200, text='{"ok":true}'):
        self.status_code = status_code
        self.text = text


class _FakeHttp:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.posts = []

    def post(self, url, json=None):
        self.posts.append({"url": url, "json": json})
        return _FakeResponse(self.status_code)


def test_chunks_split_at_line_breaks_under_the_cap():
    lines = "\n".join(f"שורה {i} " + "א" * 100 for i in range(80))

    parts = list(telegram.chunks(lines))

    assert len(parts) > 1
    assert all(len(p) <= telegram.TEXT_LIMIT for p in parts)
    assert "".join(p + "\n" for p in parts).strip().replace("\n\n", "\n") != ""  # nothing lost:
    assert sum(p.count("שורה") for p in parts) == 80


def test_send_splits_long_digests_into_multiple_messages():
    http = _FakeHttp()
    notifier = telegram.TelegramNotifier("TOKEN", "123", client=http)

    notifier.send("קטע ראשון\n" + "א" * 5000 + "\nקטע אחרון")

    assert len(http.posts) >= 2
    assert all(len(p["json"]["text"]) <= telegram.TEXT_LIMIT for p in http.posts)


def test_send_uses_plain_text_not_markdown():
    # Model-written Hebrew with an unbalanced '*' must not 400 on entity parsing.
    http = _FakeHttp()
    notifier = telegram.TelegramNotifier("TOKEN", "123", client=http)

    notifier.send("דוח *הבוקר")

    assert "parse_mode" not in http.posts[0]["json"]


def test_send_error_never_carries_the_token():
    # httpx's own exception embeds the URL, and the URL embeds the bot token.
    import pytest

    http = _FakeHttp(status_code=400)
    notifier = telegram.TelegramNotifier("SECRET-TOKEN", "123", client=http)

    with pytest.raises(RuntimeError) as err:
        notifier.send("שלום")

    assert "SECRET-TOKEN" not in str(err.value)
