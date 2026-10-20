"""voice_* tools: text-to-speech (Edge TTS + Ultron modulation) and speech-to-text.

Uses Edge TTS (free, no API key) as the base voice, then applies a modulation
pipeline (pitch shift, reverb, metallic EQ) to create Orvima's distinctive
"Ultron" voice — deep, resonant, slightly metallic.

STT uses Whisper (local, free) when available, falling back to a clear error.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np

try:
    import edge_tts
    _EDGE_AVAILABLE = True
except ImportError:
    _EDGE_AVAILABLE = False

try:
    import sounddevice as sd
    import soundfile as sf
    _AUDIO_AVAILABLE = True
except ImportError:
    _AUDIO_AVAILABLE = False

try:
    from scipy import signal
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

# Ultron style parameters
_STYLES = {
    "ultron": {"pitch_shift": -2.5, "reverb": 0.3, "metallic": True, "speed": 0.95},
    "neutral": {"pitch_shift": 0.0, "reverb": 0.0, "metallic": False, "speed": 1.0},
    "calm": {"pitch_shift": -1.0, "reverb": 0.15, "metallic": False, "speed": 0.9},
}

_CURRENT_STYLE = "ultron"
_EDGE_VOICE = "en-US-GuyNeural"  # deep male voice


def _modulate(audio: np.ndarray, sr: int, style: str) -> np.ndarray:
    """Apply Ultron-style modulation to raw audio."""
    params = _STYLES.get(style, _STYLES["ultron"])
    out = audio.copy()

    # Pitch shift via resampling
    if params["pitch_shift"] != 0 and _SCIPY_AVAILABLE:
        factor = 2 ** (params["pitch_shift"] / 12.0)
        # Simple pitch shift: resample then trim/pad
        new_len = int(len(out) / factor)
        if new_len > 0:
            out = signal.resample(out, new_len)
            # Pad or trim to original length
            if len(out) < len(audio):
                out = np.pad(out, (0, len(audio) - len(out)))
            elif len(out) > len(audio):
                out = out[:len(audio)]

    # Metallic EQ: boost 2-4kHz
    if params["metallic"] and _SCIPY_AVAILABLE:
        nyq = sr / 2.0
        low = 2000 / nyq
        high = 4000 / nyq
        if high < 1.0:
            b, a = signal.butter(2, [low, high], btype="band")
            filtered = signal.filtfilt(b, a, out)
            out = out + 0.3 * filtered

    # Reverb (simple delay-based)
    if params["reverb"] > 0:
        delay_samples = int(sr * 0.04)
        if delay_samples < len(out):
            reverb = np.zeros_like(out)
            reverb[delay_samples:] = out[:-delay_samples] * params["reverb"]
            out = out + reverb

    # Normalize
    peak = np.max(np.abs(out))
    if peak > 0:
        out = out / peak * 0.9

    return out.astype(np.float32)


async def _edge_tts_generate(text: str, voice: str, rate: str) -> bytes:
    """Generate speech using Edge TTS."""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data


def voice_say(text: str, style: str | None = None, play: bool = True) -> dict:
    """Speak text using Orvima's voice (Edge TTS + Ultron modulation).

    style: "ultron" (default), "neutral", "calm".
    play: if True, plays audio through speakers.
    Returns {"ok": True, "audio_path": ...} or error.
    """
    if not _EDGE_AVAILABLE:
        return {"ok": False, "error": "edge-tts not installed: pip install edge-tts"}
    if not _AUDIO_AVAILABLE:
        return {"ok": False, "error": "soundfile/sounddevice not installed"}

    style = style or _CURRENT_STYLE
    params = _STYLES.get(style, _STYLES["ultron"])
    rate = f"{int((params['speed'] - 1) * 100):+d}%"

    try:
        import asyncio
        audio_bytes = asyncio.run(_edge_tts_generate(text, _EDGE_VOICE, rate))

        # Save to temp file and read back as numpy
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        # Read audio
        data, sr = sf.read(tmp_path)
        if data.ndim > 1:
            data = data.mean(axis=1)

        # Modulate
        modulated = _modulate(data, sr, style)

        # Save modulated audio
        out_path = tmp_path.replace(".mp3", "_orvima.wav")
        sf.write(out_path, modulated, sr)

        # Play
        if play:
            sd.play(modulated, sr)
            sd.wait()

        # Cleanup
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        return {"ok": True, "audio_path": out_path, "style": style, "text": text}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def voice_listen(duration: float = 5.0) -> dict:
    """Listen for speech and transcribe using Whisper (local).

    Records `duration` seconds of audio, then transcribes.
    """
    try:
        import whisper
    except ImportError:
        return {"ok": False, "error": "whisper not installed: pip install openai-whisper"}

    if not _AUDIO_AVAILABLE:
        return {"ok": False, "error": "sounddevice not installed"}

    try:
        sr = 16000
        recording = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="float32")
        sd.wait()
        audio = recording.flatten()

        model = whisper.load_model("base")
        result = model.transcribe(audio, fp16=False)
        return {"ok": True, "text": result["text"].strip(), "language": result.get("language", "en")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def voice_set_style(style: str) -> dict:
    """Set the current voice style: 'ultron', 'neutral', or 'calm'."""
    global _CURRENT_STYLE
    if style not in _STYLES:
        return {"ok": False, "error": f"unknown style {style!r}; choose from {list(_STYLES)}"}
    _CURRENT_STYLE = style
    return {"ok": True, "style": style}


def voice_list_styles() -> dict:
    """List available voice styles."""
    return {"ok": True, "styles": list(_STYLES.keys()), "current": _CURRENT_STYLE}


VOICE_TOOLS = (
    voice_say,
    voice_listen,
    voice_set_style,
    voice_list_styles,
)
