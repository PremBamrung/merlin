"""Unit tests for the Groq audio-transcription chunking/stitching logic.

These exercise the pure conversion + the chunk-stitching offset math without
touching the network or ffmpeg (the HTTP POST and the split are mocked).
"""

import os
import threading
import time
from unittest.mock import MagicMock, patch

from merlin.knowledge_sources.plugins.youtube.audio_transcriber import AudioTranscriber


def test_result_to_subtitles_offsets_segment_starts():
    result = {
        "segments": [
            {"start": 0.0, "end": 2.0, "text": " hello "},
            {"start": 2.0, "end": 5.0, "text": "world"},
        ]
    }
    subs = AudioTranscriber._result_to_subtitles(result, offset=100.0)
    assert subs == [
        {"start": 100.0, "duration": 2.0, "text": "hello"},
        {"start": 102.0, "duration": 3.0, "text": "world"},
    ]


def test_result_to_subtitles_drops_empty_segments():
    result = {"segments": [{"start": 0, "end": 1, "text": "   "}]}
    assert AudioTranscriber._result_to_subtitles(result) == []


def test_result_to_subtitles_falls_back_to_full_text():
    result = {"segments": [], "text": "no segments here", "duration": 12.0}
    subs = AudioTranscriber._result_to_subtitles(result, offset=5.0)
    assert subs == [{"start": 5.0, "duration": 12.0, "text": "no segments here"}]


def test_result_to_subtitles_empty_when_nothing():
    assert AudioTranscriber._result_to_subtitles({"segments": [], "text": ""}) == []


def _by_chunk(results):
    """A _post_audio stand-in answering by chunk index, not call order (the
    chunks are transcribed concurrently)."""

    def post(path):
        return results[int(os.path.basename(path)[1])]

    return post


def test_transcribe_chunked_stitches_with_running_offset():
    # Two chunks, each 60s of audio; the second chunk's timestamps must be
    # shifted by the first chunk's reported duration.
    chunk_results = [
        (
            True,
            {
                "segments": [{"start": 1.0, "end": 3.0, "text": "a"}],
                "duration": 60.0,
                "language": "french",
            },
            None,
        ),
        (
            True,
            {"segments": [{"start": 2.0, "end": 4.0, "text": "b"}], "duration": 60.0},
            None,
        ),
    ]

    with (
        patch.object(
            AudioTranscriber, "_split_audio", return_value=["c0.mp3", "c1.mp3"]
        ),
        patch.object(
            AudioTranscriber, "_post_audio", side_effect=_by_chunk(chunk_results)
        ),
    ):
        ok, subs, err, language = AudioTranscriber._transcribe_chunked("big.mp3")

    assert ok and err is None
    # Language is taken from the first chunk.
    assert language == "french"
    assert subs == [
        {"start": 1.0, "duration": 2.0, "text": "a"},
        {"start": 62.0, "duration": 2.0, "text": "b"},  # 2.0 + 60.0 offset
    ]


def test_transcribe_chunked_propagates_chunk_failure():
    chunk_results = [
        (
            True,
            {"segments": [{"start": 0.0, "end": 1.0, "text": "a"}], "duration": 60.0},
            None,
        ),
        (False, None, "Groq API error: 413 - too large"),
    ]
    with (
        patch.object(
            AudioTranscriber, "_split_audio", return_value=["c0.mp3", "c1.mp3"]
        ),
        patch.object(
            AudioTranscriber, "_post_audio", side_effect=_by_chunk(chunk_results)
        ),
    ):
        ok, subs, err, language = AudioTranscriber._transcribe_chunked("big.mp3")

    assert not ok
    assert subs is None
    assert language is None
    assert "Chunk 2/2 failed" in err


def test_transcribe_chunked_runs_chunks_concurrently_and_stitches_in_order():
    # The first chunk is the slowest to come back; the stitch must still follow
    # chunk order, and the chunks must overlap in time.
    active = 0
    peak = 0
    lock = threading.Lock()

    def post(path):
        nonlocal active, peak
        i = int(os.path.basename(path)[1])
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.15 if i == 0 else 0.05)
        with lock:
            active -= 1
        seg = {"start": 0.0, "end": 1.0, "text": f"part{i}"}
        return True, {"segments": [seg], "duration": 10.0}, None

    with (
        patch.object(
            AudioTranscriber,
            "_split_audio",
            return_value=["c0.ogg", "c1.ogg", "c2.ogg"],
        ),
        patch.object(AudioTranscriber, "_post_audio", side_effect=post),
    ):
        ok, subs, err, _ = AudioTranscriber._transcribe_chunked("big.ogg")

    assert ok and err is None
    assert peak > 1
    assert [(s["text"], s["start"]) for s in subs] == [
        ("part0", 0.0),
        ("part1", 10.0),
        ("part2", 20.0),
    ]


