"""Mock hardware for the laptop simulation.

Each mock just prints what the real device would do, so a whole game is visible
in the console. The light sensor reports "dark" once the light is off, so the
night dark-confirm succeeds.
"""


class MockLight:
    def __init__(self):
        self.is_on = True

    def on(self):
        self.is_on = True
        print("[light] on")

    def off(self):
        self.is_on = False
        print("[light] off")

    def rest(self):
        pass

    def status(self):
        return {"state": "on" if self.is_on else "off", "simulated": True}

    def close(self):
        pass


class MockESP32:
    def __init__(self, light):
        self._light = light
        self.online = True

    def status(self):
        return {"name": "botfia-robot", "online": True,
                "dark": not self._light.is_on, "light_raw": 200 if self._light.is_on else 20}

    def light(self):
        return {"raw": 200 if self._light.is_on else 20, "dark": not self._light.is_on}

    def is_dark(self):
        return not self._light.is_on

    def face_on(self, fade_ms=700):
        print("[face] on")

    def face_off(self, fade_ms=700):
        print("[face] off")

    def eyes_on(self, fade_ms=700):
        print("[eyes] on")

    def eyes_off(self, fade_ms=700):
        print("[eyes] off")

    def smile_on(self, fade_ms=700):
        print("[smile] on")

    def smile_off(self, fade_ms=700):
        print("[smile] off")

    def calibrate(self, state):
        return {"state": state}


class MockSpeaker:
    def status(self):
        return {"available": False, "connected": False, "name": "laptop"}

    def connect(self):
        return False


class MockMusic:
    def play(self, mood):
        print(f"[music] {mood}")

    def duck(self):
        pass

    def unduck(self):
        pass

    def stop(self):
        print("[music] stop")

    def is_available(self):
        return True


class MockTTS:
    def say(self, text, blocking=True):
        print(f'[botfia] "{text}"')

    def prerender(self, text):
        return None

    def is_available(self):
        return True
