"""Unit tests for SubtitleExtractor's original-language detection.

A French video that *also* ships an English subtitle track must still be
detected as French — the summary language follows the spoken language, not
whichever track happens to sit first in the caller's preferred-language list.
The network (YouTubeTranscriptApi) is faked; no real requests are made.
"""

from unittest.mock import patch

import pytest

from merlin.knowledge_sources.plugins.youtube.extractors import (
    SubtitleExtractor,
    SubtitlesUnavailable,
)


@pytest.fixture(autouse=True)
def _no_cooldown_persistence(monkeypatch):
    """Keep the module-level limiter's cooldown in memory — these tests trip it,
    and must never write it to whatever DB DATABASE_URL points at."""
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    monkeypatch.setattr(_subtitle_rate_limiter, "_load_state", None)
    monkeypatch.setattr(_subtitle_rate_limiter, "_save_state", None)
    monkeypatch.setattr(_subtitle_rate_limiter, "_loaded", True)


class _FakeTranscript:
    def __init__(self, language_code, is_generated, fetch_error=None, variant=None):
        self.language_code = language_code
        self.is_generated = is_generated
        # Mirrors youtube-transcript-api's private caption URL; dub tracks carry
        # variant=timing-optimized.
        self._url = (
            f"https://www.youtube.com/api/timedtext?v=vid&lang={language_code}"
            + (f"&variant={variant}" if variant else "")
        )
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


def test_ip_block_on_fetch_raises_blocked_and_never_translates():
    # The chosen transcript's fetch() hits a YouTube IP block. We must NOT try
    # to translate (which would only pile more requests on the blocked IP) —
    # extract_subtitles raises SubtitlesUnavailable("blocked") (→ caller falls
    # back to audio, saying why) and the cooldown is tripped so subsequent
    # ingests skip subtitles.
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    ip_block = Exception("YouTube is blocking requests from your IP (RequestBlocked)")
    blocked = _FakeTranscript("fr", is_generated=True, fetch_error=ip_block)

    with pytest.raises(SubtitlesUnavailable) as exc:
        _extract([blocked], ["en", "fr"])

    assert exc.value.kind == "blocked"
    assert blocked.translate_called is False
    assert _subtitle_rate_limiter.in_cooldown()
    _subtitle_rate_limiter.clear_cooldown()


def test_ai_dubbed_video_picks_original_over_dub_track():
    # YouTube AI-dubbed a French video into English: there's an ASR track per
    # audio track, and the dub's is region-tagged ("en-US"). Listed first, it
    # used to win — the original-audio "fr" track must be detected and fetched.
    transcripts = [
        _FakeTranscript("en-US", is_generated=True),
        _FakeTranscript("fr", is_generated=True),
    ]
    result = _extract(transcripts, ["en", "fr", "en", "fr", "de"])
    assert result["language_code"] == "fr"
    assert result["transcript_language"] == "fr"
    assert result["transcript_source"] == "auto"
    assert result["subtitles"][0]["text"] == "text-fr"


def test_title_language_breaks_a_tie_between_bare_tracks():
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _pick_original_language,
    )

    tracks = [
        _FakeTranscript("en", is_generated=True),
        _FakeTranscript("fr", is_generated=True),
    ]
    assert _pick_original_language(tracks, "Le CRA en MONOCOMPTE sur DOFUS") == "fr"
    # No usable hint → keep the listed order.
    assert _pick_original_language(tracks, "DOFUS 3.6") == "en"


def test_manual_track_reports_its_provenance():
    transcripts = [
        _FakeTranscript("en", is_generated=False),
        _FakeTranscript("fr", is_generated=True),
    ]
    result = _extract(transcripts, ["en", "fr"])
    assert result["language_code"] == "fr"  # spoken language
    assert result["transcript_language"] == "en"  # the text actually used
    assert result["transcript_source"] == "manual"


def test_guess_text_language():
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _guess_text_language,
    )

    assert _guess_text_language("Le CRA en MONOCOMPTE sur DOFUS") == "fr"
    assert _guess_text_language("How to pick the best class for your first run") == "en"
    assert _guess_text_language("DOFUS 3.6") is None


def test_many_language_dub_picks_the_non_dub_track():
    # gAUYvSB0fdU's real layout: auto-dubbed into ~20 languages, all bare codes,
    # Bengali listed first. Only the original's URL lacks timing-optimized.
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _pick_original_language,
    )

    dubs = ["bn", "nl", "fr", "de", "hi", "ja", "es"]
    tracks = [_FakeTranscript(c, True, variant="timing-optimized") for c in dubs[:2]]
    tracks.append(_FakeTranscript("en", True, variant="gemini"))
    tracks += [_FakeTranscript(c, True, variant="timing-optimized") for c in dubs[2:]]
    # Even a title in another language can't pull it onto a dub track.
    assert _pick_original_language(tracks, "Le guide pour la machine") == "en"


def test_region_tagged_dub_with_variant_marker():
    # zyJqVR7Svqo's real layout: en-US dub (timing-optimized) + original fr.
    transcripts = [
        _FakeTranscript("en-US", True, variant="timing-optimized"),
        _FakeTranscript("fr", True),
    ]
    result = _extract(transcripts, ["en", "fr", "de"])
    assert result["language_code"] == "fr"
    assert result["transcript_language"] == "fr"


