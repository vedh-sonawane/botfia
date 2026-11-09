# Setup checklist

Do these once, in order, before the first game. Each step is short. Related guides:
WIRING.md (the table unit), docs/SPEAKER.md (the speaker), docs/GAME_NIGHT.md
(running a game).

## 1. API key

Put your Anthropic key in a `.env` file at the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is gitignored and never committed. If this key is missing or the internet is
down, Botfia still runs, it falls back to prewritten narration lines.

## 2. Wi-Fi

Two things need the Wi-Fi details:

- The ESP32 table unit. Copy `esp32-robot/src/secrets.example.h` to
  `esp32-robot/src/secrets.h` and fill in the network name and password, then
  reflash the board. `secrets.h` is gitignored.
- The shared device (the phone, tablet, or laptop everyone passes around). Join it to
  the same network the Pi is on, then open `botfia.local`.

The Pi, the ESP32, and the shared device must all be on the same Wi-Fi network.

## 3. Music

Import your instrumental tracks and list them in `music/tracks.json`. See
`music/README.md` for the exact format (each track needs an id, a file, and a mood:
calm, uneasy, tense, or final). Botfia picks tracks by id from that list, so the file
and the list must match.

## 4. Voice

Choose the Piper voice. Audition the candidates and pick the calmest one:

```
python -m pi.audio.tts --audition
```

Set your choice in config. Keep it plain and natural.

## 5. Light / dark threshold

Calibrate what "dark" means for your room so the night check is reliable. With the
ESP32 wired and online:

- With the room light on, store the bright reading: `POST /calibrate {"state":"light"}`.
- With the room light off, store the dark reading: `POST /calibrate {"state":"dark"}`.

The threshold is set midway between the two readings. Setup also runs this
auto-calibration for you by reading the room light-on and light-off, so in practice
you just confirm it during the first game.
