"""Prewritten fallback narration.

These are the scenes Botfia tells out loud when the Claude API or the internet
is unavailable. They must match the tone of good narration: short story beats of
2-3 sentences, set in one small lamplit town at the edge of the woods. Eerie and
atmospheric, never gory, goofy, or cringe. No puns, no emojis, no exclamation-mark
spam, no markdown, no tired clichés.

Everything here is pure and offline, and nothing here references a secret:
no roles, no who the mafia targeted, no who the doctor saved, no detective
results. Only the public fields passed in through ``ctx`` are ever used.
"""

import random

# One bank per event. Each entry is a plain format string that only ever refers
# to public ``ctx`` fields. Pick one at random so the game does not repeat itself.
# Story beats run 2-3 sentences; the UI prompts and the end-game reveal stay short.
_BANK = {
    # Start of the game. ctx: {player_count}
    "game_start": [
        "There are {player_count} of you in the little town at the edge of the woods tonight, and some of them are lying. By morning you will start finding out who.",
        "{player_count} gather by lamplight, all easy smiles — but not everyone here means the others well. The story starts now.",
    ],
    # Private role reveal, passed around the circle. ctx: {} (short instruction)
    "role_reveal": [
        "Hold the screen to see who you are tonight. Let go before anyone leans in.",
        "Your role is under your thumb. Look, remember, hide it, and pass it on.",
    ],
    # Hand-off screen between players. ctx: {next_name} (short)
    "pass_device": [
        "Pass it to {next_name}.",
        "{next_name}, it is yours.",
        "Over to {next_name}.",
    ],
    # Start of a night. ctx: {day_number}
    "night_start": [
        "The last lamp goes out and the town shuts its doors against the dark. Somewhere past the fences, someone is already awake and moving.",
        "Shutters close one by one until the whole town is black and still. Not everyone behind those doors intends to sleep tonight.",
    ],
    # Morning after someone was killed in the night. ctx: {name}
    "morning_death": [
        "They found {name} at first light, out past the fence where the lamplight dies. No one heard a sound in the night.",
        "{name} bolted the door twice, and it made no difference. This morning their chair sat empty, still pulled out from the table.",
        "The dogs started barking before dawn. {name} was out past the mill road, and by the time the town arrived there was nothing to be done.",
    ],
    # Morning when no one died. ctx: {}
    "morning_safe": [
        "There were footsteps on the stairs last night, and a door that thought better of opening. But the sun came up on a full table — someone lost their nerve.",
        "The town held its breath through every dark hour. Morning came, and somehow no one was missing.",
    ],
    # Start of the day discussion. ctx: {alive_count}
    "day_start": [
        "The bell pulls {alive_count} of you into the square, uneasy in the daylight. Talk it out — and watch whose eyes do not quite meet yours.",
        "{alive_count} remain to sort friend from killer. Make your case, before someone makes one about you.",
    ],
    # Discussion time is up; move to the vote. ctx: {}
    "discussion_end": [
        "The arguing dies down and the square goes still. It is time to choose, and someone is not walking home.",
        "The talking is done. Now the town has to decide — and live with it.",
    ],
    # Someone was voted out. ctx: {name}
    "vote_out": [
        "The town turned on {name} all at once, and the hands went up before the shouting stopped. The gate shut behind them, and no one could say for certain they got it right.",
        "{name} was walked to the edge of town, protesting every step. The crowd did not waver.",
    ],
    # The vote tied. ctx: {}
    "vote_tie": [
        "The vote split clean down the middle, and no one could break it. Whoever should have gone tonight lives to see another dawn.",
        "The vote came back even. The gate stays shut, and everyone stays — for now.",
    ],
    # No one was voted out. ctx: {}
    "vote_none": [
        "The town looked from face to face and could not point at anyone. Everyone goes home tonight — including whoever should not.",
        "Nobody. The town chose to trust its own, and the night will decide whether that was brave or foolish.",
    ],
    # Town victory. ctx: {}
    "town_win": [
        "The last of them is dragged into the daylight, and the town finally breathes. Tonight, for the first time in a while, it sleeps.",
        "The killers are gone, pulled into the light one by one, and the square breathes again. The town has won.",
    ],
    # Mafia victory. ctx: {}
    "mafia_win": [
        "There are not enough honest faces left to matter, and the ones who remain see too late who has been among them. The town belongs to the woods now.",
        "One by one the town fell, and the ones who did it no longer need to hide. The doors will not save anyone tonight.",
    ],
    # Jester victory. ctx: {name}
    "jester_win": [
        "{name} went to the gate smiling, and only now do you understand why. They wanted the vote, played all of you, and walked away the winner.",
        "The town was so sure about {name} — and that was the whole idea. The jester got exactly what they came for.",
    ],
    # End-of-game role reveal, when every role is already public. ctx: {name, role} (short)
    "reveal_role": [
        "{name} was the {role}.",
        "Turns out {name} was the {role} all along.",
        "{name} — the {role}.",
        "And {name}? The {role}.",
    ],
}

# Said for any event we don't recognize. Minimal and safe; never crashes.
_NEUTRAL = "The town waits."


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
        "jester_win": {"name": "Maria"},
        "reveal_role": {"name": "Daniel", "role": "detective"},
        "unknown_event": {},
    }
    for event, ctx in examples.items():
        print(f"{event:>15}: {line(event, ctx)}")
