"""Background music for Botfia: pick by mood, crossfade, duck under narration.

Quiet instrumental tracks live in music/ and are listed in music/tracks.json
(id, file, mood). Claude picks a mood for the moment; the code checks the id/file
exists before playing. Moods are exactly: calm, uneasy, tense, final.

Player choice: ffplay (from ffmpeg), driven over subprocess, one track at a time.
Why not pygame.mixer? ffplay is already needed for other audio, needs no Python
package, and keeps memory low on a 1GB Pi (we do not load whole tracks into RAM).
The trade-off: ffplay has no live volume knob once playing, so "crossfade" and
"ducking" are done by stopping the old process and starting a new one at the new
volume. For quiet background music this is smooth enough and dead simple.

Everything degrades gracefully. No tracks.json, no files, or no ffplay -> every
method logs once and does nothing. The game never blocks on music.

Dependency: ffmpeg (provides ffplay). Install on the Pi with:  sudo apt install ffmpeg
No pip package is required.
"""

from __future__ import annotations

import json
import logging
import random
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("botfia.music")

# --- Config (defensive), same pattern as tts.py ------------------------------
try:
    from ..config import CONFIG  # type: ignore
except Exception:  # pragma: no cover
    CONFIG = {}

MOODS = ("calm", "uneasy", "tense", "final")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MUSIC_DIR = _REPO_ROOT / "music"
_TRACKS_JSON = _MUSIC_DIR / "tracks.json"


def _cfg_float(key, default):
    try:
        if isinstance(CONFIG, dict) and CONFIG.get(key) is not None:
            return float(CONFIG[key])
    except Exception:
        pass
    return default


class Music:
    """Background music controller. One track plays at a time via ffplay."""

    def __init__(self, music_dir=None, tracks_json=None):
        self._dir = Path(music_dir) if music_dir else _MUSIC_DIR
        self._tracks_path = Path(tracks_json) if tracks_json else _TRACKS_JSON
        # Base volume (normal) and ducked volume (while narration speaks), 0-1.
        self._base_volume = _cfg_float("music_volume", 0.35)
        self._duck_volume = _cfg_float("music_duck_volume", 0.12)
        self._ducked = False
        self._proc = None            # the live ffplay process, if any
        self._current_file = None    # Path of the track currently playing
        self._tracks = self._load_tracks()

    # --- tracks.json ----------------------------------------------------------
    def _load_tracks(self):
        """Return a list of valid track dicts {id, file, mood}. [] if missing/bad."""
        if not self._tracks_path.exists():
            log.info("music: no tracks.json at %s; music disabled", self._tracks_path)
            return []
        try:
            data = json.loads(self._tracks_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("music: could not read tracks.json: %s", e)
            return []
        raw = data.get("tracks", data) if isinstance(data, dict) else data
        tracks = []
        if isinstance(raw, list):
            for t in raw:
                if not isinstance(t, dict):
                    continue
                tid, tfile, mood = t.get("id"), t.get("file"), t.get("mood")
                if not (tid and tfile and mood in MOODS):
                    continue
                tracks.append({"id": tid, "file": tfile, "mood": mood})
        if not tracks:
            log.info("music: tracks.json has no usable entries; music disabled")
        return tracks

    def _resolve(self, track):
        """Return the absolute Path of a track's file if it exists, else None."""
        p = Path(track["file"])
        if not p.is_absolute():
            p = self._dir / p
        return p if p.exists() else None

    # --- availability ---------------------------------------------------------
    def is_available(self):
        """True if ffplay exists and at least one track file is present."""
        if shutil.which("ffplay") is None:
            return False
        return any(self._resolve(t) for t in self._tracks)

    # --- playback -------------------------------------------------------------
    def _volume(self):
        return self._duck_volume if self._ducked else self._base_volume

    def _spawn(self, file_path, volume):
        """Start an ffplay process looping `file_path` quietly. Return proc or None."""
        if shutil.which("ffplay") is None:
            log.info("music: ffplay not found; cannot play")
            return None
        vol = max(0, min(100, int(volume * 100)))
        cmd = [
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
            "-loop", "0",                      # loop the track until stopped
            "-volume", str(vol),
            str(file_path),
        ]
        try:
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("music: ffplay failed to start: %s", e)
            return None

    def _kill(self):
        """Stop the current ffplay process, if any."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            except Exception:
                pass
        self._proc = None

    def play(self, mood):
        """Crossfade to a random track whose mood matches. No-op if none usable.

        'Crossfade' here is a quick swap: we start the new track at the current
        volume and stop the old one. For quiet background loops this reads as a
        smooth change, and it keeps memory and code minimal.
        """
        if mood not in MOODS:
            log.warning("music: unknown mood %r; ignoring", mood)
            return
        candidates = [t for t in self._tracks if t["mood"] == mood and self._resolve(t)]
        if not candidates:
            log.info("music: no playable track for mood %r; staying silent", mood)
            return
        choice = random.choice(candidates)
        path = self._resolve(choice)

        new_proc = self._spawn(path, self._volume())
        if new_proc is None:
            return
        self._kill()                 # stop the old track after the new one starts
        self._proc = new_proc
        self._current_file = path
        log.info("music: playing %s (mood=%s)", choice["id"], mood)

    def duck(self):
        """Lower music volume while narration speaks."""
        if self._ducked:
            return
        self._ducked = True
        self._restart_at_current_volume()

    def unduck(self):
        """Raise music back to its base volume after narration."""
        if not self._ducked:
            return
        self._ducked = False
        self._restart_at_current_volume()

    def _restart_at_current_volume(self):
        """Re-spawn the current track at the current volume (ffplay has no live knob)."""
        if self._proc is None or self._current_file is None:
            return
        new_proc = self._spawn(self._current_file, self._volume())
        if new_proc is None:
            return
        self._kill()
        self._proc = new_proc

    def stop(self):
        """Stop music entirely."""
        self._kill()
        self._current_file = None
