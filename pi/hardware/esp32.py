"""HTTP client for the ESP32 table unit (eyes, smile, photoresistor).

Every call has a short timeout and fails quietly, if the board is offline the
game continues without the eyes. Uses the stdlib only (no extra dependency).
Endpoints match the "Pi <-> ESP32 HTTP contract" in CLAUDE.md.
"""

import json
import urllib.request


class ESP32:
    def __init__(self, host="botfia-robot.local", timeout=2.0):
        self.host = host
        self.timeout = timeout
        self.online = False

    def _url(self, path):
        return f"http://{self.host}{path}"

    def _request(self, path, method="GET", body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self._url(path), data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                self.online = True
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except Exception:
            self.online = False
            return None

    # ---- reads ----
    def status(self):
        return self._request("/status")

    def light(self):
        return self._request("/light")

    def is_dark(self):
        info = self.light()
        return bool(info.get("dark")) if info else None

    # ---- face ----
    def face_on(self, fade_ms=700):
        return self._request("/face/on", "POST", {"fade_ms": fade_ms})

    def face_off(self, fade_ms=700):
        return self._request("/face/off", "POST", {"fade_ms": fade_ms})

    def eyes_on(self, fade_ms=700):
        return self._request("/eyes/on", "POST", {"fade_ms": fade_ms})

    def eyes_off(self, fade_ms=700):
        return self._request("/eyes/off", "POST", {"fade_ms": fade_ms})

    def smile_on(self, fade_ms=700):
        return self._request("/smile/on", "POST", {"fade_ms": fade_ms})

    def smile_off(self, fade_ms=700):
        return self._request("/smile/off", "POST", {"fade_ms": fade_ms})

    # ---- calibration ----
    def calibrate(self, state):
        """state is "light" or "dark", store the current room reading."""
        return self._request("/calibrate", "POST", {"state": state})
