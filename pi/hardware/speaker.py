"""Bluetooth speaker status/connect for the host health screen.

Pairing is a one-time manual step (see docs/SPEAKER.md). This module just reports
whether a speaker is connected and can nudge a reconnect. On a non-Linux laptop
it reports "not available" and the game plays audio through the laptop instead.
"""

import shutil
import subprocess


class Speaker:
    def __init__(self, mac=None):
        self.mac = mac
        self._have_bt = shutil.which("bluetoothctl") is not None

    def available(self):
        return self._have_bt

    def status(self):
        if not self._have_bt:
            return {"available": False, "connected": False, "name": None}
        try:
            out = subprocess.run(
                ["bluetoothctl", "info"] + ([self.mac] if self.mac else []),
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            return {"available": True, "connected": False, "name": None}
        connected = "Connected: yes" in out
        name = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Name:"):
                name = line.split("Name:", 1)[1].strip()
                break
        return {"available": True, "connected": connected, "name": name,
                "volume": self.get_volume()}

    # --- speaker output volume (the real sink level; affects everything) ------
    _SINK = "@DEFAULT_AUDIO_SINK@"

    def get_volume(self):
        """Return the speaker output volume 0.0-1.0 (via PipeWire), or None."""
        if shutil.which("wpctl") is None:
            return None
        try:
            out = subprocess.run(["wpctl", "get-volume", self._SINK],
                                  capture_output=True, text=True, timeout=5).stdout
        except Exception:
            return None
        for tok in out.replace("Volume:", " ").split():   # "Volume: 0.60 [MUTED]"
            try:
                return max(0.0, min(1.0, float(tok)))
            except ValueError:
                continue
        return None

    def set_volume(self, v):
        """Set the speaker output volume 0.0-1.0 (affects narration + music)."""
        if shutil.which("wpctl") is None:
            return False
        try:
            v = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return False
        try:
            subprocess.run(["wpctl", "set-volume", self._SINK, f"{v:.2f}"],
                           capture_output=True, text=True, timeout=5)
            return True
        except Exception:
            return False

    def connect(self):
        if not self._have_bt or not self.mac:
            return False
        try:
            subprocess.run(["bluetoothctl", "connect", self.mac],
                           capture_output=True, text=True, timeout=10)
        except Exception:
            return False
        return self.status().get("connected", False)