def test_transcribe_video_uses_canonical_url_and_a_private_dir_it_removes():
    seen = {}

    def download(url, out_dir):
        seen["url"], seen["dir"] = url, out_dir
        path = os.path.join(out_dir, "source.webm")
        open(path, "wb").close()
        return True, path

    def encode(src, out_dir):
        assert os.path.dirname(src) == out_dir
        path = os.path.join(out_dir, "speech.ogg")
        open(path, "wb").close()
        return path

    def transcribe(path, report=None):
        seen["transcribed"] = path
        assert os.path.exists(path)
        assert not os.path.exists(os.path.join(seen["dir"], "source.webm"))
        return True, [{"start": 0.0, "duration": 1.0, "text": "hi"}], None, "en"

    with (
        patch.object(AudioTranscriber, "download_audio", side_effect=download),
        patch.object(AudioTranscriber, "_to_speech_audio", side_effect=encode),
        patch.object(AudioTranscriber, "transcribe_audio", side_effect=transcribe),
    ):
        ok, subs, err, language = AudioTranscriber.transcribe_video("abc123XYZ_-")

    assert ok and language == "en"
    assert seen["url"] == "https://www.youtube.com/watch?v=abc123XYZ_-"
    assert os.path.basename(seen["dir"]).startswith("yt_audio_abc123XYZ_-_")
    assert seen["transcribed"] == os.path.join(seen["dir"], "speech.ogg")
    assert not os.path.exists(seen["dir"])  # whole work dir cleaned up


def test_transcribe_video_dirs_are_private_per_call():
    dirs = []

    def download(url, out_dir):
        dirs.append(out_dir)
        return False, "boom"

    with patch.object(AudioTranscriber, "download_audio", side_effect=download):
        assert AudioTranscriber.transcribe_video("a")[0] is False
        assert AudioTranscriber.transcribe_video("a")[0] is False

    assert dirs[0] != dirs[1]
    assert not any(os.path.exists(d) for d in dirs)


def test_post_audio_maps_groq_errors(tmp_path):
    import groq
    import httpx

    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"x")
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/audio")

    def status_error(code):
        response = httpx.Response(code, request=request)
        return groq.APIStatusError("nope", response=response, body=None)

    cases = [
        (status_error(413), "HTTP 413"),
        (status_error(500), "Groq API error: 500"),
        (groq.APITimeoutError(request=request), "failed after retries"),
    ]
    for exc, expected in cases:
        client = MagicMock()
        client.audio.transcriptions.create.side_effect = exc
        with patch(
            "merlin.knowledge_sources.plugins.youtube.audio_transcriber._groq_client",
            return_value=client,
        ):
            ok, result, err = AudioTranscriber._post_audio(str(audio))
        assert not ok and result is None
        assert expected in err


def test_post_audio_sends_bytes_and_returns_verbose_json(tmp_path):
    from groq.types.audio import Transcription

    audio = tmp_path / "speech.ogg"
    audio.write_bytes(b"opus-bytes")
    seen = {}

    def create(**kw):
        seen.update(kw)
        return Transcription.construct(
            text="hi", segments=[{"start": 0, "end": 1, "text": "hi"}], language="en"
        )

    client = MagicMock()
    client.audio.transcriptions.create.side_effect = create
    with patch(
        "merlin.knowledge_sources.plugins.youtube.audio_transcriber._groq_client",
        return_value=client,
    ):
        ok, result, err = AudioTranscriber._post_audio(str(audio))

    assert ok and err is None
    assert seen["file"] == ("speech.ogg", b"opus-bytes")
    assert seen["response_format"] == "verbose_json"
    assert result["language"] == "en" and result["segments"][0]["text"] == "hi"


