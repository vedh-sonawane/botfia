"""Piper text-to-speech for Botfia, behind a small swappable class.

Botfia narrates out loud through the Sony Bluetooth speaker. We use Piper
(https://github.com/rhasspy/piper): a small, fast, local neural TTS that runs
fine on a Pi 5 with 1GB RAM. No cloud, no account, no cost.

Everything here degrades gracefully. If the `piper` binary, a voice model, or
an audio player is missing, every call logs a line and does nothing. A laptop
with no speaker, or the game simulation, will never crash because of audio.

How it works:
  - say(text)       synthesize `text` to a wav and play it.
  - prerender(text) synthesize to a cached wav and return its path (no playback),
                    so the game can render upcoming lines ahead of time and play
                    them instantly later. The cache key is a hash of text + voice.
  - is_available()  True only if both piper and a player are usable right now.

--------------------------------------------------------------------------------
Installing Piper on the Pi (Raspberry Pi OS, 64-bit):

  # 1. Download the piper binary for arm64 (check the releases page for the
  #    latest version; this is the ARM64 build):
  cd ~
  wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
  tar -xzf piper_linux_aarch64.tar.gz      # creates a ./piper/ folder
  # Put it on PATH, or set BOTFIA_PIPER_BIN to ~/piper/piper (see config below).

  # 2. Download a voice. Each voice is two files that live together:
  #    <name>.onnx  and  <name>.onnx.json. Voices are on Hugging Face:
  #    https://huggingface.co/rhasspy/piper-voices/tree/main/en
  #    For 1GB RAM, prefer "low" or "medium" quality (not "high"):
  mkdir -p ~/piper-voices && cd ~/piper-voices
  # Example (calm US male, medium):
  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx
  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json

  # 3. Point Botfia at it (one of):
  #      - set BOTFIA_PIPER_VOICE=/home/pi/piper-voices/en_US-ryan-medium.onnx
  #      - or put piper_voice in pi/config.py CONFIG (another process owns that).
  #      - or drop the .onnx under pi/audio/voices/ (auto-discovered).

  # 4. Audio out: on the Pi, aplay (ALSA) plays wavs to the default device,
  #    which routes to the Sony speaker once it is the default Bluetooth sink.

--------------------------------------------------------------------------------
Candidate calm voices for the audition (all low/medium quality, 1GB-friendly).
These match the style rules: a quiet, dry, serious narrator. Run:

    python -m pi.audio.tts --audition

and keep the one that sounds calmest to you:

  - en_US-ryan-medium, measured US male, even and unhurried.
  - en_GB-alba-medium, soft Scottish English female, understated.
  - en_US-lessac-medium, neutral US female, clear and flat.
  - en_GB-northern_english_male-medium, low, dry UK male.

The audition downloads any it is missing into pi/audio/voices/ and speaks the
same sample line through each. Set the winner as BOTFIA_PIPER_VOICE.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger("botfia.tts")

# --- Config (defensive) -------------------------------------------------------
# pi/config.py is owned by another process and may not exist yet. Import it if we
# can; otherwise fall back to env vars and sensible defaults. Never crash here.
try:
    from ..config import CONFIG  # type: ignore
except Exception:  # pragma: no cover - config not present on this machine
    CONFIG = {}


def _cfg(key, env, default):
    """Config value by precedence: CONFIG dict -> env var -> default."""
    try:
        if isinstance(CONFIG, dict) and CONFIG.get(key) is not None:
            return CONFIG[key]
    except Exception:
        pass
    val = os.environ.get(env)
    return val if val is not None else default


_AUDIO_DIR = Path(__file__).resolve().parent
_VOICES_DIR = _AUDIO_DIR / "voices"
_CACHE_DIR = _AUDIO_DIR / "cache"

# A short, in-style sample line for the audition.
_SAMPLE_LINE = "The town is asleep. Close your eyes."

# Audition candidates: (voice_name, hugging_face_relative_path). Low/medium only.
_AUDITION_VOICES = [
    ("en_US-ryan-medium", "en/en_US/ryan/medium/en_US-ryan-medium"),
    ("en_GB-alba-medium", "en/en_GB/alba/medium/en_GB-alba-medium"),
    ("en_US-lessac-medium", "en/en_US/lessac/medium/en_US-lessac-medium"),
    ("en_GB-northern_english_male-medium",
     "en/en_GB/northern_english_male/medium/en_GB-northern_english_male-medium"),
]
_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"


class TTS:
    """Piper TTS wrapper. Swap this class out to change TTS engines."""

    def __init__(self, voice=None, piper_bin=None, volume=None):
        # Resolve the piper binary: explicit arg -> config/env -> PATH.
        self.piper_bin = (
            piper_bin
            or _cfg("piper_bin", "BOTFIA_PIPER_BIN", None)
            or shutil.which("piper")
        )
        # Resolve the voice .onnx: explicit arg -> config/env -> first in voices/.
        self.voice = voice or _cfg("piper_voice", "BOTFIA_PIPER_VOICE", None)
        if not self.voice:
            self.voice = self._discover_voice()
        # Volume 0.0-1.0; only applied by players that support it (ffplay/paplay).
        try:
            self.volume = float(_cfg("tts_volume", "BOTFIA_TTS_VOLUME", volume or 1.0))
        except (TypeError, ValueError):
            self.volume = 1.0
        # Deepen / slow the voice so it reads calm and serious, not chirpy.
        # pitch < 1.0 = deeper; tempo < 1.0 = slower. Applied with ffmpeg rubberband.
        try:
            self.pitch = float(_cfg("tts_pitch", "BOTFIA_TTS_PITCH", 0.84))
        except (TypeError, ValueError):
            self.pitch = 0.84
        try:
            self.tempo = float(_cfg("tts_tempo", "BOTFIA_TTS_TEMPO", 0.95))
        except (TypeError, ValueError):
            self.tempo = 0.95

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # --- availability ---------------------------------------------------------
    @staticmethod
    def _discover_voice():
        """Return the first .onnx voice under pi/audio/voices/, or None."""
        if _VOICES_DIR.is_dir():
            for onnx in sorted(_VOICES_DIR.glob("*.onnx")):
                return str(onnx)
        return None

    def is_available(self):
        """True only if piper, a voice model, and a player are all usable."""
        if not self.piper_bin or not Path(str(self.piper_bin)).exists() and not shutil.which(str(self.piper_bin)):
            return False
        if not self.voice or not Path(str(self.voice)).exists():
            return False
        if _pick_player() is None:
            return False
        return True

    # --- synthesis ------------------------------------------------------------
    def _cache_path(self, text):
        key = f"{self.voice}|{self.pitch}|{self.tempo}|{text}".encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()[:32]
        return _CACHE_DIR / f"{digest}.wav"

    def _synthesize(self, text, out_path):
        """Run piper to render `text` into out_path (a wav). Return True on success."""
        if not self.piper_bin or not self.voice:
            log.warning("TTS unavailable (piper_bin=%s voice=%s); skipping synth",
                        self.piper_bin, self.voice)
            return False
        if not Path(str(self.voice)).exists():
            log.warning("TTS voice model missing: %s; skipping synth", self.voice)
            return False
        cmd = [str(self.piper_bin), "--model", str(self.voice),
               "--output_file", str(out_path)]
        try:
            # Piper reads the text to speak from stdin.
            subprocess.run(
                cmd, input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("piper synth failed: %s", e)
            return False
        if not (out_path.exists() and out_path.stat().st_size > 0):
            return False
        self._deepen(out_path)
        return out_path.exists() and out_path.stat().st_size > 0

    def _deepen(self, wav_path):
        """Pitch the voice down and slow it slightly (calm, serious tone) with
        ffmpeg's rubberband filter. No-op if ffmpeg is missing or no change asked."""
        if abs(self.pitch - 1.0) < 1e-3 and abs(self.tempo - 1.0) < 1e-3:
            return
        if shutil.which("ffmpeg") is None:
            return
        tmp = wav_path.with_suffix(".proc.wav")
        af = f"rubberband=pitch={self.pitch}:tempo={self.tempo}"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                 "-af", af, str(tmp)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=True, timeout=60,
            )
            if tmp.exists() and tmp.stat().st_size > 0:
                tmp.replace(wav_path)
        except (OSError, subprocess.SubprocessError):
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def prerender(self, text):
        """Render `text` to a cached wav and return its path (no playback).

        Returns the Path on success, or None if TTS is unavailable / failed.
        Safe to call ahead of time so playback later is instant.
        """
        text = (text or "").strip()
        if not text:
            return None
        out = self._cache_path(text)
        if out.exists() and out.stat().st_size > 0:
            return out  # already rendered
        if self._synthesize(text, out):
            return out
        # Clean up a half-written file so we retry next time.
        try:
            if out.exists():
                out.unlink()
        except OSError:
            pass
        return None

    def say(self, text, blocking=True):
        """Speak `text` out loud. No-op (logged) if TTS/audio is unavailable.

        If blocking is False, playback runs in the background and this returns
        immediately.
        """
        wav = self.prerender(text)
        if wav is None:
            log.info("TTS no-op (not available): %r", (text or "")[:60])
            return
        _play(wav, self.volume, blocking=blocking)


