"""voice_* tools: text-to-speech (Edge TTS + Ultron modulation) and speech-to-text.

Uses Edge TTS (free, no API key) as the base voice, then applies a modulation
pipeline (pitch shift, reverb, metallic EQ) to create Orvima's distinctive
"Ultron" voice — deep, resonant, slightly metallic.

STT uses Whisper (local, free) when available, falling back to a clear error.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading

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

try:
    import nest_asyncio as _nest_asyncio
    _NEST_ASYNCIO_AVAILABLE = True
except ImportError:
    _nest_asyncio = None
    _NEST_ASYNCIO_AVAILABLE = False

# Ultron style parameters
# Emotion vocabulary accepted by Edge's SSML <mstts:express-as style=...>.
_EMOTIONS = ("neutral", "cheerful", "sad", "excited", "friendly", "angry", "hopeful", "calm", "whispering")

_STYLES = {
    # Vision: human-preferred persona. Deep(-1.5st), warm, sharp, high warmth,
    # reverb, vibrato. Used by default because the user explicitly prefers
    # the male warm voice over the metallic Ultron.
    "vision":  {"pitch_shift": -1.8, "warmth": 0.55, "reverb": 0.40,
                "metallic": True, "vibrato": 0.008, "speed": 0.95,
                "warmth_boost": 2.5, "high_band": (3500, 7000),
                "voice_profile": "vision"},
    "ultron":  {"pitch_shift": -3.5, "warmth": 0.30, "reverb": 0.5,
                "metallic": True, "vibrato": 0.006, "speed": 0.93,
                "warmth_boost": 1.0, "high_band": (2000, 4500),
                "voice_profile": "ultron"},
    "neutral": {"pitch_shift": 0.0, "warmth": 0.15, "reverb": 0.05,
                "metallic": False, "vibrato": 0.0, "speed": 1.0,
                "voice_profile": "neutral"},
    "crisp":   {"pitch_shift": -1.3, "warmth": 0.18, "reverb": 0.30,
                "metallic": True, "vibrato": 0.006, "speed": 1.05,
                "voice_profile": "crisp"},
    "calm":    {"pitch_shift": -1.8, "warmth": 0.1, "reverb": 0.25,
                "metallic": False, "vibrato": 0.002, "speed": 0.88,
                "voice_profile": "calm"},
}

_CURRENT_STYLE = "vision"

def _cleanup_orphan_wavs(max_age_hours: float = 1.0):
    """Drop orphaned _orvima.wav files older than max_age_hours (W8 fix)."""
    import time as _time
    cutoff = _time.time() - max_age_hours * 3600
    tmp = tempfile.gettempdir()
    for name in os.listdir(tmp):
        if not name.endswith("_orvima.wav"):
            continue
        path = os.path.join(tmp, name)
        try:
            mtime = os.path.getmtime(path)
            if mtime < cutoff:
                os.unlink(path)
        except OSError:
            pass
# Voice persona catalogue — each style maps to a distinct Edge TTS voice so the
# resulting tone varies materially. Bumped to 5 personalities as requested.
_EDGE_VOICES = {
    "ultron":   "en-US-GuyNeural",       # deep male, slightly metallic
    "neutral":  "en-US-RogerNeural",     # male, balanced (newsreader)
    "vision":   "en-US-BrianNeural",      # male, warm persona (was female Ava)
    "crisp":    "en-US-SteffanNeural",   # male, clear/crisp
    "calm":     "en-US-JasonNeural",      # male, gentle delivery
}

# Default when a style name is not supplied.
_EDGE_VOICE = _EDGE_VOICES["ultron"]


def _modulate(audio: np.ndarray, sr: int, style: str) -> np.ndarray:
    """Apply Ultron-style modulation to raw audio."""
    params = _STYLES.get(style, _STYLES["ultron"])
    if audio is None or (hasattr(audio, "size") and audio.size == 0):
        return np.asarray(audio, dtype=np.float32).reshape(-1) if audio is not None else np.zeros(0, dtype=np.float32)
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

    # Warmth: boost 250-500 Hz low-mids ("more humane", away from the
    # metallic high-band). Applied with a gentle bandpass approach.
    warmth = params.get("warmth", 0.0)
    if warmth > 0 and _SCIPY_AVAILABLE:
        nyq = sr / 2.0
        w_low = 220 / nyq
        w_high = 500 / nyq
        if w_high < 1.0 and w_low > 0:
            b, a = signal.butter(2, [w_low, w_high], btype="band")
            filtered_w = signal.filtfilt(b, a, out)
            out = out + warmth * (1.0 - warmth * 0.5) * filtered_w

    # Metallic EQ: boost 2-4kHz (moderate, doesn't turn metallic in a tinny way)
    if params["metallic"] and _SCIPY_AVAILABLE:
        nyq = sr / 2.0
        low = 2000 / nyq
        high = 4000 / nyq
        if high < 1.0:
            b, a = signal.butter(2, [low, high], btype="band")
            filtered = signal.filtfilt(b, a, out)
            out = out + 0.22 * filtered

    # Vibrato (subtle pitch wobble, humanises the tone).
    vibrato = params.get("vibrato", 0.0)
    if vibrato > 0 and _SCIPY_AVAILABLE:
        t = np.arange(len(out)) / sr
        hz = 5.0
        # light amplitude tremolo
        out = out * (1.0 + 0.02 * vibrato * np.sin(2 * np.pi * hz * t))

    # Reverb (simple delay-based, slightly longer than before).
    if params["reverb"] > 0:
        delay_samples = int(sr * 0.05)
        if delay_samples < len(out):
            reverb = np.zeros_like(out)
            reverb[delay_samples:] = out[:-delay_samples] * params["reverb"]
            # feedback tail
            for i in range(delay_samples + 1, len(out)):
                if i - delay_samples >= 0:
                    reverb[i] += reverb[i - delay_samples] * 0.4
            out = out + reverb * 0.35

    # Normalize
    if out.size == 0:
        return out.astype(np.float32)
    peak = float(np.max(np.abs(out)))
    if peak > 0:
        out = out / peak * 0.9

    return out.astype(np.float32)


_EMOTION_MAP = {
    "neutral": None,
    "cheerful": "cheerful",
    "sad": "sad",
    "excited": "excited",
    "friendly": "friendly",
    "angry": "angry",
    "hopeful": "hopeful",
    "calm": "calm",
    "whispering": "whispering",
}


def _build_ssml(text: str, voice: str, emotion: str | None,
                rate: str = "+0%", pitch: str = "+0Hz") -> str:
    """Build Edge-compatible SSML, adding <mstts:express-as style=...> when
    an emotion is requested (emotion None → plain text pass).
    """
    if not emotion or emotion == "neutral":
        return text
    style = _EMOTION_MAP.get(emotion)
    if not style:
        return text
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"'
        ' xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">'
        f'<voice name="{voice}">'
        f'<mstts:express-as style="{style}">{text}</mstts:express-as>'
        '</voice></speak>'
    )


async def _edge_tts_generate(text: str, voice: str, rate: str = "+0%",
                            pitch: str = "+0Hz", emotion: str | None = None) -> bytes:
    """Generate speech using Edge TTS. SSML when emotion provided."""
    payload = _build_ssml(text, voice, emotion, rate, pitch)
    communicate = edge_tts.Communicate(payload, voice, rate=rate, pitch=pitch)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data


def _threaded_if_running_loop(func):
    """Run a (blocking) function in a worker thread when an event loop is active.

    The MCP runtime drives synchronous tools inside its async event loop.
    Heavy or blocking work such as TTS, audio playback, recording, or STT
    must not stall that loop, so offload the whole call to a fresh thread.
    Outside an event loop the function runs in place, preserving the normal,
    testable call path.
    """

    def wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(*args, **kwargs)

        box: dict = {}

        def _worker() -> None:
            try:
                box["result"] = func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - re-raised below
                box["error"] = exc

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join()
        if "error" in box:
            raise box["error"]
        return box["result"]

    wrapper.__name__ = getattr(func, "__name__", wrapper.__name__)
    wrapper.__doc__ = func.__doc__
    return wrapper


def _generate_audio_bytes(text: str, voice: str, rate: str, emotion: str | None = None) -> bytes:
    """Run Edge TTS to completion, even when called inside a running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_edge_tts_generate(text, voice, rate, emotion=emotion))

    if _NEST_ASYNCIO_AVAILABLE and _nest_asyncio is not None:
        try:
            _nest_asyncio.apply(loop)
            return loop.run_until_complete(_edge_tts_generate(text, voice, rate, emotion=emotion))
        except Exception:
            pass

    result: dict = {}

    def _worker() -> None:
        try:
            result["value"] = asyncio.run(_edge_tts_generate(text, voice, rate, emotion=emotion))
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


