"""Tests for the pass-and-play engine.

The ones that matter most, per the project rules:
  - public state never exposes roles while the game is in progress;
  - the narration layer is never handed a secret;
  - the shared device, during a private turn, shows ONLY the current player's
    own info (hand-off privacy);
  - every turn enforces the minimum turn time (so roles can't be read by timing).

Run:  python pi/tests/test_game.py   (or: python -m pytest pi/tests/)
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pi.game.engine import GameEngine
from pi.narration import prompts

NAMES = ["Ava", "Ben", "Cora", "Dan", "Eli", "Fay", "Gus"]
ROLE_WORDS = ("mafia", "doctor", "detective", "villager")


def new_game(n=7, narrate=None, min_turn=0.0):
    g = GameEngine(narrate=narrate, min_turn_seconds=min_turn)
    g.configure(NAMES[:n], {"voting_style": "secret"})
    g.start()
    return g


def drive(engine, on_state=None, pick=0, max_steps=3000):
    steps = 0
    while engine.phase != "end" and steps < max_steps:
        steps += 1
        if on_state:
            on_state(engine)
        ds = engine.device_state()
        screen = ds.get("screen")
        if screen == "handoff":
            engine.begin_turn()
        elif screen == "reveal":
            engine.finish_turn()
        elif screen == "ready_night":
            engine.begin_night()
        elif screen == "night":
            opts = ds.get("options", [])
            if opts:
                engine.submit_night(opts[pick % len(opts)]["seat"])
            engine.finish_turn()
        elif screen == "morning":
            engine.morning_continue()
        elif screen == "day":
            if ds.get("stage") == "post_vote":
                engine.day_continue()
            else:
                engine.start_vote()
        elif screen == "vote":
            opts = ds.get("options", [])
            engine.submit_vote(opts[pick % len(opts)]["seat"] if opts else None)
            engine.finish_turn()
        elif screen == "vote_open":
            opts = ds.get("options", [])
            engine.set_open_vote(opts[0]["seat"] if opts else None)
        else:
            break
    return steps


# ------------------------------------------------------------------ tests
def test_roles_assigned():
    g = new_game(7)
    counts = {}
    for p in g.players:
        counts[p.role] = counts.get(p.role, 0) + 1
    assert counts == {"mafia": 2, "doctor": 1, "detective": 1, "villager": 3}, counts


def test_public_players_never_have_roles():
    g = new_game(7)

    def check(engine):
        for p in engine.public_state()["players"]:
            assert set(p.keys()) == {"seat", "name", "alive"}, p
        if engine.phase != "end":
            assert "reveal" not in engine.public_state()

    drive(g, on_state=check)
    assert g.winner in ("town", "mafia")
    # Only at the end is the reveal (roles) present.
    assert "reveal" in g.public_state()


def test_narration_only_ever_public():
    # A spy narrator that refuses any non-public context exactly like the real
    # prompt builder. If the engine ever passed a secret, this raises.
    seen = []

    def spy(event, ctx):
        prompts.assert_public(event, ctx)   # raises on any non-allowlisted key
        seen.append((event, dict(ctx or {})))
        return "ok"

    g = new_game(7, narrate=spy)
    drive(g)
    assert g.winner in ("town", "mafia")
    # No call ever carried a role except the public reveal_role at elimination/end.
    for event, ctx in seen:
        if "role" in ctx:
            assert event == "reveal_role", (event, ctx)


def test_handoff_hides_everything():
    g = new_game(7)
    # At the first reveal hand-off, the device shows no role or action.
    ds = g.device_state()
    assert ds["screen"] == "handoff"
    blob = json.dumps(ds)
    for w in ROLE_WORDS:
        assert w not in blob.lower(), ds
    assert "role" not in ds and "kind" not in ds and "options" not in ds


def test_device_shows_only_current_actor():
    g = new_game(7)
    # Walk to a night action screen and confirm it exposes only this player.
    def check(engine):
        ds = engine.device_state()
        if ds.get("screen") == "night":
            # options are names only — no roles leak about other players
            for o in ds.get("options", []):
                assert set(o.keys()) == {"seat", "name"}, o
            # the only role-ish field is this player's own action kind
            assert "teammates" not in ds or engine._current().role == "mafia"
    drive(g, on_state=check)


def test_equal_turn_timing_enforced():
    g = new_game(7, min_turn=0.25)
    # advance to the first active reveal turn
    assert g.device_state()["screen"] == "handoff"
    g.begin_turn()
    assert g.device_state()["screen"] == "reveal"
    # too soon -> rejected
    assert g.finish_turn() is False
    time.sleep(0.3)
    # now allowed
    assert g.finish_turn() is True


def test_doctor_save_prevents_death():
    g = new_game(6)
    g.phase = "reveal"
    # fast-forward reveal
    g.min_turn_seconds = 0.0
    while g.phase == "reveal":
        if g.device_state()["screen"] == "handoff":
            g.begin_turn()
        else:
            g.finish_turn()
    g.begin_night()
    mafia = next(p for p in g.players if p.role == "mafia")
    doctor = next(p for p in g.players if p.role == "doctor")
    victim = next(p for p in g.players if p.role == "villager")
    # drive night turns, forcing mafia->victim and doctor->victim
    while g.phase == "night":
        ds = g.device_state()
        if ds["screen"] == "handoff":
            g.begin_turn()
            continue
        cur = g._current()
        if cur.role == "mafia":
            g.submit_night(victim.seat)
        elif cur.role == "doctor":
            g.submit_night(victim.seat)
        g.finish_turn()
    assert victim.alive is True
    assert (g._last_morning or {}).get("died") is None


def test_mafia_win_when_numbers_reached():
    g = new_game(4)  # 1 mafia, 1 doctor, 1 detective, 1 villager
    # Kill until mafia >= others by driving the game; just assert it terminates
    # with a valid winner and the end screen reveals roles.
    drive(g)
    assert g.phase == "end"
    assert g.winner in ("town", "mafia")
    assert len(g.public_state()["reveal"]) == 4


def _run(label, fn):
    try:
        fn()
        print(f"PASS  {label}")
        return True
    except AssertionError as e:
        print(f"FAIL  {label}: {e}")
        return False
    except Exception as e:
        print(f"ERROR {label}: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    tests = [
        ("roles assigned", test_roles_assigned),
        ("public players never have roles", test_public_players_never_have_roles),
        ("narration only ever public", test_narration_only_ever_public),
        ("hand-off hides everything", test_handoff_hides_everything),
        ("device shows only current actor", test_device_shows_only_current_actor),
        ("equal turn timing enforced", test_equal_turn_timing_enforced),
        ("doctor save prevents death", test_doctor_save_prevents_death),
        ("mafia win terminates + reveals", test_mafia_win_when_numbers_reached),
    ]
    ok = sum(_run(l, f) for l, f in tests)
    print(f"\n{ok}/{len(tests)} passed")
    sys.exit(0 if ok == len(tests) else 1)