# --- audio player selection ---------------------------------------------------
# Pick whatever is installed at runtime. On the Pi this is pw-play, which sends
# audio straight to the PipeWire default sink (the Sony speaker once it is the
# Bluetooth default) with no ALSA-routing guesswork. aplay/paplay are kept as
# fallbacks; Windows/macOS/dev machines fall back to ffplay/afplay/winsound.

def _pick_player():
    """Return a tag for the best available wav player, or None."""
    for tool, tag in (("pw-play", "pw-play"), ("ffplay", "ffplay"),
                      ("aplay", "aplay"), ("paplay", "paplay"),
                      ("afplay", "afplay")):
        if shutil.which(tool):
            return tag
    if sys.platform.startswith("win"):
        try:
            import winsound  # noqa: F401  (stdlib on Windows)
            return "winsound"
        except Exception:
            pass
    return None


def _play(wav_path, volume=1.0, blocking=True):
    """Play a wav with the available player. Logs and returns on any failure."""
    player = _pick_player()
    if player is None:
        log.info("No audio player found; cannot play %s", wav_path)
        return

    wav = str(wav_path)
    try:
        if player == "winsound":
            import winsound
            flags = winsound.SND_FILENAME
            if not blocking:
                flags |= winsound.SND_ASYNC
            winsound.PlaySound(wav, flags)
            return

        if player == "pw-play":
            vol = max(0.0, min(1.0, volume))
            cmd = ["pw-play", f"--volume={vol}", wav]
        elif player == "aplay":
            cmd = ["aplay", "-q", wav]
        elif player == "paplay":
            vol = max(0, min(65536, int(volume * 65536)))
            cmd = ["paplay", f"--volume={vol}", wav]
        elif player == "ffplay":
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                   "-volume", str(max(0, min(100, int(volume * 100)))), wav]
        elif player == "afplay":
            cmd = ["afplay", wav]
        else:
            return

        if blocking:
            subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=120)
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("audio playback failed (%s): %s", player, e)


