import json
from pathlib import Path

from app.analyze import gemini


class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = None


class _FakeModels:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._text)


class _FakeFiles:
    def upload(self, file):
        return {"uri": f"fake://{file}"}


class _FakeClient:
    def __init__(self, text):
        self.files = _FakeFiles()
        self.models = _FakeModels(text)


def test_analyze_video_parses_json_response():
    sample = Path("tests/fixtures/analysis_sample.json").read_text(encoding="utf-8")
    client = _FakeClient(sample)

    result = gemini.analyze_video("/tmp/x.mp4", rubric="rubric text", client=client)

    assert result["hook"] == "הילד רץ אחרי המשאית"
    assert result["fits_erez_style"] is True
    assert client.models.calls[0]["model"] == "gemini-3.5-flash"


def test_analyze_video_strips_markdown_fences():
    sample = json.dumps({"hook": "x"}, ensure_ascii=False)
    client = _FakeClient(f"```json\n{sample}\n```")

    result = gemini.analyze_video("/tmp/x.mp4", rubric="r", client=client)

    assert result["hook"] == "x"


def test_estimate_cost_is_cents_per_video():
    # A 60s video is roughly 15,780 input tokens at $0.30/1M.
    cost = gemini.estimate_cost(60)
    assert 0.001 < cost < 0.05


class _FakeFile:
    """Shaped after the real SDK: uploads come back PROCESSING, not ready."""

    def __init__(self, state, name="files/abc"):
        self.state = type("_State", (), {"name": state})()
        self.name = name


def test_wait_until_active_polls_until_gemini_finishes_processing():
    # A real upload returns PROCESSING; calling generate_content on it is a 400.
    processing, active = _FakeFile("PROCESSING"), _FakeFile("ACTIVE")

    class _Files:
        def __init__(self):
            self.gets = 0

        def get(self, name):
            self.gets += 1
            return active

    class _Client:
        def __init__(self):
            self.files = _Files()

    client = _Client()

    out = gemini._wait_until_active(client, processing, sleep=lambda _s: None)

    assert gemini._state_of(out) == "ACTIVE"
    assert client.files.gets == 1


def test_wait_until_active_raises_when_gemini_cannot_process():
    import pytest

    with pytest.raises(RuntimeError, match="could not process"):
        gemini._wait_until_active(object(), _FakeFile("FAILED"), sleep=lambda _s: None)