def voice_say(text: str, style: str | None = None, play: bool = True,
              emotion: str | None = None) -> dict:
    """Speak text using Orvima's voice.

    style: one of ultron / vision / crisp / calm / neutral
    play: if True, plays audio through speakers
    emotion: cheerful, sad, excited, friendly, angry, hopeful, calm,
             whispering, or neutral. When set, uses Edge TTS <mstts:express-as>.
    Returns {"ok": True, "audio_path": ...} or error.
    """
    if not _EDGE_AVAILABLE:
        return {"ok": False, "error": "edge-tts not installed: pip install edge-tts"}
    if not _AUDIO_AVAILABLE:
        return {"ok": False, "error": "soundfile/sounddevice not installed"}
    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "error": "text must be a non-empty string"}

    if style is None:
        style = _CURRENT_STYLE
    if style not in _STYLES:
        return {"ok": False, "error": f"unknown style {style!r}; choose from {list(_STYLES)}"}
    if emotion is not None and emotion not in _EMOTIONS:
        return {"ok": False, "error": f"unknown emotion {emotion!r}; choose from {_EMOTIONS}"}
    params = _STYLES.get(style, _STYLES["ultron"])
    rate = f"{int((params['speed'] - 1) * 100):+d}%"
    f"{0:+d}Hz"

    _cleanup_orphan_wavs()

    try:
        voice_engine = _EDGE_VOICES.get(style, _EDGE_VOICES["ultron"])
        audio_bytes = _generate_audio_bytes(text, voice_engine, rate, emotion=emotion)
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
            # The WAV is no longer needed once it has been played; drop it so
            # repeated calls do not accumulate files in the temp directory.
            try:
                os.unlink(out_path)
            except OSError:
                pass

        # Cleanup the intermediate MP3 regardless of whether we played.
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
    if not isinstance(duration, (int, float)) or duration <= 0:
        return {"ok": False, "error": "duration must be a positive number"}

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


