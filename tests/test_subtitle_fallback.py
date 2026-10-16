"""YouTubePlugin's audio fallback says *why* it skipped subtitles.

The extractors, transcriber and summariser are stubbed; this checks only the
progress messages and the task error the plugin builds from
SubtitlesUnavailable.
"""

import pytest

from merlin.knowledge_sources.base import IngestRequest
from merlin.knowledge_sources.plugins.youtube.audio_transcriber import AudioTranscriber
from merlin.knowledge_sources.plugins.youtube.extractors import SubtitlesUnavailable
from merlin.knowledge_sources.plugins.youtube.plugin import YouTubePlugin

URL = "https://www.youtube.com/watch?v=abcdefghijk"


class _StubSummarizer:
    last_usage: dict = {}

    def summarize(self, **kwargs):
        return "## Overview\nok", {}, {}


def _plugin(monkeypatch, unavailable, transcribe):
    from merlin.config import settings

    if hasattr(settings, "youtube_comments_limit"):  # no comments fetch
        monkeypatch.setattr(settings, "youtube_comments_limit", 0)
    plugin = YouTubePlugin()
    plugin._summarizer = _StubSummarizer()
    monkeypatch.setattr(
        plugin._video_extractor,
        "extract_video_info",
        lambda url: {
            "title": "T",
            "channel": "C",
            "date": "01/01/2026",
            "views": "1",
            "description": "",
        },
    )

    def extract_subtitles(*args, **kwargs):
        raise unavailable

    monkeypatch.setattr(
        plugin._subtitle_extractor, "extract_subtitles", extract_subtitles
    )
    monkeypatch.setattr(AudioTranscriber, "transcribe_video", transcribe)
    return plugin


def _request(reports):
    return IngestRequest(
        raw_input=URL, progress_callback=lambda p, m: reports.append((p, m))
    )


@pytest.mark.parametrize(
    "unavailable, says",
    [
        (
            SubtitlesUnavailable("cooldown", "117 min left"),
            "YouTube is blocking subtitles (paused, 117 min left)",
        ),
        (SubtitlesUnavailable("blocked"), "YouTube blocked the subtitle request"),
        (SubtitlesUnavailable("none"), "This video has no subtitles"),
        (
            SubtitlesUnavailable("error", "timed out"),
            "Couldn't fetch subtitles (timed out)",
        ),
    ],
)
def test_fallback_progress_names_the_reason(monkeypatch, unavailable, says):
    def transcribe(video_id, report=None):
        report(36, "Downloading audio…")
        return True, [{"start": 0.0, "duration": 2.0, "text": "hi"}], None, "en"

    reports = []
    result = _plugin(monkeypatch, unavailable, transcribe).ingest(_request(reports))

    assert (35, f"{says} — transcribing the audio instead…") in reports
    assert result.source_metadata["transcript_source"] == "audio"


def test_fallback_steps_keep_the_reason(monkeypatch):
    def transcribe(video_id, report=None):
        report(36, "Downloading audio…")
        return True, [{"start": 0.0, "duration": 2.0, "text": "hi"}], None, "en"

    reports = []
    plugin = _plugin(monkeypatch, SubtitlesUnavailable("blocked"), transcribe)
    plugin.ingest(_request(reports))

    assert (36, "Subtitles blocked by YouTube · Downloading audio…") in reports


def test_failed_fallback_error_names_both_causes(monkeypatch):
    def transcribe(video_id, report=None):
        return False, None, "YouTube refused the audio download (HTTP 403).", None

    plugin = _plugin(
        monkeypatch, SubtitlesUnavailable("cooldown", "5 min left"), transcribe
    )
    with pytest.raises(ValueError) as exc:
        plugin.ingest(_request([]))

    assert str(exc.value) == (
        "Subtitles blocked by YouTube, and the audio fallback failed: "
        "YouTube refused the audio download (HTTP 403)."
    )
