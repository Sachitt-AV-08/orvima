"""voice_call_* tools: free voice calling via local audio.

Uses sounddevice for mic/speaker I/O, faster-whisper for STT (local, free),
and Edge TTS (existing voice module) for TTS. No API keys, no cloud, no cost.

Supports:
- Local audio mode: mic → STT → TTS → speaker (in-person/intercom)
- WebRTC peer-to-peer (future): browser-based remote calls
- SIP calling (future): free SIP providers
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

# Lazy-loaded whisper model
_whisper_model = None
_whisper_lock = threading.Lock()

# Active call state
_active_call = None
_call_lock = threading.Lock()


def _get_whisper_model(model_size: str = "base"):
    """Lazy-load the faster-whisper model."""
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            except Exception as exc:
                raise RuntimeError(f"Failed to load whisper model: {exc}") from None
    return _whisper_model


def _record_audio(duration: float = 5.0, sample_rate: int = 16000) -> np.ndarray:
    """Record audio from the default microphone."""
    try:
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
        return audio.flatten()
    except Exception as exc:
        raise RuntimeError(f"Microphone recording failed: {exc}") from None


def _play_audio(audio_path: str):
    """Play an audio file through the default speaker."""
    try:
        data, sr = sf.read(audio_path)
        sd.play(data, sr)
        sd.wait()
    except Exception as exc:
        raise RuntimeError(f"Audio playback failed: {exc}") from None


def _transcribe(audio: np.ndarray, sample_rate: int = 16000, language: str = "en") -> str:
    """Transcribe audio using faster-whisper."""
    try:
        model = _get_whisper_model()
        segments, info = model.transcribe(audio, language=language, beam_size=1)
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip()
    except Exception as exc:
        return f"[STT error: {exc}]"


def _synthesize_speech(text: str, voice: str = "vision", emotion: str = "neutral") -> str:
    """Synthesize speech using the existing voice module. Returns path to WAV."""
    try:
        from .voice import voice_say
        result = voice_say(text, style=voice, emotion=emotion)
        if isinstance(result, dict) and result.get("ok"):
            return result.get("path", result.get("file", ""))
        # Fallback: try direct
        return ""
    except Exception as exc:
        raise RuntimeError(f"TTS failed: {exc}") from None


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def voice_call_speak(text: str, voice: str = "vision", emotion: str = "neutral") -> dict:
    """Speak text through the default speaker (TTS)."""
    try:
        from .voice import voice_say
        result = voice_say(text, style=voice, emotion=emotion, play=True)
        if isinstance(result, dict) and result.get("ok"):
            return {"ok": True, "text": text, "voice": voice, "played": True}
        return {"ok": False, "error": result.get("error", "TTS failed") if isinstance(result, dict) else "TTS failed"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def voice_call_listen(duration: float = 5.0, language: str = "en") -> dict:
    """Listen to the microphone for `duration` seconds and transcribe."""
    try:
        audio = _record_audio(duration=duration)
        # Check for silence
        if np.max(np.abs(audio)) < 0.01:
            return {"ok": True, "transcript": "", "duration": duration, "silent": True}
        text = _transcribe(audio, language=language)
        return {"ok": True, "transcript": text, "duration": duration, "silent": False}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def voice_call_local(max_turns: int = 10, greeting: str = "Hello! I'm Orvima. How can I help you?") -> dict:
    """Start a local audio conversation (mic → STT → TTS → speaker).

    Loops for up to `max_turns` turns or until the user says 'goodbye'/'exit'/'quit'.
    """
    global _active_call
    with _call_lock:
        _active_call = {"type": "local", "started": time.time(), "turns": [], "status": "active"}

    transcript = []
    try:
        # Greet
        voice_call_speak(greeting, voice="vision")
        transcript.append({"role": "assistant", "text": greeting})

        for _turn in range(max_turns):
            # Listen
            result = voice_call_listen(duration=5.0)
            if not result.get("ok"):
                break
            user_text = result.get("transcript", "").strip()
            if not user_text:
                continue
            transcript.append({"role": "user", "text": user_text})

            # Check for exit
            if any(w in user_text.lower() for w in ("goodbye", "exit", "quit", "bye", "stop")):
                voice_call_speak("Goodbye! Have a great day.", voice="vision")
                transcript.append({"role": "assistant", "text": "Goodbye! Have a great day."})
                break

            # Route via errands
            response = _route_intent(user_text)
            voice_call_speak(response, voice="vision")
            transcript.append({"role": "assistant", "text": response})

        with _call_lock:
            if _active_call:
                _active_call["status"] = "completed"
                _active_call["turns"] = transcript

        # Save transcript
        _save_transcript("local", transcript)

        return {"ok": True, "mode": "local", "turns": len(transcript), "transcript": transcript}
    except Exception as exc:
        with _call_lock:
            if _active_call:
                _active_call["status"] = "error"
        return {"ok": False, "error": str(exc), "transcript": transcript}


def _route_intent(text: str) -> str:
    """Route user intent through errands recipes. Returns a response string."""
    # Try errands
    try:
        from errands import load_dir
        recipes_dir = os.environ.get("ORVIMA_RECIPES_DIR", str(Path.home() / ".orvima" / "recipes"))
        recipes = load_dir(recipes_dir) if Path(recipes_dir).is_dir() else []
        goal_lower = text.lower()
        for recipe in recipes:
            for trigger in recipe.triggers:
                if trigger.lower() in goal_lower:
                    return f"I found a recipe for {recipe.name}. {recipe.description or 'Let me help you with that.'}"
    except Exception:
        pass

    # Fallback: simple keyword responses
    text_lower = text.lower()
    if any(w in text_lower for w in ("hello", "hi", "hey")):
        return "Hello! How can I help you today?"
    if any(w in text_lower for w in ("help", "what can you do")):
        return "I can help you browse the web, send messages, set reminders, check email, and more."
    if any(w in text_lower for w in ("weather", "temperature")):
        return "I don't have weather data yet, but I can help you browse weather websites."
    if any(w in text_lower for w in ("time", "date")):
        import datetime
        now = datetime.datetime.now()
        return f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%B %d, %Y')}."
    if any(w in text_lower for w in ("thank", "thanks")):
        return "You're welcome! Is there anything else I can help with?"
    return f"I'm not sure how to help with that yet. You said: {text}. Could you rephrase?"


def voice_call_hangup() -> dict:
    """End the active call."""
    global _active_call
    with _call_lock:
        if _active_call is None:
            return {"ok": False, "error": "no active call"}
        _active_call["status"] = "ended"
        _active_call["ended"] = time.time()
        _save_transcript(_active_call.get("type", "unknown"), _active_call.get("turns", []))
        _active_call = None
    return {"ok": True, "message": "call ended"}


def voice_call_transcript() -> dict:
    """Get the current or last call transcript."""
    global _active_call
    with _call_lock:
        if _active_call:
            return {"ok": True, "status": _active_call.get("status"), "turns": _active_call.get("turns", [])}
    # Try to load last transcript
    calls_dir = Path.home() / ".orvima" / "calls"
    if calls_dir.is_dir():
        files = sorted(calls_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if files:
            import json
            data = json.loads(files[0].read_text(encoding="utf-8"))
            return {"ok": True, "status": "completed", "turns": data.get("turns", []), "file": str(files[0])}
    return {"ok": True, "status": "none", "turns": []}


def voice_call_status() -> dict:
    """Get the status of the active call."""
    global _active_call
    with _call_lock:
        if _active_call is None:
            return {"ok": True, "status": "idle", "active": False}
        elapsed = time.time() - _active_call.get("started", time.time())
        return {
            "ok": True,
            "status": _active_call.get("status", "unknown"),
            "active": True,
            "type": _active_call.get("type"),
            "turns": len(_active_call.get("turns", [])),
            "elapsed_seconds": round(elapsed, 1),
        }


def voice_call_webrtc(signal_url: str = "") -> dict:
    """Start a WebRTC peer-to-peer call.

    Opens a browser tab with a WebRTC client that connects peer-to-peer.
    Requires a signaling server (use a free one like PeerJS, or self-host).
    """
    try:
        import webbrowser
        if not signal_url:
            signal_url = os.environ.get("ORVIMA_WEBRTC_SIGNAL_URL", "https://peerjs.com")
        # Create a simple WebRTC page
        html = _webrtc_html(signal_url)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file:///{tmp.name}")
        return {"ok": True, "mode": "webrtc", "signal_url": signal_url, "page": tmp.name}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _webrtc_html(signal_url: str) -> str:
    return f"""<!DOCTYPE html>  # noqa: E501
