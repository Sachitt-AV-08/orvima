"""media_* tools: YouTube transcripts/search and music playback.

Uses yt-dlp (free, local) for YouTube data and Edge TTS / system player
for music. All operations are local-first.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


def youtube_transcript(url: str, language: str = "en") -> dict:
    """Fetch the transcript/subtitles of a YouTube video.

    Returns {"ok": True, "transcript": "...", "title": ..., "duration": ...}.
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--skip-download", url],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip()[:500]}

        info = json.loads(result.stdout)
        title = info.get("title", "")
        duration = info.get("duration", 0)

        # Try to get subtitles
        subs = info.get("subtitles", {}) or info.get("automatic_captions", {})
        lang_subs = subs.get(language, [])
        transcript = ""

        if lang_subs:
            # Download the subtitle file
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run(
                    ["yt-dlp", "--write-sub", "--sub-lang", language, "--skip-download",
                     "-o", f"{tmpdir}/%(id)s.%(ext)s", url],
                    capture_output=True, text=True, timeout=60,
                )
                # Find the subtitle file
                for f in Path(tmpdir).glob("*.vtt"):
                    transcript = _parse_vtt(f.read_text(encoding="utf-8"))
                    break
                for f in Path(tmpdir).glob("*.srt"):
                    transcript = _parse_srt(f.read_text(encoding="utf-8"))
                    break

        return {"ok": True, "title": title, "duration": duration, "transcript": transcript[:5000]}
    except FileNotFoundError:
        return {"ok": False, "error": "yt-dlp not installed: pip install yt-dlp"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _parse_vtt(text: str) -> str:
    """Extract plain text from WebVTT subtitles."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line or line.isdigit():
            continue
        # Remove VTT tags
        import re
        line = re.sub(r"<[^>]+>", "", line)
        if line and line not in lines:
            lines.append(line)
    return " ".join(lines)


def _parse_srt(text: str) -> str:
    """Extract plain text from SRT subtitles."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        if line not in lines:
            lines.append(line)
    return " ".join(lines)


def youtube_search(query: str, limit: int = 5) -> dict:
    """Search YouTube and return top results (title, url, duration, channel)."""
    try:
        result = subprocess.run(
            ["yt-dlp", f"ytsearch{limit}:{query}", "--dump-json", "--skip-download", "--no-warnings"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip()[:500]}

        results = []
        for line in result.stdout.strip().splitlines():
            try:
                info = json.loads(line)
                results.append({
                    "title": info.get("title", ""),
                    "url": info.get("webpage_url", ""),
                    "duration": info.get("duration", 0),
                    "channel": info.get("channel", info.get("uploader", "")),
                    "views": info.get("view_count", 0),
                })
            except json.JSONDecodeError:
                continue

        return {"ok": True, "query": query, "results": results}
    except FileNotFoundError:
        return {"ok": False, "error": "yt-dlp not installed: pip install yt-dlp"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def music_search(query: str, limit: int = 5) -> dict:
    """Search YouTube for music and return playable results."""
    return youtube_search(f"{query} music", limit=limit)


def music_play(url: str) -> dict:
    """Play a YouTube video's audio using the system player.

    Downloads audio to a persistent file and plays it via the default media player.
    """
    try:
        # Use persistent directory so the file survives after function returns
        media_dir = Path.home() / ".orvima" / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        out_path = media_dir / "audio.mp3"

        result = subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", str(out_path), url],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip()[:500]}

        # Find the downloaded file
        audio_files = list(media_dir.glob("*.mp3"))
        if not audio_files:
            return {"ok": False, "error": "no audio file downloaded"}

        # Play via system default
        import os
        if os.name == "nt":
            os.startfile(str(audio_files[0]))
        else:
            subprocess.Popen(["xdg-open", str(audio_files[0])])

        return {"ok": True, "url": url, "file": str(audio_files[0])}
    except FileNotFoundError:
        return {"ok": False, "error": "yt-dlp not installed: pip install yt-dlp"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


MEDIA_TOOLS = (
    youtube_transcript,
    youtube_search,
    music_search,
    music_play,
)
