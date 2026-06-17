"""Unit tests for SubtitleExtractor's original-language detection.

A French video that *also* ships an English subtitle track must still be
detected as French — the summary language follows the spoken language, not
whichever track happens to sit first in the caller's preferred-language list.
The network (YouTubeTranscriptApi) is faked; no real requests are made.
"""

from unittest.mock import patch

from merlin.knowledge_sources.plugins.youtube.extractors import SubtitleExtractor


class _FakeTranscript:
    def __init__(self, language_code, is_generated):
        self.language_code = language_code
        self.is_generated = is_generated

    def fetch(self):
        return [{"start": 0.0, "duration": 1.0, "text": f"text-{self.language_code}"}]


class _FakeTranscriptList:
    """Minimal stand-in for youtube_transcript_api's TranscriptList.

    Iteration yields manual transcripts before generated ones (matching the
    real library), and find_* honours the caller's language priority order.
    """

    def __init__(self, transcripts):
        self._transcripts = transcripts

    def __iter__(self):
        manual = [t for t in self._transcripts if not t.is_generated]
        generated = [t for t in self._transcripts if t.is_generated]
        return iter(manual + generated)

    def _find(self, languages, generated):
        pool = {
            t.language_code: t for t in self._transcripts if t.is_generated == generated
        }
        for lang in languages:
            if lang in pool:
                return pool[lang]
        raise Exception("no transcript")

    def find_manually_created_transcript(self, languages):
        return self._find(languages, generated=False)

    def find_generated_transcript(self, languages):
        return self._find(languages, generated=True)


def _extract(transcripts, languages):
    fake_api = type(
        "Api", (), {"list": lambda self, vid: _FakeTranscriptList(transcripts)}
    )()
    with (
        patch(
            "merlin.knowledge_sources.plugins.youtube.extractors.YouTubeTranscriptApi",
            return_value=fake_api,
        ),
        patch(
            "merlin.knowledge_sources.plugins.youtube.extractors._subtitle_rate_limiter.wait"
        ),
    ):
        return SubtitleExtractor.extract_subtitles("vid", languages)


def test_french_video_with_english_subs_detected_as_french():
    # French ASR + an English manual track. English is first in the priority
    # list (the en+fr default), yet detection must report French.
    transcripts = [
        _FakeTranscript("en", is_generated=False),
        _FakeTranscript("fr", is_generated=True),
    ]
    result = _extract(transcripts, ["en", "fr", "en", "fr", "de"])
    assert result["language_code"] == "fr"


def test_english_video_detected_as_english():
    transcripts = [_FakeTranscript("en", is_generated=True)]
    result = _extract(transcripts, ["en", "fr", "de"])
    assert result["language_code"] == "en"


def test_falls_back_to_first_available_when_no_generated():
    # Manual-only video: detect from the first listed (original) track.
    transcripts = [
        _FakeTranscript("fr", is_generated=False),
        _FakeTranscript("en", is_generated=False),
    ]
    result = _extract(transcripts, ["en", "fr"])
    assert result["language_code"] == "fr"
