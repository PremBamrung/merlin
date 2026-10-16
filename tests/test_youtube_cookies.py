"""YouTube cookies (YOUTUBE_COOKIES_FILE) and the audio-download 403 message.

No network: yt-dlp's YoutubeDL is replaced with a fake that records its
options and fails the way YouTube does.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import yt_dlp

from merlin.config import settings
from merlin.knowledge_sources.plugins.youtube import cookies
from merlin.knowledge_sources.plugins.youtube.audio_transcriber import AudioTranscriber

COOKIES = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tabc123\n"
)


def _cookies_file(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text(COOKIES)
    return str(path)


def test_no_cookies_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "youtube_cookies_file", "")
    assert cookies.cookie_file() is None
    assert cookies.transcript_http_client() is None


def test_missing_cookies_file_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "youtube_cookies_file", str(tmp_path / "nope.txt"))
    assert cookies.cookie_file() is None


def test_transcript_client_carries_cookies(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "youtube_cookies_file", _cookies_file(tmp_path))
    session = cookies.transcript_http_client()
    assert session.cookies.get("SID", domain=".youtube.com") == "abc123"


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """download_audio retries a 403 once after a pause — skip the wait here."""
    from merlin.knowledge_sources.plugins.youtube import audio_transcriber

    monkeypatch.setattr(audio_transcriber, "_DOWNLOAD_RETRY_DELAY_SECONDS", 0)


class _Fake403YDL:
    """Stands in for yt_dlp.YoutubeDL: records options, then 403s."""

    seen: dict = {}

    def __init__(self, opts):
        _Fake403YDL.seen = dict(opts)
        cookiefile = opts.get("cookiefile")
        _Fake403YDL.seen["cookie_existed"] = bool(
            cookiefile and os.path.isfile(cookiefile)
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        raise yt_dlp.utils.DownloadError(
            "ERROR: unable to download video data: HTTP Error 403: Forbidden"
        )


def test_download_403_explains_itself_and_uses_a_cookie_copy(monkeypatch, tmp_path):
    user_file = _cookies_file(tmp_path)
    monkeypatch.setattr(settings, "youtube_cookies_file", user_file)
    out = tmp_path / "out"
    out.mkdir()
    with patch.object(yt_dlp, "YoutubeDL", _Fake403YDL):
        ok, msg = AudioTranscriber.download_audio("https://youtu.be/x", str(out))
    assert ok is False
    assert "refused the audio download (HTTP 403)" in msg
    assert yt_dlp.version.__version__ in msg
    assert "YOUTUBE_COOKIES_FILE" not in msg  # cookies were already in use
    # yt-dlp got a private copy (it rewrites cookiefile), removed afterwards.
    copy = _Fake403YDL.seen["cookiefile"]
    assert copy != user_file and _Fake403YDL.seen["cookie_existed"]
    assert not os.path.exists(copy)
    assert open(user_file).read() == COOKIES


def test_download_403_without_cookies_suggests_them(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "youtube_cookies_file", "")
    with patch.object(yt_dlp, "YoutubeDL", _Fake403YDL):
        ok, msg = AudioTranscriber.download_audio("https://youtu.be/x", str(tmp_path))
    assert ok is False
    assert "cookiefile" not in _Fake403YDL.seen
    assert "Setting YOUTUBE_COOKIES_FILE may help." in msg
