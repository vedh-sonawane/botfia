"""Tests for the game engine.

The most important one, per the project rules: public state must NEVER leak
secrets (roles, the mafia's target, the doctor's save, detective results) while
the game is in progress. Run with:  python -m pytest pi/tests/  (or just run
this file directly:  python pi/tests/test_game.py)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.engine import GameEngine, Phase


def _new_game(n=6):
    g = GameEngine()
    for seat in range(1, n + 1):
        g.add_player(f"P{seat}", seat)
    g.start_game()
    return g


def _seats_by_role(g, role):
    return [p for p in g.players.values() if p.role == role]


def test_roles_assigned_correctly():
    g = _new_game(6)
    counts = {}
    for p in g.players.values():
        counts[p.role] = counts.get(p.role, 0) + 1
    assert counts == {"mafia": 1, "doctor": 1, "detective": 1, "villager": 3}


def test_public_state_never_leaks_roles_during_play():
    g = _new_game(8)
    blob = json.dumps(g.public_state())
    for role in ("mafia", "doctor", "detective", "villager"):
        assert role not in blob, f"public_state leaked role '{role}'"

    # Through a full night, still no leaks.
    g.begin_night()
    mafia = _seats_by_role(g, "mafia")[0]
    doctor = _seats_by_role(g, "doctor")[0]
    detective = _seats_by_role(g, "detective")[0]
    victim = next(p for p in g.players.values() if p.role != "mafia")
    for p in g.players.values():
        if p.role == "mafia":
            g.submit_night_action(p.id, victim.id)
        elif p.role == "doctor":
            g.submit_night_action(p.id, p.id)        # save self
        elif p.role == "detective":
            g.submit_night_action(p.id, mafia.id)    # check the mafia
        else:
            g.submit_night_action(p.id, None)        # villager neutral tap
    g.resolve_night()

    blob = json.dumps(g.public_state())
    for role in ("mafia", "doctor", "detective", "villager"):
        assert role not in blob, f"public_state leaked role '{role}' after night"
    # The victim's name may appear (public), but nothing about who did what.
    assert "is_mafia" not in blob
    assert "detective_result" not in blob


def test_detective_result_is_private():
    g = _new_game(6)
    g.begin_night()
    detective = _seats_by_role(g, "detective")[0]
    mafia = _seats_by_role(g, "mafia")[0]
    for p in g.players.values():
        g.submit_night_action(p.id, mafia.id if p.role == "detective" else None)

    # The detective sees their result...
    dv = g.player_view(detective.id)
    assert dv["detective_result"]["is_mafia"] is True

    # ...but no other player's view contains a detective result.
    for p in g.players.values():
        if p.id != detective.id:
            assert "detective_result" not in g.player_view(p.id)


def test_doctor_save_prevents_death():
    g = _new_game(6)
    g.begin_night()
    mafia = _seats_by_role(g, "mafia")[0]
    doctor = _seats_by_role(g, "doctor")[0]
    target = next(p for p in g.players.values() if p.role == "villager")
    for p in g.players.values():
        if p.role == "mafia":
            g.submit_night_action(p.id, target.id)
        elif p.role == "doctor":
            g.submit_night_action(p.id, target.id)   # save the target
        else:
            g.submit_night_action(p.id, None)
    result = g.resolve_night()
    assert result is None
    assert target.alive is True


def test_mafia_kill_without_save():
    g = _new_game(6)
    g.begin_night()
    mafia = _seats_by_role(g, "mafia")[0]
    target = next(p for p in g.players.values() if p.role == "villager")
    for p in g.players.values():
        if p.role == "mafia":
            g.submit_night_action(p.id, target.id)
        elif p.role == "doctor":
            g.submit_night_action(p.id, p.id)        # save self, not the target
        else:
            g.submit_night_action(p.id, None)
    result = g.resolve_night()
    assert result == {"seat": target.seat, "name": target.name}
    assert target.alive is False


def test_town_wins_when_mafia_voted_out():
    g = _new_game(4)   # 1 mafia, 1 doctor, 1 detective, 1 villager
    mafia = _seats_by_role(g, "mafia")[0]
    g.begin_vote()
    for p in g.players.values():
        g.submit_vote(p.id, mafia.id)
    g.resolve_vote()
    assert g.winner == "town"
    assert g.phase == Phase.END
    # Roles are revealed only now.
    assert "reveal" in g.public_state()


def _run(label, fn):
    try:
        fn()
        print(f"PASS  {label}")
        return True
    except AssertionError as e:
        print(f"FAIL  {label}: {e}")
        return False


if __name__ == "__main__":
    tests = [
        ("roles assigned correctly", test_roles_assigned_correctly),
        ("public state never leaks roles", test_public_state_never_leaks_roles_during_play),
        ("detective result is private", test_detective_result_is_private),
        ("doctor save prevents death", test_doctor_save_prevents_death),
        ("mafia kill without save", test_mafia_kill_without_save),
        ("town wins when mafia voted out", test_town_wins_when_mafia_voted_out),
    ]
    ok = sum(_run(l, f) for l, f in tests)
    print(f"\n{ok}/{len(tests)} passed")
    sys.exit(0 if ok == len(tests) else 1)
