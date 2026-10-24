"""Pins orvima.voice module behavior (no network/audio required)."""

from __future__ import annotations

import pytest

from orvima import voice


@pytest.fixture(autouse=True)
def _restore_style():
    original = voice._CURRENT_STYLE
    yield
    voice._CURRENT_STYLE = original


def test_list_styles():
    res = voice.voice_list_styles()
    assert res["ok"] is True
    assert "ultron" in res["styles"]
    assert res["current"] in res["styles"]


def test_set_style_valid_and_invalid():
    res = voice.voice_set_style("neutral")
    assert res == {"ok": True, "style": "neutral"}
    assert voice._CURRENT_STYLE == "neutral"

    res = voice.voice_set_style("nope")
    assert res["ok"] is False
    assert "unknown style" in res["error"]


def test_modulate_empty_audio():
    import numpy as np
    out = voice._modulate(np.zeros(0, dtype=np.float32), 16000, "neutral")
    assert out.size == 0
    # unknown style falls back to ultron params without crashing
    out2 = voice._modulate(None, 16000, "unknown")
    assert out2.size == 0


def test_voice_say_empty_text(monkeypatch):
    monkeypatch.setattr(voice, "_EDGE_AVAILABLE", True)
    monkeypatch.setattr(voice, "_AUDIO_AVAILABLE", True)
    res = voice.voice_say("")
    assert res["ok"] is False
    assert "non-empty" in res["error"]
    res = voice.voice_say("   ")
    assert res["ok"] is False
    res = voice.voice_say(123)  # type: ignore[arg-type]
    assert res["ok"] is False


def test_voice_say_unknown_style(monkeypatch):
    monkeypatch.setattr(voice, "_EDGE_AVAILABLE", True)
    monkeypatch.setattr(voice, "_AUDIO_AVAILABLE", True)
    res = voice.voice_say("hi", style="bogus")
    assert res["ok"] is False
    assert "unknown style" in res["error"]


def test_voice_say_missing_edge(monkeypatch):
    monkeypatch.setattr(voice, "_EDGE_AVAILABLE", False)
    res = voice.voice_say("hi")
    assert res["ok"] is False
    assert "edge-tts" in res["error"]


def test_voice_say_missing_audio(monkeypatch):
    monkeypatch.setattr(voice, "_EDGE_AVAILABLE", True)
    monkeypatch.setattr(voice, "_AUDIO_AVAILABLE", False)
    res = voice.voice_say("hi")
    assert res["ok"] is False
    assert "soundfile" in res["error"]


def test_voice_listen_invalid_duration(monkeypatch):
    import sys
    import types
    monkeypatch.setitem(sys.modules, "whisper", types.ModuleType("whisper"))
    monkeypatch.setattr(voice, "_AUDIO_AVAILABLE", True)
    res = voice.voice_listen(0)
    assert res["ok"] is False
    assert "positive" in res["error"]
    res = voice.voice_listen(-1)
    assert res["ok"] is False
    res = voice.voice_listen("x")  # type: ignore[arg-type]
    assert res["ok"] is False


def test_voice_listen_missing_whisper():
    # whisper may or may not be installed; either way no crash and ok/error dict
    res = voice.voice_listen(1)
    assert isinstance(res, dict)
    assert "ok" in res
    if not res["ok"]:
        assert "error" in res


def test_threaded_if_running_loop_off_threads():
    def fn(x):
        return x + 1
    wrapped = voice._threaded_if_running_loop(fn)
    assert wrapped(4) == 5


def test_generate_audio_bytes_no_running_loop(monkeypatch):
    # If edge missing we don't call; just ensure function exists callable
    assert callable(voice._generate_audio_bytes)


def test_voice_tools_tuple():
    assert voice.VOICE_TOOLS[0] is voice.voice_say
    assert len(voice.VOICE_TOOLS) == 5
