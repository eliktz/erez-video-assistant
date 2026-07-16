import pytest

from app.digest import compose


class _FakeUsage:
    prompt_token_count = 1000
    candidates_token_count = 500


class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = _FakeUsage()


class _FakeModels:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._text)


class _FakeClient:
    """Shaped after google-genai: client.models.generate_content -> resp.text/.usage_metadata."""

    def __init__(self, text):
        self.models = _FakeModels(text)


def test_reply_about_video_returns_hebrew_and_cost():
    client = _FakeClient("ההוק פה זה הרגע לפני ההפתעה.")

    out = compose.reply_about_video(
        {"hook": "x", "why_it_worked": "y"}, persona="תדבר בעברית", client=client
    )

    assert out.text == "ההוק פה זה הרגע לפני ההפתעה."
    assert out.cost_usd == pytest.approx(0.00155)  # 1000*0.30/1M + 500*2.50/1M
    call = client.models.calls[0]
    assert call["model"] == "gemini-3.5-flash"
    assert "תדבר בעברית" in call["contents"][0]  # persona rides in as the system preamble


def test_write_digest_includes_every_item():
    client = _FakeClient("הדוח של הבוקר")

    out = compose.write_digest([{"hook": "a"}, {"hook": "b"}], template="כתוב דוח", client=client)

    assert out.text == "הדוח של הבוקר"
    prompt = client.models.calls[0]["contents"][0]
    assert '"a"' in prompt and '"b"' in prompt


def test_estimate_cost_uses_gemini_rates():
    # 1000 in * 0.30/1M + 500 out * 2.50/1M = 0.0003 + 0.00125 = 0.00155
    assert abs(compose.estimate_cost(_FakeUsage()) - 0.00155) < 1e-9
