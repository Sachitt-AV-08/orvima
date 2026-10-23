"""Focused tests for the seven warning fixes in W7/W9/W10/W11/W12/W13/W14."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orvima import compute, gate, tools, vision, voice


def test_unit_convert_identity_and_temperature_matrix():
    assert compute.unit_convert(5, "m", "m")["result"] == 5
    assert compute.unit_convert(0, "c", "f")["result"] == 32.0
    assert compute.unit_convert(32, "f", "c")["result"] == 0.0
    assert compute.unit_convert(273.15, "k", "c")["result"] == 0.0
    assert compute.unit_convert(0, "c", "k")["result"] == 273.15
    assert compute.unit_convert(300, "k", "f")["result"] == 80.33
    assert compute.unit_convert(300, "k", "k")["result"] == 300
    unknown = compute.unit_convert(1, "foo", "bar")
    assert unknown["ok"] is False


def test_math_plot_data_honours_variable():
    result = compute.math_plot_data("t**2", variable="t")
    assert result["ok"] is True
    assert result["variable"] == "t"
    assert result["y"][0] == 100.0


def test_gate_functions_do_not_raise():
    assert gate.gate_classify("browse_snapshot", {})["ok"] is True
    assert gate.gate_describe_action("browse_snapshot", {})["ok"] is True
    assert gate.gate_risk_concepts("anything")["ok"] is True


def test_browse_snapshot_offset_guard():
    class FakeBrowser:
        def snapshot(self):
            return {"items": [{"a": 1}, {"b": 2}], "body": "hi"}

    bad = tools.tool_browse_snapshot(FakeBrowser(), offset="abc")
    assert bad["ok"] is True
    assert bad["offset"] == 0

    good = tools.tool_browse_snapshot(FakeBrowser(), offset=1)
    assert good["offset"] == 1


def test_browse_set_files_rejects_string_paths():
    class FakeBrowser:
        def set_files(self, sel, paths):
            return {"pageSaw": paths}

    result = tools.tool_browse_set_files(FakeBrowser(), "abc.txt", selector="#x")
    assert result["ok"] is False
    assert "list" in result["error"]

    ok = tools.tool_browse_set_files(FakeBrowser(), ["x.txt"], selector="#x")
    assert ok["ok"] is True


def test_vision_video_frames_positions_in_range():
    import cv2
    import numpy as np

    path = str(Path(__file__).parent / "tmp_video.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 24))
    for i in range(12):
        writer.write(np.full((24, 32, 3), i * 10, dtype="uint8"))
    writer.release()

    try:
        result = vision.vision_video_frames(path, count=100)
        assert result["ok"] is True
        assert result["saved"] == 12
        for frame in result["frames"]:
            assert 0 <= frame["frame_no"] < result["total_frames"]

        # positions never exceed total-1 for a modest request either
        result2 = vision.vision_video_frames(path, count=5)
        for frame in result2["frames"]:
            assert 0 <= frame["frame_no"] < result2["total_frames"]
        assert result2["ok"] is True

        assert vision.vision_video_frames(path, count=0)["ok"] is False
        assert vision.vision_video_frames(path, count=-1)["ok"] is False
    finally:
        Path(path).unlink(missing_ok=True)


def test_voice_generate_audio_bytes_under_running_loop(monkeypatch):
    async def _fake(text, voice, rate):
        return b"audio"

    monkeypatch.setattr(voice, "_edge_tts_generate", _fake)
    monkeypatch.setattr(voice, "_EDGE_AVAILABLE", True)
    monkeypatch.setattr(voice, "_NEST_ASYNCIO_AVAILABLE", False)
    monkeypatch.setattr(voice, "_nest_asyncio", None)

    async def main():
        value = voice._generate_audio_bytes("hi", "v", "0%")
        assert value == b"audio"

    asyncio.run(main())
