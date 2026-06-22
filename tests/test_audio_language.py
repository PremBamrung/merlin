"""Unit tests for Whisper-detected-language plumbing (no network, no LLM).

The audio fallback must summarise in the language Whisper actually detected
(e.g. French), not a hard-coded English. Whisper auto-detects the language
(no language is forced in the Groq request) and returns it in verbose_json;
these tests cover surfacing that value and normalising it to an ISO code.
"""

from unittest.mock import patch

from merlin.knowledge_sources.plugins.youtube.audio_transcriber import AudioTranscriber
from merlin.knowledge_sources.plugins.youtube.plugin import _normalize_language


def test_normalize_language_full_name_to_code():
    assert _normalize_language("french") == "fr"
    assert _normalize_language("ENGLISH") == "en"


def test_normalize_language_passes_through_known_code():
    assert _normalize_language("fr") == "fr"
    assert _normalize_language("fr-FR") == "fr"
    assert _normalize_language("pt_BR") == "pt"


def test_normalize_language_unknown_or_empty_is_none():
    assert _normalize_language(None) is None
    assert _normalize_language("") is None
    assert _normalize_language("klingon") is None


def test_transcribe_audio_surfaces_detected_language():
    # A small (non-chunked) file: transcribe_audio returns the raw Whisper
    # language alongside the subtitles.
    result = {
        "segments": [{"start": 0.0, "end": 2.0, "text": "bonjour"}],
        "duration": 2.0,
        "language": "french",
    }
    with (
        patch.object(
            AudioTranscriber, "_post_audio", return_value=(True, result, None)
        ),
        patch(
            "merlin.knowledge_sources.plugins.youtube.audio_transcriber.os.path.getsize",
            return_value=1024,
        ),
        patch(
            "merlin.knowledge_sources.plugins.youtube.audio_transcriber.GROQ_API_KEY",
            "test-key",
        ),
    ):
        ok, subs, err, language = AudioTranscriber.transcribe_audio("small.mp3")

    assert ok and err is None
    assert subs == [{"start": 0.0, "duration": 2.0, "text": "bonjour"}]
    assert language == "french"
    assert _normalize_language(language) == "fr"
