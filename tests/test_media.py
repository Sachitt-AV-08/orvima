"""Pins orvima.media parsing and tool behavior (no network)."""

from __future__ import annotations

import json
from unittest.mock import patch

from orvima import media


def test_parse_vtt_basic():
    text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello <b>world</b>\n\n00:00:03.000 --> 00:00:04.000\nAgain\n"
    assert media._parse_vtt(text) == "Hello world Again"


def test_parse_vtt_dedup():
    text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nSame\n\n00:00:03.000 --> 00:00:04.000\nSame\n"
    assert media._parse_vtt(text) == "Same"


def test_parse_srt_basic():
    text = "1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n"
    assert media._parse_srt(text) == "Hello World"


def test_youtube_transcript_missing_ytdlp():
    with patch("orvima.media.subprocess.run", side_effect=FileNotFoundError("yt-dlp")):
        res = media.youtube_transcript("http://example.com")
    assert res["ok"] is False
    assert "yt-dlp" in res["error"]


def test_youtube_transcript_nonzero_returncode():
    class R:
        returncode = 1
        stderr = "some error\n"
        stdout = ""
    with patch("orvima.media.subprocess.run", return_value=R()):
        res = media.youtube_transcript("http://example.com")
    assert res["ok"] is False
    assert "some error" in res["error"]


def test_youtube_transcript_success_no_subs():
    info = {"title": "T", "duration": 10}
    class R:
        returncode = 0
        stderr = ""
        stdout = json.dumps(info)
    with patch("orvima.media.subprocess.run", return_value=R()):
        res = media.youtube_transcript("http://example.com", language="en")
    assert res["ok"] is True
    assert res["title"] == "T"
    assert res["duration"] == 10
    assert res["transcript"] == ""


def test_youtube_transcript_exception():
    with patch("orvima.media.subprocess.run", side_effect=RuntimeError("boom")):
        res = media.youtube_transcript("http://example.com")
    assert res["ok"] is False
    assert "boom" in res["error"]


def test_youtube_search_missing_ytdlp():
    with patch("orvima.media.subprocess.run", side_effect=FileNotFoundError("yt-dlp")):
        res = media.youtube_search("query")
    assert res["ok"] is False
    assert "yt-dlp" in res["error"]


def test_youtube_search_success():
    lines = [
        json.dumps({"title": "A", "webpage_url": "u1", "duration": 5, "channel": "c1", "view_count": 3}),
        "not json",
        json.dumps({"title": "B", "webpage_url": "u2"}),
    ]
    class R:
        returncode = 0
        stderr = ""
        stdout = "\n".join(lines)
    with patch("orvima.media.subprocess.run", return_value=R()):
        res = media.youtube_search("q", limit=2)
    assert res["ok"] is True
    assert res["query"] == "q"
    assert len(res["results"]) == 2
    assert res["results"][0]["title"] == "A"


def test_youtube_search_nonzero():
    class R:
        returncode = 2
        stderr = "fail"
        stdout = ""
    with patch("orvima.media.subprocess.run", return_value=R()):
        res = media.youtube_search("q")
    assert res["ok"] is False


def test_music_search_delegates():
    with patch.object(media, "youtube_search", return_value={"ok": True, "results": []}) as ys:
        res = media.music_search("abc", limit=3)
    ys.assert_called_once_with("abc music", limit=3)
    assert res["ok"] is True


def test_music_play_missing_ytdlp():
    with patch("orvima.media.subprocess.run", side_effect=FileNotFoundError("yt-dlp")):
        res = media.music_play("http://example.com")
    assert res["ok"] is False
    assert "yt-dlp" in res["error"]


def test_music_play_download_failure():
    class R:
        returncode = 1
        stderr = "download error"
        stdout = ""
    with patch("orvima.media.subprocess.run", return_value=R()):
        res = media.music_play("http://example.com")
    assert res["ok"] is False
    assert "download error" in res["error"]


def test_media_tools_tuple():
    assert len(media.MEDIA_TOOLS) == 4
