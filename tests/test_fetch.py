import pytest

from app.analyze import fetch


def test_download_builds_expected_ytdlp_options():
    captured = {}

    def fake_runner(url, opts):
        captured["url"] = url
        captured["opts"] = opts
        return {"duration": 42.0, "_filename": "/tmp/out/vid.mp4"}

    result = fetch.download(
        "https://tiktok.com/@x/video/1", "/tmp/out", runner=fake_runner
    )

    assert result.path == "/tmp/out/vid.mp4"
    assert result.duration_seconds == 42.0
    assert captured["url"] == "https://tiktok.com/@x/video/1"
    # Logged-out only: never send cookies, never use Erez's account.
    assert "cookiefile" not in captured["opts"]
    assert captured["opts"]["noplaylist"] is True


def test_download_raises_fetch_error_on_failure():
    def failing_runner(url, opts):
        raise RuntimeError("HTTP 403")

    with pytest.raises(fetch.FetchError, match="403"):
        fetch.download("https://x.com/1", "/tmp/out", runner=failing_runner)


def test_download_rejects_missing_duration():
    def runner(url, opts):
        return {"_filename": "/tmp/out/vid.mp4"}

    with pytest.raises(fetch.FetchError, match="duration"):
        fetch.download("https://x.com/1", "/tmp/out", runner=runner)
