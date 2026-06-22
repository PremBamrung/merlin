"""Unit tests for the Groq audio-transcription chunking/stitching logic.

These exercise the pure conversion + the chunk-stitching offset math without
touching the network or ffmpeg (the HTTP POST and the split are mocked).
"""

from unittest.mock import patch

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
        patch.object(AudioTranscriber, "_post_audio", side_effect=chunk_results),
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
        patch.object(AudioTranscriber, "_post_audio", side_effect=chunk_results),
    ):
        ok, subs, err, language = AudioTranscriber._transcribe_chunked("big.mp3")

    assert not ok
    assert subs is None
    assert language is None
    assert "Chunk 2/2 failed" in err
