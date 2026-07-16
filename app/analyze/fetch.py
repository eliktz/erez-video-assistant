"""Get video bytes for analysis.

Two paths: yt-dlp for a public URL, or the file Telegram already has when Erez
uploads directly. The upload path needs no scraping at all, which is why it is
the fallback when yt-dlp gets blocked.
"""

from dataclasses import dataclass

# Telegram's getFile refuses anything larger. A 60s 1080p reel can exceed this,
# so the URL path stays primary and this is the fallback.
TELEGRAM_MAX_BYTES = 20 * 1024 * 1024


class FetchError(Exception):
    """Could not get the video. Message is safe to show a user."""


@dataclass(frozen=True)
class FetchResult:
    path: str
    duration_seconds: float


def _default_runner(url: str, opts: dict) -> dict:
    import yt_dlp

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def download(url: str, dest_dir: str, *, runner=None) -> FetchResult:
    """Download a public video. Logged out, always — never Erez's account."""
    runner = runner or _default_runner
    opts = {
        "outtmpl": f"{dest_dir}/%(id)s.%(ext)s",
        "format": "mp4[height<=720]/best[height<=720]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        info = runner(url, opts)
    except Exception as exc:  # yt-dlp raises many types; the caller only needs one
        raise FetchError(f"Could not download {url}: {exc}") from exc

    duration = info.get("duration")
    if duration is None:
        raise FetchError(f"No duration reported for {url}; refusing to guess cost.")
    return FetchResult(path=_downloaded_path(info, url), duration_seconds=float(duration))


def _downloaded_path(info: dict, url: str) -> str:
    """Where yt-dlp actually wrote the file.

    Current yt-dlp reports it under requested_downloads[].filepath; older/other
    shapes used a top-level _filename. Accept either, and fail loudly if neither
    is present rather than handing a missing path downstream.
    """
    downloads = info.get("requested_downloads") or []
    path = info.get("_filename") or (downloads[0].get("filepath") if downloads else None)
    if not path:
        raise FetchError(f"Downloaded {url} but could not find the saved file path.")
    return path
