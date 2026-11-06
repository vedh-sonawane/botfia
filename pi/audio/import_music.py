"""Tag downloaded music by mood and (re)write music/tracks.json.

Put your downloaded instrumental tracks in music/ (see music/README.md), then:

    # from the repo root
    python -m pi.audio.import_music              # interactive: asks a mood per file
    python -m pi.audio.import_music --file calm_piano.ogg --mood calm
    python -m pi.audio.import_music --convert    # also normalize to .ogg (needs ffmpeg)

Moods are exactly: calm, uneasy, tense, final.

This merges with any existing tracks.json: it keeps entries whose files still
exist and adds/updates the ones you tag. A stable id is derived from the file
name, so re-running does not create duplicates.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MOODS = ("calm", "uneasy", "tense", "final")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MUSIC_DIR = _REPO_ROOT / "music"
_TRACKS_JSON = _MUSIC_DIR / "tracks.json"

_AUDIO_EXTS = {".ogg", ".mp3", ".wav", ".flac", ".m4a", ".aac"}


def _slug(name):
    """A stable id from a file stem: lowercase, words joined by hyphens."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "track"


def _audio_files():
    """Audio files sitting directly in music/ (not recursive)."""
    return sorted(
        p for p in _MUSIC_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in _AUDIO_EXTS
    )


def _load_existing():
    """Return {id: entry} from the current tracks.json, dropping missing files."""
    out = {}
    if not _TRACKS_JSON.exists():
        return out
    try:
        data = json.loads(_TRACKS_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    raw = data.get("tracks", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return out
    for t in raw:
        if not isinstance(t, dict):
            continue
        tid, tfile, mood = t.get("id"), t.get("file"), t.get("mood")
        if not (tid and tfile and mood in MOODS):
            continue
        # Keep only entries whose file still exists and is not a placeholder.
        p = Path(tfile)
        if not p.is_absolute():
            p = _MUSIC_DIR / p
        if p.exists():
            out[tid] = {"id": tid, "file": tfile, "mood": mood}
    return out


def _convert_to_ogg(path):
    """Convert a file to .ogg next to it using ffmpeg. Return the new path or original."""
    if shutil.which("ffmpeg") is None:
        print("  --convert: ffmpeg not found; leaving file as-is")
        return path
    if path.suffix.lower() == ".ogg":
        return path
    out = path.with_suffix(".ogg")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
           "-c:a", "libvorbis", "-q:a", "4", str(out)]
    try:
        subprocess.run(cmd, check=True, timeout=300)
        print(f"  converted -> {out.name}")
        return out
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  convert failed ({e}); keeping {path.name}")
        return path


def _write(entries):
    """Write tracks.json from a dict of {id: entry}, sorted by mood then id."""
    order = {m: i for i, m in enumerate(MOODS)}
    tracks = sorted(entries.values(), key=lambda t: (order.get(t["mood"], 9), t["id"]))
    payload = {
        "_comment": ("Generated/edited by pi/audio/import_music.py. Each entry: "
                     "id, file (relative to music/), mood (calm|uneasy|tense|final)."),
        "tracks": tracks,
    }
    _TRACKS_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(tracks)} track(s) to {_TRACKS_JSON}")


def _add(entries, path, mood, convert):
    """Add/update one file at `path` with `mood` into the entries dict."""
    if convert:
        path = _convert_to_ogg(path)
    rel = path.relative_to(_MUSIC_DIR) if path.is_relative_to(_MUSIC_DIR) else path
    tid = _slug(path.stem)
    entries[tid] = {"id": tid, "file": str(rel).replace("\\", "/"), "mood": mood}
    print(f"  tagged {path.name} -> {mood} (id={tid})")


def _ask_mood(fname):
    """Prompt the user for a mood for one file. Returns a mood or None to skip."""
    prompt = f'  mood for "{fname}" [calm/uneasy/tense/final, or s=skip]: '
    while True:
        try:
            ans = input(prompt).strip().lower()
        except EOFError:
            return None
        if ans in ("s", "skip", ""):
            return None
        if ans in MOODS:
            return ans
        # Accept unambiguous prefixes (c, u, t, f).
        matches = [m for m in MOODS if m.startswith(ans)]
        if len(matches) == 1:
            return matches[0]
        print("    please type one of: calm, uneasy, tense, final (or s to skip)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tag music by mood -> music/tracks.json")
    ap.add_argument("--file", help="tag just this file (relative to music/ or absolute)")
    ap.add_argument("--mood", choices=MOODS, help="mood for --file")
    ap.add_argument("--convert", action="store_true",
                    help="normalize tagged files to .ogg with ffmpeg (optional)")
    args = ap.parse_args(argv)

    if not _MUSIC_DIR.is_dir():
        print(f"music folder not found: {_MUSIC_DIR}")
        return 1

    entries = _load_existing()

    # Non-interactive: tag a single file.
    if args.file:
        if not args.mood:
            print("--file requires --mood")
            return 2
        p = Path(args.file)
        if not p.is_absolute():
            p = _MUSIC_DIR / p
        if not p.exists():
            print(f"file not found: {p}")
            return 2
        _add(entries, p, args.mood, args.convert)
        _write(entries)
        return 0

    # Interactive: walk every audio file in music/.
    files = _audio_files()
    if not files:
        print(f"No audio files in {_MUSIC_DIR}. Download some first (see README.md).")
        return 1

    print(f"Found {len(files)} audio file(s) in {_MUSIC_DIR}.")
    print("For each, choose a mood (calm, uneasy, tense, final) or skip.\n")
    for p in files:
        mood = _ask_mood(p.name)
        if mood is None:
            print(f"  skipped {p.name}")
            continue
        _add(entries, p, mood, args.convert)

    if not entries:
        print("\nNothing tagged; tracks.json left unchanged.")
        return 0
    _write(entries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
