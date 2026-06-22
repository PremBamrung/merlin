"""Unit tests for SubtitleExtractor's original-language detection.

A French video that *also* ships an English subtitle track must still be
detected as French — the summary language follows the spoken language, not
whichever track happens to sit first in the caller's preferred-language list.
The network (YouTubeTranscriptApi) is faked; no real requests are made.
"""

from unittest.mock import patch

from merlin.knowledge_sources.plugins.youtube.extractors import SubtitleExtractor


class _FakeTranscript:
    def __init__(self, language_code, is_generated, fetch_error=None):
        self.language_code = language_code
        self.is_generated = is_generated
        self._fetch_error = fetch_error
        self.translate_called = False

    def fetch(self):
        if self._fetch_error is not None:
            raise self._fetch_error
        return [{"start": 0.0, "duration": 1.0, "text": f"text-{self.language_code}"}]

    def translate(self, target):
        # We never translate via YouTube — flag it so the test can assert it
        # was not called.
        self.translate_called = True
        raise AssertionError("translate() must not be called")


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
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    # The rate limiter is a module-level singleton; clear any cooldown a prior
    # test may have tripped so cases run in isolation.
    _subtitle_rate_limiter.clear_cooldown()
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


def test_ip_block_on_fetch_returns_none_and_never_translates():
    # The chosen transcript's fetch() hits a YouTube IP block. We must NOT try
    # to translate (which would only pile more requests on the blocked IP) —
    # extract_subtitles returns None (→ caller falls back to audio) and the
    # cooldown is tripped so subsequent ingests skip subtitles.
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    ip_block = Exception("YouTube is blocking requests from your IP (RequestBlocked)")
    blocked = _FakeTranscript("fr", is_generated=True, fetch_error=ip_block)

    result = _extract([blocked], ["en", "fr"])

    assert result is None
    assert blocked.translate_called is False
    assert _subtitle_rate_limiter.in_cooldown()
    _subtitle_rate_limiter.clear_cooldown()