def test_download_audio_single_pass_small_format(tmp_path):
    import yt_dlp

    class FakeYDL:
        seen: dict = {}

        def __init__(self, opts):
            FakeYDL.seen["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            FakeYDL.seen.setdefault("calls", []).append(download)
            path = os.path.join(tmp_path, "source.webm")
            open(path, "wb").close()
            return {"requested_downloads": [{"filepath": path}], "format_id": "249"}

    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        ok, path = AudioTranscriber.download_audio("https://youtu.be/x", str(tmp_path))

    assert ok and path == os.path.join(tmp_path, "source.webm")
    assert FakeYDL.seen["calls"] == [True]  # one extract_info, downloading
    opts = FakeYDL.seen["opts"]
    assert opts["format"].startswith("bestaudio[abr<=70]")
    assert opts["outtmpl"] == os.path.join(tmp_path, "source.%(ext)s")
    assert "postprocessors" not in opts  # re-encoding is ours, not yt-dlp's


class _FlakyYDL:
    """yt-dlp stand-in: the first `fail` extract_info calls 403, then succeed."""

    fail = 1
    calls = 0
    out_dir = ""

    def __init__(self, opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        import yt_dlp

        type(self).calls += 1
        if type(self).calls <= type(self).fail:
            raise yt_dlp.utils.DownloadError(
                "ERROR: unable to download video data: HTTP Error 403: Forbidden"
            )
        path = os.path.join(type(self).out_dir, "source.webm")
        open(path, "wb").close()
        return {"requested_downloads": [{"filepath": path}], "format_id": "249"}


def _flaky(tmp_path, fail):
    return type(
        "Flaky", (_FlakyYDL,), {"fail": fail, "calls": 0, "out_dir": str(tmp_path)}
    )


def test_download_audio_retries_a_403_once(tmp_path, monkeypatch):
    import yt_dlp

    from merlin.knowledge_sources.plugins.youtube import audio_transcriber as mod

    monkeypatch.setattr(mod, "_DOWNLOAD_RETRY_DELAY_SECONDS", 0)
    ydl = _flaky(tmp_path, fail=1)
    with patch.object(yt_dlp, "YoutubeDL", ydl):
        ok, path = AudioTranscriber.download_audio("https://youtu.be/x", str(tmp_path))

    assert ok and path == os.path.join(tmp_path, "source.webm")
    assert ydl.calls == 2


def test_download_audio_gives_up_after_a_second_403(tmp_path, monkeypatch):
    import yt_dlp

    from merlin.knowledge_sources.plugins.youtube import audio_transcriber as mod

    monkeypatch.setattr(mod, "_DOWNLOAD_RETRY_DELAY_SECONDS", 0)
    ydl = _flaky(tmp_path, fail=2)
    with patch.object(yt_dlp, "YoutubeDL", ydl):
        ok, msg = AudioTranscriber.download_audio("https://youtu.be/x", str(tmp_path))

    assert not ok and "HTTP 403" in msg
    assert ydl.calls == 2


def test_download_audio_does_not_retry_other_errors(tmp_path):
    import yt_dlp

    class Broken(_FlakyYDL):
        calls = 0

        def extract_info(self, url, download=False):
            type(self).calls += 1
            raise yt_dlp.utils.DownloadError("ERROR: Video unavailable")

    with patch.object(yt_dlp, "YoutubeDL", Broken):
        ok, msg = AudioTranscriber.download_audio("https://youtu.be/x", str(tmp_path))

    assert not ok and "Video unavailable" in msg
    assert Broken.calls == 1


def test_transcribe_video_reports_each_step():
    reports = []

    def download(url, out_dir):
        path = os.path.join(out_dir, "source.webm")
        open(path, "wb").close()
        return True, path

    def encode(src, out_dir):
        path = os.path.join(out_dir, "speech.ogg")
        open(path, "wb").close()
        return path

    def post(path):
        return True, {"segments": [{"start": 0, "end": 1, "text": "hi"}]}, None

    with (
        patch.object(AudioTranscriber, "download_audio", side_effect=download),
        patch.object(AudioTranscriber, "_to_speech_audio", side_effect=encode),
        patch.object(AudioTranscriber, "_post_audio", side_effect=post),
        patch(
            "merlin.knowledge_sources.plugins.youtube.audio_transcriber.GROQ_API_KEY",
            "k",
        ),
    ):
        ok, *_ = AudioTranscriber.transcribe_video(
            "a", report=lambda p, m: reports.append((p, m))
        )

    assert ok
    assert reports == [
        (36, "Downloading audio…"),
        (40, "Re-encoding audio…"),
        (42, "Transcribing audio…"),
    ]
