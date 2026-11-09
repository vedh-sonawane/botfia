"""Botfia game engine, pass-and-play Mafia on one shared device.

This is PLAIN CODE. It decides every outcome. Claude is never involved here; the
only thing the engine asks an outside narrator for is a public line of text, and
it only ever hands that narrator PUBLIC information.

Two views:
  - public_state(): safe for the host screen and general UI. NEVER contains roles
    or secret actions while the game is in progress.
  - device_state(): the one screen the shared device should show right now. During
    a private turn it contains ONLY the current player's own role/action, never
    anyone else's. Physical privacy (press-and-hold, hand-off) is enforced by the
    client; the engine makes sure the data for a turn belongs to that turn only.

Phases: setup -> reveal -> night -> morning -> day -> vote -> (loop) -> end
Private turns (reveal, night, secret vote) go around the circle with a hand-off
between each player and a minimum turn time so roles can't be read from timing.
"""

import json
import random
import time
from collections import Counter
from pathlib import Path

ROLES_PATH = Path(__file__).with_name("roles.json")

PHASES = ("setup", "reveal", "night", "morning", "day", "vote", "end")

ROLE_BLURB = {
    "mafia": "Each night, choose someone to remove.",
    "doctor": "Each night, choose someone to protect.",
    "detective": "Each night, check one person. You learn if they are mafia.",
    "villager": "No night action. Find the mafia by day.",
    "jester": "No night action. Get the town to vote you out. If they do, you win.",
}


