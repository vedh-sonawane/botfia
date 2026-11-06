"""Prewritten fallback narration.

These are the lines Botfia says out loud when the Claude API or the internet
is unavailable. They must be indistinguishable in tone from good narration:
short, calm, dry, serious. No jokes, no emojis, no exclamation marks, no
cliches. Understated. Say the minimum.

Everything here is pure and offline, and nothing here references a secret:
no roles, no who the mafia targeted, no who the doctor saved, no detective
results. Only the public fields passed in through ``ctx`` are ever used.
"""

import random

# One bank per event. Each entry is a plain format string that only ever
# refers to public ``ctx`` fields. Pick one at random so the game does not
# repeat itself. Keep every line to at most two sentences.
_BANK = {
    # Start of the game. ctx: {player_count}
    "game_start": [
        "{player_count} players. The town is quiet.",
        "{player_count} at the table. Let's begin.",
        "{player_count} players. Learn who you are first.",
        "We have {player_count}. Settle in.",
        "{player_count} players. The game starts now.",
        "{player_count} tonight. Hold the device and begin.",
    ],
    # Private role reveal, passed around the circle. ctx: {}
    "role_reveal": [
        "Learn your role. Hold to see it. Let go to hide it.",
        "Press and hold to read your role. Let go to hide it.",
        "Hold the screen to see who you are. Let go when you're done.",
        "Your role is under your thumb. Hold to read, release to hide.",
        "Check your role quietly. Hold to see it, let go to hide it.",
        "Hold to reveal your role. Release, then pass it on.",
    ],
    # Hand-off screen between players. ctx: {next_name}
    "pass_device": [
        "Pass to {next_name}.",
        "Hand the device to {next_name}.",
        "{next_name} is next.",
        "Pass it on. {next_name}.",
        "Over to {next_name}.",
        "Give the device to {next_name}.",
    ],
    # Start of a night. ctx: {day_number}
    "night_start": [
        "The town is asleep. Close your eyes.",
        "Night falls. Everyone, close your eyes.",
        "The town goes to sleep.",
        "Eyes closed. The town is asleep.",
        "It's night. Close your eyes and stay quiet.",
        "The town sleeps. Keep your eyes shut.",
    ],
    # Morning after someone was killed in the night. ctx: {name}
    "morning_death": [
        "Morning. {name} did not wake up.",
        "Morning. {name} is gone.",
        "Morning. We lost {name} in the night.",
        "The town wakes. {name} is dead.",
        "Morning. {name} did not make it through the night.",
        "Daylight. {name} is no longer with us.",
    ],
    # Morning when no one died. ctx: {}
    "morning_safe": [
        "Morning. Everyone is still here.",
        "Morning. No one was lost.",
        "The town wakes. Everyone made it through.",
        "Daylight. Nobody died tonight.",
        "Morning. The town is whole.",
        "Morning. No one is missing.",
    ],
    # Start of the day discussion. ctx: {alive_count}
    "day_start": [
        "{alive_count} are left. Talk it over.",
        "{alive_count} remain. Decide who you suspect.",
        "{alive_count} still here. Discuss.",
        "{alive_count} at the table. Make your case.",
        "{alive_count} left. The floor is yours.",
        "{alive_count} remain. Time to talk.",
    ],
    # Discussion time is up; move to the vote. ctx: {}
    "discussion_end": [
        "Time is up. Cast your votes.",
        "Discussion is over. Vote now.",
        "That's the end of the discussion. Vote.",
        "Time's up. Decide who goes.",
        "Talk is done. It's time to vote.",
        "No more discussion. Vote.",
    ],
    # Someone was voted out. ctx: {name}
    "vote_out": [
        "{name} was voted out.",
        "The town chose {name}.",
        "{name} is out.",
        "{name} leaves the table.",
        "The vote falls on {name}.",
        "{name} was eliminated.",
    ],
    # The vote tied. ctx: {}
    "vote_tie": [
        "The vote is tied. No one is eliminated.",
        "It's a tie. No one goes.",
        "The vote is split. No one leaves.",
        "Tied vote. No one is out.",
        "The town is split. No one is eliminated.",
    ],
    # No one was voted out (e.g. the town declined to vote). ctx: {}
    "vote_none": [
        "No one was voted out.",
        "The town kept everyone.",
        "No one leaves the table.",
        "No vote carried. Everyone stays.",
        "The town chose no one.",
    ],
    # Town victory. ctx: {}
    "town_win": [
        "The town wins.",
        "The mafia is gone. The town wins.",
        "The town holds. They win.",
        "That's the last of the mafia. The town wins.",
    ],
    # Mafia victory. ctx: {}
    "mafia_win": [
        "The mafia wins.",
        "The mafia has the numbers. They win.",
        "The town falls. The mafia wins.",
        "The town can't recover. The mafia wins.",
    ],
    # End-of-game role reveal, when every role is already public.
    # ctx: {name, role}
    "reveal_role": [
        "{name} was the {role}.",
        "{name}: {role}.",
        "{name} played the {role}.",
        "{name} was a {role} all along.",
        "{name} had the {role}.",
    ],
}

# Said for any event we don't recognize. Minimal and safe; never crashes.
_NEUTRAL = "Botfia is thinking."


def line(event: str, ctx: dict | None = None) -> str:
    """Return one prewritten public narration line for ``event``.

    Picks at random from several equally-good variants. Pure and offline.
    Only uses the public fields in ``ctx``; never references a secret. An
    unknown event (or a missing ctx field) returns a safe neutral line
    instead of raising.
    """
    ctx = ctx or {}
    variants = _BANK.get(event)
    if not variants:
        return _NEUTRAL
    template = random.choice(variants)
    try:
        return template.format(**ctx)
    except (KeyError, IndexError):
        # A required field was missing from ctx. Fall back rather than crash.
        return _NEUTRAL


if __name__ == "__main__":
    # Print one example of every event so the lines can be eyeballed.
    examples = {
        "game_start": {"player_count": 7},
        "role_reveal": {},
        "pass_device": {"next_name": "Daniel"},
        "night_start": {"day_number": 1},
        "morning_death": {"name": "Daniel"},
        "morning_safe": {},
        "day_start": {"alive_count": 6},
        "discussion_end": {},
        "vote_out": {"name": "Maria"},
        "vote_tie": {},
        "vote_none": {},
        "town_win": {},
        "mafia_win": {},
        "reveal_role": {"name": "Daniel", "role": "detective"},
        "unknown_event": {},
    }
    for event, ctx in examples.items():
        print(f"{event:>15}: {line(event, ctx)}")
