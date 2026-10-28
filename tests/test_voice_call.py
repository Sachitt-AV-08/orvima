"""Tests for orvima.voice_call module."""

from orvima.voice_call import (
    voice_call_speak,
    voice_call_listen,
    voice_call_status,
    voice_call_transcript,
    voice_call_hangup,
    voice_call_webrtc,
    VOICE_CALL_TOOLS,
)


def test_voice_call_status_idle():
    r = voice_call_status()
    assert r["ok"] is True
    assert r["active"] is False


def test_voice_call_transcript_empty():
    r = voice_call_transcript()
    assert r["ok"] is True


def test_voice_call_hangup_no_active():
    r = voice_call_hangup()
    assert r["ok"] is False


def test_voice_call_webrtc():
    r = voice_call_webrtc()
    assert r["ok"] is True
    assert r["mode"] == "webrtc"


def test_voice_call_listen_silent():
    r = voice_call_listen(duration=1.0)
    assert r["ok"] is True


def test_voice_call_speak():
    r = voice_call_speak("Hello, this is a test.")
    assert r["ok"] is True
    assert r["played"] is True


def test_voice_call_tools_tuple():
    assert len(VOICE_CALL_TOOLS) == 7


def test_voice_call_tools_annotated():
    from orvima.tool_annotations import for_tool
    for fn in VOICE_CALL_TOOLS:
        ann = for_tool(fn.__name__)
        assert ann is not None