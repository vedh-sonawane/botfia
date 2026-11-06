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
        return {"available": True, "connected": connected, "name": name}

    def connect(self):
        if not self._have_bt or not self.mac:
            return False
        try:
            subprocess.run(["bluetoothctl", "connect", self.mac],
                           capture_output=True, text=True, timeout=10)
        except Exception:
            return False
        return self.status().get("connected", False)
