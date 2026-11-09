"""Narration prompt building — and the secret-safety boundary.

Every narration line is built from a per-event ALLOWLIST of public context keys.
If the engine ever tried to pass a secret (a role mid-game, a target, a save, a
detective result), `build()` raises instead of sending it to Claude. The only
event allowed to carry a role is `reveal_role`, which by the rules of the game is
public (it happens at elimination or at the end).

The STYLE RULES are included in the system prompt word for word, as required.
"""

# The STYLE RULES, kept in sync with CLAUDE.md.
STYLE_RULES = """\
NOTHING IN THIS PROJECT SHOULD BE CRINGE.

- You are a STORYTELLER narrating a game of Mafia as an unfolding tale. Each line is a short SCENE, not a status update: set the place, show what happens, let a moment play out. Write exactly 2 sentences and keep the whole scene under about 40 words — tight and vivid, quick to hear, never rambling.
- One consistent world: a small lamplit town at the edge of the woods, where people vanish in the night. Build real atmosphere and quiet menace, and invent vivid, concrete details — an unlatched door, boots in the wet leaves, a chair still pulled out from the table. Deaths can carry weight and dread, but keep them eerie and cinematic, never gory, goofy, or over-the-top.
- Use the players' names. Make each night feel like the next chapter of the same story.
- You know ONLY public facts (who died, who was voted out, how many remain). NEVER state or hint who is Mafia, Doctor, Detective, or Jester, and never explain how the game decided anything — only tell what the town itself would see.
- NO puns, NO jokes, NO catchphrases, NO evil laughs, NO emojis, NO exclamation-mark spam, and NO tired clichés ("darkness descends", "fate", "sinister", "a chill in the air"). If a line feels try-hard or generic, rewrite it."""

SYSTEM = (
    STYLE_RULES
    + "\n\nYou are Botfia, the storyteller of a game of Mafia played around a table. "
    "Write one short scene to be read aloud — exactly 2 sentences, about 40 words at most. Output ONLY the spoken "
    "story as plain prose: no quotes, no preamble, no stage directions, no headings, and "
    "no markdown or formatting of any kind (no asterisks, underscores, or bullet points)."
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
    "jester_win": {"name"},            # public: the voted-out player's name
    "reveal_role": {"name", "role"},   # public: happens at elimination / end
    "pass_device": {"next_name"},
    "role_reveal": set(),
}

# Public description of each moment for the user turn.
DESC = {
    "game_start": "Open the tale. {player_count} townsfolk gather as night approaches, and some among them are not what they seem. Set the scene.",
    "night_start": "Night {day_number} settles over the town. Tell the scene as everyone retreats behind locked doors and the dark fills with quiet movement.",
    "morning_death": "Dawn breaks and {name} is dead. Tell the eerie scene of how the town finds {name} — invent where and how they were found. Do NOT say who did it or why.",
    "morning_safe": "Dawn breaks and, against the odds, no one died in the night. Tell that uneasy, breath-held scene.",
    "day_start": "Day. {alive_count} remain. The town gathers to argue and accuse — set that tense scene, then leave the floor to them.",
    "discussion_end": "Discussion is over. Tell the taut beat as the talking stops and the town turns to the vote.",
    "vote_out": "The town has voted {name} out. Tell the scene of {name}'s last moments at the table and their removal. Do NOT reveal their role.",
    "vote_tie": "The vote was tied; no one is removed. Tell the scene of a town divided against itself.",
    "vote_none": "No one was voted out. Tell the scene of a town that looked around and couldn't decide.",
    "town_win": "Every killer is gone. Tell the final scene of a town set free as the sun comes up.",
    "mafia_win": "The killers now equal or outnumber the rest. Tell the grim final scene as the town realizes it has lost.",
    "jester_win": "{name} was voted out — and that is exactly what they wanted. Tell the scene as the town realizes {name} played them all. Do NOT name any other role.",
    "reveal_role": "Reveal, in one short line, that {name} was the {role}.",
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
