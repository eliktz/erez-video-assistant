import pytest

from app.digest import compose


class _FakeUsage:
    input_tokens = 1000
    output_tokens = 500
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage()
        self.stop_reason = "end_turn"


class _FakeMessages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMessage(self._text)


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def test_reply_about_video_returns_hebrew_text():
    client = _FakeClient("ההוק פה זה הרגע לפני ההפתעה.")

    out = compose.reply_about_video(
        {"hook": "x", "why_it_worked": "y"}, persona="תדבר בעברית", client=client
    )

    assert out.text == "ההוק פה זה הרגע לפני ההפתעה."
    assert out.cost_usd == pytest.approx(0.0175)
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["system"] == "תדבר בעברית"


def test_write_digest_includes_every_item():
    client = _FakeClient("הדוח של הבוקר")

    out = compose.write_digest([{"hook": "a"}, {"hook": "b"}], template="כתוב דוח", client=client)

    assert out.text == "הדוח של הבוקר"
    prompt = client.messages.calls[0]["messages"][0]["content"]
    assert '"a"' in prompt and '"b"' in prompt


def test_estimate_cost_uses_opus_rates():
    # $5/1M in, $25/1M out -> 1000 in + 500 out = 0.005 + 0.0125
    assert abs(compose.estimate_cost(_FakeUsage()) - 0.0175) < 1e-6