# --- audition CLI -------------------------------------------------------------
def _download(url, dest):
    """Download url to dest. Return True on success."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        log.info("downloading %s", url)
        with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as e:
        log.warning("download failed %s: %s", url, e)
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        return False


def _ensure_voice(name, hf_rel):
    """Make sure voice `name` exists in voices/. Download if missing. Return .onnx path or None."""
    onnx = _VOICES_DIR / f"{name}.onnx"
    conf = _VOICES_DIR / f"{name}.onnx.json"
    if onnx.exists() and conf.exists():
        return onnx
    ok_onnx = onnx.exists() or _download(_HF_BASE + hf_rel + ".onnx", onnx)
    ok_conf = conf.exists() or _download(_HF_BASE + hf_rel + ".onnx.json", conf)
    if ok_onnx and ok_conf:
        return onnx
    return None


def _audition():
    """Speak the same sample line through each candidate voice, in turn."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    piper_bin = _cfg("piper_bin", "BOTFIA_PIPER_BIN", None) or shutil.which("piper")
    if not piper_bin:
        print("piper binary not found. Install it first (see the top of this file).")
        print("Set BOTFIA_PIPER_BIN or put 'piper' on PATH, then rerun.")
        return 1
    if _pick_player() is None:
        print("No audio player found (aplay/paplay/ffplay/afplay/winsound).")
        return 1

    print(f'Audition line: "{_SAMPLE_LINE}"\n')
    for name, hf_rel in _AUDITION_VOICES:
        onnx = _ensure_voice(name, hf_rel)
        if onnx is None:
            print(f"  [skip] {name}: could not obtain voice files")
            continue
        print(f"  [play] {name}")
        tts = TTS(voice=str(onnx), piper_bin=piper_bin)
        tts.say(_SAMPLE_LINE, blocking=True)
    print("\nPick the calmest. Then set it, e.g.:")
    print("  export BOTFIA_PIPER_VOICE=pi/audio/voices/en_US-ryan-medium.onnx")
    return 0


if __name__ == "__main__":
    if "--audition" in sys.argv:
        raise SystemExit(_audition())
    # Default: speak the sample line through the configured voice.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    TTS().say(_SAMPLE_LINE, blocking=True)
