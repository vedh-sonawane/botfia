"""Botfia game engine — the Mafia state machine.

This is PLAIN CODE. It decides every outcome: role assignment, night kills,
doctor saves, detective results, votes, and wins. Claude is never involved here.

Secret safety is the core rule. Two views exist:
  - public_state(): what everyone (and later, Claude for narration) may see. It
    NEVER contains roles, who the mafia targeted, who the doctor saved, or
    detective results. Roles are only revealed at the end of the game.
  - player_view(pid): what one player sees on their own phone, including their
    own role and their own private results (e.g. a detective's check result).

Phases: lobby -> reveal -> night -> day -> vote -> (loop) -> end
"""

import json
import random
from collections import Counter
from enum import Enum
from pathlib import Path

ROLES_PATH = Path(__file__).with_name("roles.json")


class Phase(str, Enum):
    LOBBY = "lobby"       # players join; host configures and starts
    REVEAL = "reveal"     # each player privately confirms their role
    NIGHT = "night"       # everyone taps; mafia/doctor/detective act
    DAY = "day"           # announce what happened; discuss
    VOTE = "vote"         # players vote to eliminate someone
    END = "end"           # winner announced, all roles revealed


class Player:
    def __init__(self, pid, name, seat):
        self.id = pid
        self.name = name
        self.seat = seat
        self.role = None
        self.alive = True


def load_role_table():
    data = json.loads(ROLES_PATH.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


class GameEngine:
    def __init__(self, role_table=None):
        self.role_table = role_table or load_role_table()
        self.players = {}            # pid -> Player
        self.phase = Phase.LOBBY
        self.day_number = 0
        self.winner = None           # "mafia" or "town"
        # per-round working state (secret)
        self._night_actions = {}     # pid -> target pid or None
        self._votes = {}             # pid -> target pid or None
        self._detective_results = {} # detective pid -> {"target_seat": s, "is_mafia": bool}
        # public announcements (NO secrets) — the lines narration will speak
        self.public_log = []

    # ---------- lobby ----------
    def add_player(self, name, seat):
        if self.phase != Phase.LOBBY:
            raise ValueError("game already started")
        name = (name or "").strip()[:20] or "Player"
        if any(p.seat == seat for p in self.players.values()):
            raise ValueError("seat taken")
        pid = f"p{len(self.players) + 1}_{random.randint(1000, 9999)}"
        self.players[pid] = Player(pid, name, seat)
        return pid

    def _alive(self):
        return [p for p in self.players.values() if p.alive]

    def _alive_by_role(self, role):
        return [p for p in self._alive() if p.role == role]

    # ---------- start / roles ----------
    def start_game(self):
        n = len(self.players)
        key = str(n)
        if key not in self.role_table:
            raise ValueError(f"no role setup for {n} players")
        bag = []
        for role, count in self.role_table[key].items():
            bag += [role] * count
        if len(bag) != n:
            raise ValueError("role counts do not match player count")
        random.shuffle(bag)
        for player, role in zip(self.players.values(), bag):
            player.role = role
        self.phase = Phase.REVEAL
        self.public_log.append("The game begins.")

    # ---------- night ----------
    def begin_night(self):
        self.phase = Phase.NIGHT
        self.day_number += 1
        self._night_actions = {}
        self._detective_results = {}

    def submit_night_action(self, pid, target_pid):
        """Every alive player submits once. Villagers pass target_pid=None."""
        if self.phase != Phase.NIGHT:
            raise ValueError("not night")
        player = self.players.get(pid)
        if not player or not player.alive:
            raise ValueError("unknown or dead player")
        self._night_actions[pid] = target_pid
        # Detective learns their result privately, immediately.
        if player.role == "detective" and target_pid in self.players:
            t = self.players[target_pid]
            self._detective_results[pid] = {
                "target_seat": t.seat,
                "target_name": t.name,
                "is_mafia": t.role == "mafia",
            }

    def night_done(self):
        return all(p.id in self._night_actions for p in self._alive())

    def resolve_night(self):
        """Kill the mafia's target unless the doctor saved them. Returns the
        public result (no secrets): the dead player's seat/name, or None."""
        mafia_targets = [
            self._night_actions.get(m.id)
            for m in self._alive_by_role("mafia")
        ]
        mafia_targets = [t for t in mafia_targets if t in self.players]
        victim_pid = None
        if mafia_targets:
            victim_pid = Counter(mafia_targets).most_common(1)[0][0]

        saved = [
            self._night_actions.get(d.id)
            for d in self._alive_by_role("doctor")
        ]
        result = None
        if victim_pid and victim_pid not in saved:
            victim = self.players[victim_pid]
            victim.alive = False
            result = {"seat": victim.seat, "name": victim.name}
            self.public_log.append(f"Morning. {victim.name} did not wake up.")
        else:
            self.public_log.append("Morning. Everyone is still here.")

        self.phase = Phase.DAY
        self._check_win()
        return result

    # ---------- vote ----------
    def begin_vote(self):
        self.phase = Phase.VOTE
        self._votes = {}

    def submit_vote(self, pid, target_pid):
        if self.phase != Phase.VOTE:
            raise ValueError("not vote")
        player = self.players.get(pid)
        if not player or not player.alive:
            raise ValueError("unknown or dead player")
        self._votes[pid] = target_pid  # None allowed = abstain

    def vote_done(self):
        return all(p.id in self._votes for p in self._alive())

    def resolve_vote(self):
        """Eliminate the player with the most votes. A tie eliminates no one."""
        tally = Counter(t for t in self._votes.values() if t in self.players)
        result = None
        if tally:
            top = tally.most_common()
            if len(top) == 1 or top[0][1] > top[1][1]:
                out = self.players[top[0][0]]
                out.alive = False
                result = {"seat": out.seat, "name": out.name}
                self.public_log.append(f"{out.name} was voted out.")
            else:
                self.public_log.append("The vote was tied. No one was eliminated.")
        else:
            self.public_log.append("No votes were cast.")

        self.phase = Phase.DAY
        self._check_win()
        return result

    # ---------- win check ----------
    def _check_win(self):
        mafia = len(self._alive_by_role("mafia"))
        town = len(self._alive()) - mafia
        if mafia == 0:
            self.winner = "town"
            self.phase = Phase.END
            self.public_log.append("The town wins.")
        elif mafia >= town:
            self.winner = "mafia"
            self.phase = Phase.END
            self.public_log.append("The mafia wins.")

    # ---------- views ----------
    def public_state(self):
        """Safe for everyone. No roles or secret actions during play."""
        state = {
            "phase": self.phase.value,
            "day_number": self.day_number,
            "players": sorted(
                ({"seat": p.seat, "name": p.name, "alive": p.alive}
                 for p in self.players.values()),
                key=lambda x: x["seat"],
            ),
            "log": list(self.public_log),
            "winner": self.winner,
        }
        if self.phase == Phase.END:
            # Roles are public ONLY once the game is over.
            state["reveal"] = sorted(
                ({"seat": p.seat, "name": p.name, "role": p.role}
                 for p in self.players.values()),
                key=lambda x: x["seat"],
            )
        return state

    def player_view(self, pid):
        """What one player sees: their own role and their own private info."""
        player = self.players.get(pid)
        if not player:
            return None
        view = {
            "seat": player.seat,
            "name": player.name,
            "role": player.role,
            "alive": player.alive,
            "phase": self.phase.value,
            "submitted_night": pid in self._night_actions,
            "submitted_vote": pid in self._votes,
        }
        if player.role == "detective" and pid in self._detective_results:
            view["detective_result"] = self._detective_results[pid]
        return view
