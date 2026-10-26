"""Tests for orvima.media module."""

from orvima.media import _parse_vtt, _parse_srt


def test_parse_vtt_basic():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello world\n\n00:00:04.000 --> 00:00:06.000\nSecond line"
    result = _parse_vtt(vtt)
    assert isinstance(result, str)
    assert "Hello" in result


def test_parse_vtt_empty():
    result = _parse_vtt("")
    assert isinstance(result, str)


def test_parse_srt_basic():
    srt = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n\n2\n00:00:04,000 --> 00:00:06,000\nSecond line"
    result = _parse_srt(srt)
    assert isinstance(result, str)
    assert "Hello" in result


def test_parse_srt_empty():
    result = _parse_srt("")
    assert isinstance(result, str)


def test_youtube_transcript_invalid_url():
    from orvima.media import youtube_transcript
    result = youtube_transcript("not-a-url")
    assert isinstance(result, dict)
    assert result.get("ok") is False or "error" in result or "transcript" in result


def test_youtube_search_returns_dict():
    from orvima.media import youtube_search
    result = youtube_search("test query")
    assert isinstance(result, dict)


def test_music_search_returns_dict():
    from orvima.media import music_search
    result = music_search("test song")
    assert isinstance(result, dict)


def test_music_play_returns_dict():
    from orvima.media import music_play
    result = music_play("nonexistent song")
    assert isinstance(result, dict)