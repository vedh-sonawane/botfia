"""BotfiaSession — ties the pure game engine to the real world.

The engine decides everything; this layer makes the lights, eyes, voice, and
music follow along, always in background threads so the web app never blocks and
the game never stalls. Hardware is injected so the laptop simulation can pass
mocks.
"""

import queue
import threading
import time

from .config import CONFIG
from .game.engine import GameEngine
from .narration.claude import Narrator


class BotfiaSession:
    def __init__(self, light, esp32, speaker, music, tts, narrator=None, config=None):
        self.config = config or CONFIG
        self.light = light
        self.esp32 = esp32
        self.speaker = speaker
        self.music = music
        self.tts = tts
        self.narrator = narrator or Narrator(
            model=self.config.narration_model, max_tokens=self.config.max_tokens
        )
        self.fade_ms = int(self.config.fade_ms)

        self._new_engine()

        # one worker speaks lines in order, ducking the music under each
        self._speak_q = queue.Queue()
        threading.Thread(target=self._speak_worker, daemon=True).start()

        # cached health, refreshed in the background (ESP32 polls can be slow)
        self._health = {}
        threading.Thread(target=self._health_worker, daemon=True).start()

    def _new_engine(self):
        self.engine = GameEngine(
            narrate=self.narrator.narrate,
            min_turn_seconds=float(self.config.min_turn_seconds),
        )
        self._spoken = 0

    # ------------------------------------------------------------- views
    def public_state(self):
        s = self.engine.public_state()
        s["health"] = dict(self._health)
        return s

    def device_state(self):
        return self.engine.device_state()

    # ------------------------------------------------------- game actions
    def configure(self, names, options):
        self.engine.configure(names, options)

    def start(self):
        self.engine.start()
        self.music.play("calm")
        self._after()

    def begin_turn(self):
        self.engine.begin_turn()

    def finish_turn(self):
        before = self.engine.phase
        ok = self.engine.finish_turn()
        if ok and before == "night" and self.engine.phase == "morning":
            self._morning_hw()
        self._after()
        return ok

    def submit_night(self, target):
        self.engine.submit_night(target)

    def submit_vote(self, target):
        self.engine.submit_vote(target)

    def begin_night(self):
        self.engine.begin_night()
        self._night_hw()
        self._pregen_morning()
        self._after()

    def morning_continue(self):
        self.engine.morning_continue()
        self._after()

    def start_vote(self):
        self.engine.start_vote()
        self.music.play("tense")
        self._pregen_votes()
        self._after()

    def set_open_vote(self, target):
        self.engine.set_open_vote(target)
        self._after()

    def day_continue(self):
        self.engine.day_continue()
        if self.engine.phase == "night":
            self._night_hw()
            self._pregen_morning()
        self._after()

    def restart(self):
        self._new_engine()
        try:
            self.light.on()
            self.esp32.face_off(self.fade_ms)
            self.music.stop()
        except Exception:
            pass

    def end_game(self):
        """Host force-ends the current game and returns to a safe state."""
        self.engine.end_now()
        try:
            self.light.on()
            self.esp32.face_off(self.fade_ms)
            self.music.stop()
        except Exception:
            pass
        self._after()

    def repeat_last(self):
        """Re-speak the most recent narration line."""
        log = self.engine.public_log
        if log and log[-1]:
            self._speak_q.put(log[-1])

    # ------------------------------------------------------- pre-generation
    def _pregen_morning(self):
        self.narrator.pregenerate("morning_safe")
        for p in self.engine.players:
            if p.alive:
                self.narrator.pregenerate("morning_death", {"name": p.name})

    def _pregen_votes(self):
        self.narrator.pregenerate("vote_tie")
        self.narrator.pregenerate("vote_none")
        for p in self.engine.players:
            if p.alive:
                self.narrator.pregenerate("vote_out", {"name": p.name})

    # ------------------------------------------------------- speaking
    def _after(self):
        new = self.engine.public_log[self._spoken:]
        self._spoken = len(self.engine.public_log)
        for line in new:
            if line:
                self._speak_q.put(line)

    def _speak_worker(self):
        while True:
            line = self._speak_q.get()
            try:
                self.music.duck()
                self.tts.say(line, blocking=True)
            except Exception:
                pass
            finally:
                try:
                    self.music.unduck()
                except Exception:
                    pass

    # ------------------------------------------------------- hardware flows
    def _night_hw(self):
        def run():
            try:
                self.music.play("uneasy")
                self.light.off()
                self._confirm_dark()
                self.esp32.face_on(self.fade_ms)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def _morning_hw(self):
        def run():
            try:
                self.light.on()
                self.esp32.face_off(self.fade_ms)
                self.music.play("calm")
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def _confirm_dark(self):
        """Confirm the room went dark; retry the flip up to dark_retries. Returns
        True/False, or None if the ESP32 is offline (game continues either way)."""
        retries = int(self.config.dark_retries)
        for attempt in range(retries + 1):
            time.sleep(0.4)
            d = self.esp32.is_dark()
            if d is None:
                return None          # ESP32 offline — continue without the check
            if d is True:
                return True
            if attempt < retries:
                self.light.off()     # still bright — flip again
        return False

    # ------------------------------------------------------- health
    def _health_worker(self):
        while True:
            try:
                esp = self.esp32.status()
                self._health = {
                    "esp32": {
                        "online": esp is not None,
                        "dark": (esp or {}).get("dark"),
                        "light_raw": (esp or {}).get("light_raw"),
                    },
                    "speaker": self.speaker.status(),
                    "claude": {"enabled": self.narrator.enabled},
                    "tts": {"available": self.tts.is_available()},
                    "music": self.music.status(),
                    "light": self.light.status(),
                }
            except Exception:
                pass
            time.sleep(3.0)
