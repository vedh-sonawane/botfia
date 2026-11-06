"""Narration prompt building — and the secret-safety boundary.

Every narration line is built from a per-event ALLOWLIST of public context keys.
If the engine ever tried to pass a secret (a role mid-game, a target, a save, a
detective result), `build()` raises instead of sending it to Claude. The only
event allowed to carry a role is `reveal_role`, which by the rules of the game is
public (it happens at elimination or at the end).

The STYLE RULES are included in the system prompt word for word, as required.
"""

# The STYLE RULES, verbatim from CLAUDE.md.
STYLE_RULES = """\
NOTHING IN THIS PROJECT SHOULD BE CRINGE.

- NARRATION IS SHORT, CALM, DRY, AND SERIOUS. A quiet, confident narrator. Understated is creepier than dramatic.
- NO JOKES, NO PUNS, NO CATCHPHRASES, NO EVIL LAUGHS, NO "MWAHAHA", NO EMOJIS, NO EXCLAMATION MARKS.
- NO CLICHES: no "darkness descends", "fate", "sinister", "doom", "the night is young", "a chill in the air".
- SAY THE MINIMUM. Right tone: "The town is asleep." / "Morning. Daniel did not wake up."
- IF YOU ARE UNSURE WHETHER SOMETHING IS CRINGE, IT IS. LEAVE IT OUT."""

SYSTEM = (
    STYLE_RULES
    + "\n\nYou are Botfia, the narrator of a game of Mafia played around a table. "
    "Write exactly one line to be spoken aloud. Maximum two sentences. Output only "
    "the line itself — no quotes, no preamble, no stage directions."
)

# Per-event allowed public context keys. ctx keys must be a subset of these.
ALLOWED = {
    "game_start": {"player_count"},
    "night_start": {"day_number"},
    "morning_death": {"name"},
    "morning_safe": set(),
    "day_start": {"alive_count"},
    "discussion_end": set(),
    "vote_out": {"name"},
    "vote_tie": set(),
    "vote_none": set(),
    "town_win": set(),
    "mafia_win": set(),
    "reveal_role": {"name", "role"},   # public: happens at elimination / end
    "pass_device": {"next_name"},
    "role_reveal": set(),
}

# Public description of each moment for the user turn.
DESC = {
    "game_start": "The game is beginning with {player_count} players at the table.",
    "night_start": "Night {day_number}. The town goes to sleep.",
    "morning_death": "Morning comes. {name} was killed in the night. Announce it by name.",
    "morning_safe": "Morning comes. No one was killed in the night. Announce it.",
    "day_start": "It is day. {alive_count} players remain. Tell them to discuss.",
    "discussion_end": "Discussion is over. It is time to vote.",
    "vote_out": "The town voted {name} out. Announce it by name.",
    "vote_tie": "The vote was tied. No one is eliminated.",
    "vote_none": "No one was voted out.",
    "town_win": "Every mafia member is gone. The town has won.",
    "mafia_win": "The mafia now equal or outnumber the rest of the town. The mafia has won.",
    "reveal_role": "Reveal that {name} was the {role}.",
    "pass_device": "Pass the device to {next_name}.",
    "role_reveal": "Tell each player to learn their role by holding to see it.",
}


def assert_public(event, ctx):
    """Guarantee the context carries nothing beyond the public keys for this event."""
    allowed = ALLOWED.get(event)
    if allowed is None:
        raise ValueError(f"unknown narration event: {event}")
    extra = set(ctx or {}) - allowed
    if extra:
        raise ValueError(f"secret or unexpected keys for '{event}': {sorted(extra)}")


def build(event, ctx):
    """Return (system, user) for a Claude call, or raise if ctx isn't public."""
    ctx = dict(ctx or {})
    assert_public(event, ctx)
    template = DESC.get(event, "Narrate the current moment briefly.")
    try:
        user = template.format(**ctx)
    except KeyError:
        user = template
    return SYSTEM, user