def test_track_without_url_falls_back_to_other_rules():
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _is_dub_track,
        _pick_original_language,
    )

    bare = _FakeTranscript("en", True)
    del bare._url
    assert _is_dub_track(bare) is False
    assert _pick_original_language([bare]) == "en"


def test_cooldown_tripped_while_waiting_skips_the_fetch():
    # Listing succeeded, but while this worker waited for its fetch slot another
    # worker's fetch hit an IP block. The fetch must not go out.
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    _subtitle_rate_limiter.clear_cooldown()
    transcript = _FakeTranscript("en", is_generated=True)
    fetched = []
    transcript.fetch = lambda: fetched.append(True)
    waits = []

    def wait():
        waits.append(True)
        if len(waits) == 2:  # the slot before fetch()
            _subtitle_rate_limiter.trip_cooldown()

    fake_api = type(
        "Api", (), {"list": lambda self, vid: _FakeTranscriptList([transcript])}
    )()
    try:
        with (
            patch(
                "merlin.knowledge_sources.plugins.youtube.extractors.YouTubeTranscriptApi",
                return_value=fake_api,
            ),
            patch.object(_subtitle_rate_limiter, "wait", side_effect=wait),
        ):
            with pytest.raises(SubtitlesUnavailable) as exc:
                SubtitleExtractor.extract_subtitles("vid", ["en"])
    finally:
        cooled = _subtitle_rate_limiter.in_cooldown()
        _subtitle_rate_limiter.clear_cooldown()

    assert exc.value.kind == "cooldown"
    assert fetched == []
    assert cooled


def test_active_cooldown_raises_without_contacting_youtube():
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    _subtitle_rate_limiter.clear_cooldown()
    _subtitle_rate_limiter.trip_cooldown()
    try:
        with patch(
            "merlin.knowledge_sources.plugins.youtube.extractors.YouTubeTranscriptApi"
        ) as api:
            with pytest.raises(SubtitlesUnavailable) as exc:
                SubtitleExtractor.extract_subtitles("vid", ["en"])
    finally:
        _subtitle_rate_limiter.clear_cooldown()

    assert exc.value.kind == "cooldown"
    assert exc.value.detail.endswith("min left")
    api.assert_not_called()


def test_no_transcript_at_all_raises_none():
    with pytest.raises(SubtitlesUnavailable) as exc:
        _extract([], ["en"])
    assert exc.value.kind == "none"


def test_typed_ip_block_from_list_raises_blocked():
    # The library's own IpBlocked (no "429"/"blocking" wording needed).
    from youtube_transcript_api import IpBlocked

    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    _subtitle_rate_limiter.clear_cooldown()

    def boom(self, vid):
        raise IpBlocked(vid)

    fake_api = type("Api", (), {"list": boom})()
    try:
        with (
            patch(
                "merlin.knowledge_sources.plugins.youtube.extractors.YouTubeTranscriptApi",
                return_value=fake_api,
            ),
            patch.object(_subtitle_rate_limiter, "wait"),
        ):
            with pytest.raises(SubtitlesUnavailable) as exc:
                SubtitleExtractor.extract_subtitles("vid", ["en"])
        cooled = _subtitle_rate_limiter.in_cooldown()
    finally:
        _subtitle_rate_limiter.clear_cooldown()

    assert exc.value.kind == "blocked"
    assert cooled


def test_transcripts_disabled_raises_none_without_cooldown():
    from youtube_transcript_api import TranscriptsDisabled

    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    _subtitle_rate_limiter.clear_cooldown()

    def boom(self, vid):
        raise TranscriptsDisabled(vid)

    fake_api = type("Api", (), {"list": boom})()
    with (
        patch(
            "merlin.knowledge_sources.plugins.youtube.extractors.YouTubeTranscriptApi",
            return_value=fake_api,
        ),
        patch.object(_subtitle_rate_limiter, "wait"),
    ):
        with pytest.raises(SubtitlesUnavailable) as exc:
            SubtitleExtractor.extract_subtitles("vid", ["en"])

    assert exc.value.kind == "none"
    assert not _subtitle_rate_limiter.in_cooldown()


def test_other_error_raises_error_with_short_detail():
    from merlin.knowledge_sources.plugins.youtube.extractors import (
        _subtitle_rate_limiter,
    )

    _subtitle_rate_limiter.clear_cooldown()

    def boom(self, vid):
        raise ConnectionError("connection reset by peer\nlong traceback text")

    fake_api = type("Api", (), {"list": boom})()
    with (
        patch(
            "merlin.knowledge_sources.plugins.youtube.extractors.YouTubeTranscriptApi",
            return_value=fake_api,
        ),
        patch.object(_subtitle_rate_limiter, "wait"),
    ):
        with pytest.raises(SubtitlesUnavailable) as exc:
            SubtitleExtractor.extract_subtitles("vid", ["en"])

    assert exc.value.kind == "error"
    assert exc.value.detail == "connection reset by peer"