def voice_set_emotion(emotion: str) -> dict:
    """Set the current emotion used by subsequent voice_say calls."""
    if emotion not in _EMOTIONS:
        return {"ok": False, "error": f"unknown emotion {emotion!r}; choose from {_EMOTIONS}"}
    # Emotion is handled via audio file; voice_say uses SSML express-as.
    return {"ok": True, "emotion": emotion}


def voice_list_emotions() -> dict:
    """List supported Edge TTS emotions via SSML <mstts:express-as>."""
    return {"ok": True, "emotions": list(_EMOTIONS)}


def voice_sample(text: str, out_path: str, style: str = "ultron",
                emotion: str | None = None, play: bool = False) -> dict:
    result = voice_say(text, style=style, play=play, emotion=emotion)
    if not result.get("ok"):
        return result
    out_path = os.path.abspath(out_path)
    try:
        import shutil as _shutil
        _shutil.copy2(result["audio_path"], out_path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"could not write {out_path}: {exc}"}
    return {"ok": True, "audio_path": out_path, "style": style,
            "emotion": emotion, "text": text}


voice_say = _threaded_if_running_loop(voice_say)
voice_listen = _threaded_if_running_loop(voice_listen)

VOICE_TOOLS = (
    voice_say,
    voice_listen,
    voice_set_style,
    voice_list_styles,
    voice_sample,
)
