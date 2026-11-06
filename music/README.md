# Music for Botfia

Botfia plays quiet instrumental music under the game. The mood changes with the
game state: `calm`, `uneasy`, `tense`, `final`. Claude picks a mood; the code
plays a random track tagged with that mood from `tracks.json`.

Read the style rules in `CLAUDE.md` first. In short: the music is **quiet,
instrumental, slow, and plain**. No sound effects of any kind (no thunder,
wolves, screams, creaking doors), no vocals, no big drops, nothing dramatic.
Understated is the whole point.

## How many tracks to get

Get about 7 total so moods do not repeat too often:

| Mood    | How many | When it plays                                   |
|---------|----------|--------------------------------------------------|
| calm    | 2        | setup, role reveal, early day discussion         |
| uneasy  | 2        | night begins, quiet tension                      |
| tense   | 2        | late game, voting, few players left              |
| final   | 1        | the end / win reveal                             |

## What to pick (qualities)

- Instrumental only. No singing, no spoken word.
- Slow and steady. Low energy. No sudden loud parts.
- Minimal: a soft piano, pad, or low strings. Ambient/drone works well.
- No sound effects baked in.
- 2-5 minutes is fine; the player loops tracks, so length does not matter much.
- `calm` = soft and open. `uneasy` = low, a little hollow. `tense` = darker,
  still quiet, a slow pulse is ok. `final` = sparse and resolved.

## Where to get royalty-free tracks

Pick any of these. All are free; mind the license notes.

1. **Pixabay Music** — https://pixabay.com/music/
   - Free for commercial and personal use, no attribution required.
   - Filter by "ambient", "cinematic", or "piano". Good default source.

2. **Free Music Archive (CC0 / Public Domain)** — https://freemusicarchive.org/
   - Filter the license to **CC0** to avoid attribution requirements.
   - Search "ambient", "drone", "piano".

3. **Incompetech (Kevin MacLeod)** — https://incompetech.com/music/royalty-free/
   - Free under **CC-BY**: you MUST credit the artist. If you use these, add a
     short credit line (artist, track, license) to the project README or an end
     screen. Look in the "Calming" and "Dark/Horror-but-quiet" sets, and ignore
     anything busy or jumpy.

Other fine sources: Chosic (https://www.chosic.com/free-music/), and
purple-planet (CC-BY, credit required).

## Where to put the files, and how to tag them

1. Download the audio files into this `music/` folder.
   - `.ogg`, `.mp3`, or `.wav` all work. `.ogg` keeps files small.

2. Tag them by mood, which (re)writes `tracks.json`:

   ```
   # from the repo root
   python -m pi.audio.import_music                 # interactive: asks a mood per file
   # or tag one file non-interactively:
   python -m pi.audio.import_music --file calm_piano.ogg --mood calm
   ```

   If you have `ffmpeg` installed, add `--convert` to normalize everything to a
   consistent `.ogg` (optional, keeps files uniform and small).

3. Check `tracks.json`. Each entry is `{ "id", "file", "mood" }`. You can edit it
   by hand too. The code checks each file exists before playing, so a leftover
   placeholder entry simply never plays.

## Attribution

If any track requires credit (e.g. CC-BY from Incompetech), keep a short list
here:

- (example) "Awkward Meeting" by Kevin MacLeod — CC-BY 4.0 — incompetech.com