<html><head><title>Orvima WebRTC Call</title></head>
<body style="background:#0D1117;color:#E6EDF3;font-family:Calibri,sans-serif;text-align:center;padding:40px;">
<h1 style="color:#F5A524;">Orvima Voice Call</h1>
<p>WebRTC peer-to-peer audio call</p>
<p>Signal server: {signal_url}</p>
<button onclick="startCall()">Start Call</button>
<button onclick="hangup()">Hang Up</button>
<p id="status">Idle</p>
<audio id="remoteAudio" autoplay></audio>
<script>
let pc, localStream;
async function startCall() {{
  document.getElementById('status').textContent = 'Connecting...';
  try {{
    localStream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
    pc = new RTCPeerConnection();
    localStream.getTracks().forEach(t => pc.addTrack(t, localStream));
    pc.ontrack = e => {{ document.getElementById('remoteAudio').srcObject = e.streams[0]; }};
    // Use PeerJS for signaling (free)
    const peer = new Peer();
    peer.on('open', id => {{
      document.getElementById('status').textContent = 'Your ID: ' + id;
      console.log('Peer ID:', id);
    }});
    peer.on('call', call => {{
      call.answer(localStream);
      call.on('stream', remoteStream => {{
        document.getElementById('remoteAudio').srcObject = remoteStream;
        document.getElementById('status').textContent = 'Connected!';
      }});
    }});
  }} catch (err) {{
    document.getElementById('status').textContent = 'Error: ' + err.message;
  }}
}}
function hangup() {{
  if (pc) pc.close();
  if (localStream) localStream.getTracks().forEach(t => t.stop());
  document.getElementById('status').textContent = 'Call ended';
}}
</script>
<script src="https://unpkg.com/peerjs@1.5.2/dist/peerjs.min.js"></script>
</body></html>"""


def _save_transcript(call_type: str, turns: list):
    """Save call transcript to ~/.orvima/calls/."""
    try:
        import json
        calls_dir = Path.home() / ".orvima" / "calls"
        calls_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = calls_dir / f"{call_type}_{ts}.json"
        path.write_text(json.dumps({"type": call_type, "turns": turns, "timestamp": ts}, indent=2), encoding="utf-8")
    except Exception:
        pass


# Tool tuple for MCP registration
VOICE_CALL_TOOLS = (
    voice_call_speak,
    voice_call_listen,
    voice_call_local,
    voice_call_hangup,
    voice_call_transcript,
    voice_call_status,
    voice_call_webrtc,
)
