"""Tests for orvima.voice module."""

from orvima.voice import voice_list_styles, voice_list_emotions, voice_set_style, voice_set_emotion


def test_voice_list_styles():
    result = voice_list_styles()
    assert isinstance(result, dict)
    assert result.get("ok") is True or "styles" in result or "personas" in result


def test_voice_list_emotions():
    result = voice_list_emotions()
    assert isinstance(result, dict)
    assert result.get("ok") is True or "emotions" in result


def test_voice_set_style_valid():
    result = voice_set_style("vision")
    assert isinstance(result, dict)


def test_voice_set_style_invalid():
    result = voice_set_style("nonexistent_style_xyz")
    assert isinstance(result, dict)


def test_voice_set_emotion_valid():
    result = voice_set_emotion("cheerful")
    assert isinstance(result, dict)


def test_voice_set_emotion_invalid():
    result = voice_set_emotion("nonexistent_emotion_xyz")
    assert isinstance(result, dict)


def test_build_ssml():
    from orvima.voice import _build_ssml
    result = _build_ssml("Hello world", "vision", "neutral")
    assert isinstance(result, str)
    assert "Hello" in result or "speak" in result


def test_cleanup_orphan_wavs():
    from orvima.voice import _cleanup_orphan_wavs
    # Should not raise
    _cleanup_orphan_wavs()