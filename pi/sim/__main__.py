"""Laptop simulation.

  python -m pi.sim            serve the real web app with mock hardware on :8000
  python -m pi.sim --auto     play a whole game automatically and print it

No Pi, no ESP32, no speaker needed. The game is identical to the real thing; only
the light/eyes/voice are mocked (printed to the console).
"""

import sys
import time

from ..narration.claude import Narrator
from ..session import BotfiaSession
from .mocks import MockLight, MockESP32, MockSpeaker, MockMusic, MockTTS


def make_session(fast=False):
    light = MockLight()
    esp32 = MockESP32(light)
    session = BotfiaSession(
        light=light, esp32=esp32, speaker=MockSpeaker(),
        music=MockMusic(), tts=MockTTS(), narrator=Narrator(),
    )
    if fast:
        session.engine.min_turn_seconds = 0.0
    return session


def auto_play(names):
    """Drive a full game by reading device_state and acting, like a player would."""
    session = make_session(fast=True)
    session.configure(names, {"voting_style": "secret", "min_turn_seconds": 0})
    session.engine.min_turn_seconds = 0.0
    session.start()

    steps = 0
    while steps < 2000:
        steps += 1
        st = session.public_state()
        if st["phase"] == "end":
            break
        ds = session.device_state()
        screen = ds.get("screen")
        if screen == "handoff":
            session.begin_turn()
        elif screen == "reveal":
            session.finish_turn()
        elif screen == "ready_night":
            session.begin_night()
        elif screen == "night":
            opts = ds.get("options", [])
            if opts:
                session.submit_night(opts[0]["seat"])
            session.finish_turn()
        elif screen == "morning":
            session.morning_continue()
        elif screen == "day":
            if ds.get("stage") == "post_vote":
                session.day_continue()
            else:
                session.start_vote()
        elif screen == "vote":
            opts = ds.get("options", [])
            session.submit_vote(opts[0]["seat"] if opts else None)
            session.finish_turn()
        elif screen == "vote_open":
            opts = ds.get("options", [])
            session.set_open_vote(opts[0]["seat"] if opts else None)
        else:
            break

    time.sleep(0.2)  # let the speech queue flush
    final = session.public_state()
    print("\n=== transcript ===")
    for line in final["log"]:
        print(" ", line)
    print(f"\nwinner: {final['winner']}  (in {steps} steps)")
    print("roles:")
    for p in final.get("reveal", []):
        print(f"  seat {p['seat']}  {p['name']}: {p['role']}")
    return final


def serve():
    from ..app import build_app
    session = make_session(fast=False)
    app = build_app(session)
    print("Botfia simulation on http://localhost:8000")
    app.run(host="0.0.0.0", port=8000, threaded=True)


if __name__ == "__main__":
    if "--auto" in sys.argv:
        names = ["Ava", "Ben", "Cora", "Dan", "Eli", "Fay", "Gus"]
        result = auto_play(names)
        sys.exit(0 if result["winner"] in ("town", "mafia") else 1)
    else:
        serve()
