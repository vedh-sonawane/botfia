"""Central Botfia configuration.

Defaults live here; a saved overlay (botfia_config.json) and a few env vars can
override them. Secrets (the Anthropic API key, Wi-Fi) are NOT here — they live in
.env and the Wi-Fi secrets file and are never committed.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).with_name("botfia_config.json")

DEFAULTS = {
    # Narration
    "narration_model": "claude-sonnet-4-6",   # current Sonnet; sonnet-5-5 is not real
    "max_tokens": 110,   # a tight 2-sentence (~40 word) narrated scene

    # Game pacing / rules (editable in setup)
    "min_turn_seconds": 4.0,        # equal turn-time floor so roles can't be timed
    "discussion_seconds": 180,
    "voting_style": "secret",        # "secret" | "open"
    "reveal_roles_on_death": True,
    "doctor_no_repeat": True,        # doctor can't protect the same person twice in a row
    "revote_on_tie": True,

    # Audio
    "music_volume": 0.5,
    "narration_volume": 1.0,
    "piper_voice": "en_US-ryan-medium",

    # Hardware
    "esp32_host": "botfia-robot.local",
    "fade_ms": 700,
    "dark_retries": 2,
}


class _Config(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(key) from e

    def __setattr__(self, key, value):
        self[key] = value


def load():
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text()))
        except Exception:
            pass
    if os.getenv("BOTFIA_MODEL"):
        cfg["narration_model"] = os.getenv("BOTFIA_MODEL")
    if os.getenv("BOTFIA_PIPER_VOICE"):
        cfg["piper_voice"] = os.getenv("BOTFIA_PIPER_VOICE")
    return _Config(cfg)


CONFIG = load()


def save(cfg):
    CONFIG_PATH.write_text(json.dumps(dict(cfg), indent=2))