def load_role_table():
    data = json.loads(ROLES_PATH.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


class Player:
    def __init__(self, seat, name):
        self.seat = seat
        self.name = name
        self.role = None
        self.alive = True


def _default_narrate(event, ctx):
    # Fallback narrator so the engine works standalone (tests, sim). Replaced by
    # the app with the Claude-backed narrator. Always offline and secret-free.
    from ..narration import fallback
    return fallback.line(event, ctx)


class GameEngine:
    def __init__(self, narrate=None, min_turn_seconds=4.0, role_table=None):
        self.narrate = narrate or _default_narrate
        self.min_turn_seconds = float(min_turn_seconds)
        self.role_table = role_table or load_role_table()

        self.players = []          # ordered by seat (circle order)
        self.phase = "setup"
        self.day_number = 0
        self.winner = None
        self.public_log = []       # list of public narration lines (no secrets)
        self.history = []          # per-night summary for the end screen (public once ended)

        # pass-and-play cursor (reveal / night / secret vote)
        self._order = []           # seats, in turn order for the current round
        self._cursor = 0
        self._stage = None         # None | "handoff" | "active"
        self._turn_start = 0.0
        self._seen_reveal = set()

        # secret per-round working state
        self._mafia_pick = None        # seat
        self._doctor_protect = None    # seat
        self._last_protected = None    # seat, for the no-repeat rule
        self._detective_results = {}   # detective seat -> {"seat","name","is_mafia"}
        self._votes = {}               # voter seat -> target seat or None
        self._revote_used = False

        # hub bookkeeping
        self._last_morning = None      # public: {"died": name|None}
        self._last_vote = None         # public: {"out": name|None, "tie": bool}
        self._day_stage = "discussion"  # "discussion" -> vote; "post_vote" -> next night
        self._doctor_no_repeat = True
        self._reveal_roles_on_death = True
        self._voting_style = "secret"
        self._revote_on_tie = True
        self._discussion_seconds = 180
        self._include_jester = False   # optional role: wins if voted out by day

    # ---------------------------------------------------------------- setup
    def configure(self, names, options=None):
        if self.phase != "setup":
            raise ValueError("game already started")
        names = [str(n).strip()[:20] or f"Player {i+1}" for i, n in enumerate(names)]
        if len(names) < 4:
            raise ValueError("need at least 4 players")
        if len(names) > 30:
            raise ValueError("max 30 players")
        self.players = [Player(i, n) for i, n in enumerate(names)]
        opts = options or {}
        self._doctor_no_repeat = bool(opts.get("doctor_no_repeat", True))
        self._reveal_roles_on_death = bool(opts.get("reveal_roles_on_death", True))
        self._voting_style = opts.get("voting_style", "secret")
        self._revote_on_tie = bool(opts.get("revote_on_tie", True))
        self._discussion_seconds = int(opts.get("discussion_seconds", 180))
        self._include_jester = bool(opts.get("include_jester", False))

    def _role_counts(self, n):
        """Roles for any player count: always exactly ONE mafia, one doctor, and
        one detective. Everyone else is a villager, so more players just means
        more villagers."""
        return {"mafia": 1, "doctor": 1, "detective": 1, "villager": max(0, n - 3)}

    def start(self):
        n = len(self.players)
        bag = []
        for role, count in self._role_counts(n).items():
            bag += [role] * count
        if len(bag) != n:
            raise ValueError("role counts do not match player count")
        if self._include_jester and "villager" in bag:
            bag[bag.index("villager")] = "jester"   # one villager becomes the jester
        random.shuffle(bag)
        for p, role in zip(self.players, bag):
            p.role = role
        self.phase = "reveal"
        self._order = [p.seat for p in self.players]   # everyone, circle order
        self._cursor = 0
        self._stage = "handoff"
        self._seen_reveal = set()
        self._emit("game_start", player_count=n)

    # --------------------------------------------------------------- helpers
    def _emit(self, event, **public_ctx):
        line = self.narrate(event, public_ctx)
        self.public_log.append(line)
        return line

    def _by_seat(self, seat):
        return self.players[seat] if 0 <= seat < len(self.players) else None

    def _alive(self):
        return [p for p in self.players if p.alive]

    def _alive_by_role(self, role):
        return [p for p in self._alive() if p.role == role]

    def _current(self):
        if not self._order or self._cursor >= len(self._order):
            return None
        return self._by_seat(self._order[self._cursor])

    def _next_name(self):
        cur = self._current()
        return cur.name if cur else ""

    def _elapsed_ok(self):
        return (time.monotonic() - self._turn_start) >= self.min_turn_seconds

    def _alive_options(self, exclude_self_seat=None):
        return [
            {"seat": p.seat, "name": p.name}
            for p in self._alive()
            if p.seat != exclude_self_seat
        ]

    # ------------------------------------------------------- pass-and-play turn
    def begin_turn(self):
        """Hand-off -> active. Called when the next player presses and holds."""
        if self._stage != "handoff":
            return
        self._stage = "active"
        self._turn_start = time.monotonic()

    def finish_turn(self):
        """Active -> next player. Enforces the minimum turn time."""
        if self._stage != "active":
            return False
        if not self._elapsed_ok():
            return False
        cur = self._current()
        if self.phase == "reveal" and cur:
            self._seen_reveal.add(cur.seat)
        self._cursor += 1
        if self._cursor >= len(self._order):
            self._end_round()
        else:
            self._stage = "handoff"
        return True

    def _end_round(self):
        if self.phase == "reveal":
            self._stage = None
            self.phase = "reveal_done"
        elif self.phase == "night":
            self._resolve_night()
        elif self.phase == "vote":
            self._resolve_secret_vote()

    # ------------------------------------------------------------------ night
    def begin_night(self):
        self.phase = "night"
        self.day_number += 1
        self._order = [p.seat for p in self.players if p.alive]
        self._cursor = 0
        self._stage = "handoff"
        self._mafia_pick = None
        self._doctor_protect = None
        self._detective_results = {}
        self._emit("night_start", day_number=self.day_number)

    def submit_night(self, target_seat):
        """Record the current player's action. Does not advance the turn, a player may change their pick, and the detective must view the result."""
        if self.phase != "night" or self._stage != "active":
            return
        cur = self._current()
        if not cur:
            return
        target = self._by_seat(target_seat) if target_seat is not None else None
        if cur.role == "mafia":
            if target and target.alive:
                self._mafia_pick = target.seat
        elif cur.role == "doctor":
            if target and target.alive:
                self._doctor_protect = target.seat
        elif cur.role == "detective":
            if target and target.alive:
                # Red if the target reads as a threat, mafia OR jester. The
                # detective sees only a colour, so a red is not proof of mafia
                # (it could be the jester), and green is not proof of innocence.
                self._detective_results[cur.seat] = {
                    "seat": target.seat,
                    "name": target.name,
                    "suspicious": target.role in ("mafia", "jester"),
                }
        # villager: decoy pick, nothing recorded.

    def _resolve_night(self):
        victim = self._by_seat(self._mafia_pick) if self._mafia_pick is not None else None
        saved = (self._doctor_protect is not None and self._doctor_protect == self._mafia_pick)
        died = None
        if victim and victim.alive and not saved:
            victim.alive = False
            died = victim.name
        self._last_protected = self._doctor_protect
        self._last_morning = {"died": died}
        self.history.append({"night": self.day_number, "died": died})
        self.phase = "morning"
        self._stage = None
        if died:
            self._emit("morning_death", name=died)
        else:
            self._emit("morning_safe")
        self._check_win()

    def morning_continue(self):
        if self.phase != "morning":
            return
        if self.winner:
            return
        self.phase = "day"
        self._day_stage = "discussion"
        self._emit("day_start", alive_count=len(self._alive()))

    # -------------------------------------------------------------------- day
    def start_vote(self):
        if self.phase != "day":
            return
        self._emit("discussion_end")
        self.phase = "vote"
        self._votes = {}
        self._revote_used = False
        if self._voting_style == "secret":
            self._order = [p.seat for p in self.players if p.alive]
            self._cursor = 0
            self._stage = "handoff"
        else:
            self._stage = None   # open vote: host enters the result

    def submit_vote(self, target_seat):
        """Secret vote: record the current voter's choice (None = abstain)."""
        if self.phase != "vote" or self._stage != "active":
            return
        cur = self._current()
        if not cur:
            return
        if target_seat is None:
            self._votes[cur.seat] = None
        else:
            t = self._by_seat(target_seat)
            self._votes[cur.seat] = t.seat if (t and t.alive) else None

    def set_open_vote(self, target_seat):
        """Open vote: the host enters who the group voted out (None = no one)."""
        if self.phase != "vote" or self._voting_style != "open":
            return
        out = self._by_seat(target_seat) if target_seat is not None else None
        self._apply_elimination(out)

    def _resolve_secret_vote(self):
        tally = Counter(t for t in self._votes.values() if t is not None)
        out = None
        if tally:
            top = tally.most_common()
            if len(top) == 1 or top[0][1] > top[1][1]:
                out = self._by_seat(top[0][0])
            elif self._revote_on_tie and not self._revote_used:
                # tie -> one revote
                self._revote_used = True
                self._votes = {}
                self._order = [p.seat for p in self.players if p.alive]
                self._cursor = 0
                self._stage = "handoff"
                self._emit("vote_tie")
                return
        self._apply_elimination(out, tie=(out is None and bool(tally)))

    def _apply_elimination(self, out, tie=False):
        self._stage = None
        if out and out.alive:
            out.alive = False
            self._last_vote = {"out": out.name, "tie": False}
            self._emit("vote_out", name=out.name)
            if self._reveal_roles_on_death:
                self._emit("reveal_role", name=out.name, role=out.role)
            if out.role == "jester":
                # The jester's whole goal is being voted out. They win now.
                self.winner = "jester"
                self.phase = "end"
                self._emit("jester_win", name=out.name)
                return
        elif tie:
            self._last_vote = {"out": None, "tie": True}
            self._emit("vote_tie")
        else:
            self._last_vote = {"out": None, "tie": False}
            self._emit("vote_none")
        self.phase = "day"
        self._day_stage = "post_vote"
        self._check_win()

    def day_continue(self):
        """After a vote result, the host moves on to the next night (or the game
        has already ended)."""
        if self.phase != "day" or self.winner:
            return
        self.begin_night()

    def end_now(self):
        """Host force-ends the game: jump straight to the end screen and reveal
        every role. Used from the admin controls."""
        if self.phase == "end":
            return
        self.phase = "end"
        self._stage = None
        if not self.winner:
            self.winner = "ended"

    # ------------------------------------------------------------- win check
    def _check_win(self):
        mafia = len(self._alive_by_role("mafia"))
        others = len(self._alive()) - mafia
        if mafia == 0:
            self.winner = "town"
        elif mafia >= others:
            self.winner = "mafia"
        if self.winner:
            self.phase = "end"
            self._emit("town_win" if self.winner == "town" else "mafia_win")

    # ----------------------------------------------------------------- views
    def public_state(self):
        """Safe for everyone. No roles while the game is in progress."""
        state = {
            "phase": self.phase,
            "day_number": self.day_number,
            "players": [
                {"seat": p.seat, "name": p.name, "alive": p.alive}
                for p in self.players
            ],
            "alive_count": len(self._alive()),
            "log": list(self.public_log),
            "line": self.public_log[-1] if self.public_log else "",
            "winner": self.winner,
            "voting_style": self._voting_style,
            "discussion_seconds": self._discussion_seconds,
        }
        if self.phase == "end":
            state["reveal"] = [
                {"seat": p.seat, "name": p.name, "role": p.role}
                for p in self.players
            ]
            state["history"] = list(self.history)
        return state

    def device_state(self):
        """The single screen the shared device should render right now. During a
        private turn it carries ONLY the current actor's own secret info."""
        p = self.phase
        if p == "setup":
            return {"screen": "lobby"}
        if p == "reveal_done":
            return {"screen": "ready_night", "line": "Everyone has their role."}
        if p == "morning":
            return {
                "screen": "morning",
                "night": False,
                "line": self.public_log[-1] if self.public_log else "",
                "died": (self._last_morning or {}).get("died"),
                "winner": self.winner,
            }
        if p == "day":
            d = {
                "screen": "day",
                "stage": self._day_stage,
                "line": self.public_log[-1] if self.public_log else "",
                "discussion_seconds": self._discussion_seconds,
                "voting_style": self._voting_style,
                "last_vote": self._last_vote,
            }
            if self._day_stage == "discussion":
                d["alive"] = [pl.name for pl in self._alive()]
                d["prompt"] = "Talk it out. Who is lying?"
            return d
        if p == "end":
            return {
                "screen": "end",
                "winner": self.winner,
                "reveal": [{"name": pl.name, "role": pl.role} for pl in self.players],
                "history": list(self.history),
            }

        # Open vote: the host enters the result; no pass-and-play cursor.
        if p == "vote" and self._voting_style == "open":
            return {"screen": "vote_open", "options": self._alive_options()}

        # --- private, pass-and-play turns (reveal / night / vote) ---
        cur = self._current()
        if cur is None:
            return {"screen": "ready_night"}
        if self._stage == "handoff":
            return {"screen": "handoff", "phase": p, "next_name": cur.name,
                    "night": p == "night"}

        # active turn, only this player's own data
        if p == "reveal":
            d = {"screen": "reveal", "name": cur.name, "role": cur.role,
                 "blurb": ROLE_BLURB.get(cur.role, ""),
                 "min_turn_seconds": self.min_turn_seconds}
            if cur.role == "mafia":
                d["teammates"] = [m.name for m in self._alive_by_role("mafia")
                                  if m.seat != cur.seat]
            return d
        if p == "night":
            d = {"screen": "night", "name": cur.name, "night": True,
                 "kind": cur.role, "min_turn_seconds": self.min_turn_seconds}
            if cur.role == "mafia":
                d["prompt"] = "Choose someone to remove."
                d["options"] = self._alive_options(exclude_self_seat=cur.seat)
                pick = self._by_seat(self._mafia_pick) if self._mafia_pick is not None else None
                d["current_pick"] = pick.seat if pick else None
            elif cur.role == "doctor":
                d["prompt"] = "Choose someone to protect."
                d["options"] = self._alive_options()
                if self._doctor_no_repeat and self._last_protected is not None:
                    d["blocked_seat"] = self._last_protected
            elif cur.role == "detective":
                d["prompt"] = "Choose someone to check."
                d["options"] = self._alive_options(exclude_self_seat=cur.seat)
                res = self._detective_results.get(cur.seat)
                if res:
                    d["result"] = {"name": res["name"], "suspicious": res["suspicious"]}
            else:
                # Villager decoy: same shape as the real roles (prompt + name
                # list + pass) so turns look identical, but neutral wording that
                # gives nothing away and doesn't read like the day vote.
                d["prompt"] = "Choose someone."
                d["options"] = self._alive_options(exclude_self_seat=cur.seat)
            return d
        if p == "vote":
            return {"screen": "vote", "name": cur.name,
                    "options": self._alive_options(),
                    "min_turn_seconds": self.min_turn_seconds}
        return {"screen": "lobby"}
