# Botfia

Botfia is a physical robot that hosts the party game Mafia. It sits on the table,
runs the night and day phases, turns the room's light off and on, lights its eyes
and smile, and narrates the game out loud. The game is **pass-and-play on one
shared device** — there are no personal phones, no cameras, and no physical role
cards. Botfia assigns roles itself and the device is passed around the circle.

## STYLE RULES — READ FIRST, APPLY TO EVERYTHING

NOTHING IN THIS PROJECT SHOULD BE CRINGE. Narration, UI, text, music, names, code
comments, docs. Everything.

- NARRATION IS SHORT, CALM, DRY, AND SERIOUS. A quiet, confident narrator.
  Understated is creepier than dramatic.
- NO JOKES, NO PUNS, NO CATCHPHRASES, NO EVIL LAUGHS, NO "MWAHAHA", NO EMOJIS,
  NO EXCLAMATION MARKS.
- NO CLICHES: no "darkness descends", "fate", "sinister", "doom", "the night is
  young", "a chill in the air".
- SAY THE MINIMUM. Right tone: "The town is asleep." / "Morning. Daniel did not
  wake up."
- MUSIC IS INSTRUMENTAL AND QUIET. NO SOUND EFFECTS: no thunder, wolves, screams,
  creaking doors.
- IF YOU ARE UNSURE WHETHER SOMETHING IS CRINGE, IT IS. LEAVE IT OUT.

## UI RULES — NO COMPROMISE

THE UI MUST BE INSANELY WELL MADE, NOT FLASHY. Cinematic, restrained, flawless —
like the best premium app you've used.

- Dark, minimal, premium. Beautiful typography, generous spacing, perfect
  alignment, a tight color palette.
- Smooth, purposeful animations. Every motion feels deliberate. Nothing gimmicky.
- NO emojis, neon, spooky fonts, skulls, blood, glitch effects, confetti, or
  cheesy gradients.
- Night mode: when the room is dark, the screen goes to a near-black theme with
  low-contrast deep-red accents so it lights only the person holding it.
- Huge tap targets, one-handed, works in the dark.
- Installable full-screen PWA. Screen wake lock. Haptics on supported devices.
- Polish every state: loading, error, reconnecting, empty, end of game.
- Must look perfect at phone, tablet, and laptop sizes.

## How the game works — PASS-AND-PLAY ON ONE SHARED DEVICE

One device (phone, tablet, or laptop on the Pi's Wi-Fi) opens the web app and is
passed around the circle.

Roles: Mafia, Doctor, Detective, Villager. Default counts (editable in setup):
- 5-6 players: 1 Mafia; 7-9: 2 Mafia; 10-12: 3 Mafia. Always 1 Doctor, 1
  Detective. Everyone else is a Villager.

SETUP
- Host enters player names in circle order (the pass order) and can adjust role
  counts, discussion time, voting style, and volumes.
- Role reveal: the device is passed around. Each player presses and holds to see
  their role; it hides the instant they let go. Mafia also see their teammates.
  Tap done and pass on.

NIGHT
- Botfia announces the night. The Pi flips the light off; the ESP32 photoresistor
  confirms the room is dark (retry the flip up to 2x); then eyes and smile fade on
  and quiet music plays. Botfia speaks very little at night.
- The device goes around the circle. EVERY player gets a turn:
  - Mafia: choose a victim. Later Mafia see the current pick and can change it;
    the last pick counts.
  - Doctor: choose someone to protect. Config: can't protect the same person two
    nights in a row.
  - Detective: choose someone to check; the answer shows privately (press-and-hold).
  - Villager: a decoy screen ("who do you suspect most?") that looks and takes the
    same time as a real turn.
- EVERY TURN LOOKS AND TAKES ROUGHLY THE SAME TIME. Enforce a minimum turn time so
  nobody can read roles from timing or screen shape. A neutral "pass to [next]"
  hand-off screen separates players; the next player must press-and-hold to begin.
  No back button or gesture may ever reveal a previous player's screen.

MORNING
- Light on, eyes and smile fade off. Botfia announces what happened BY NAME with a
  short Claude line (who died, or that nobody did). Eliminated roles are revealed
  (configurable).

DAY
- Big, calm discussion countdown. Host can pause, add time, or skip.
- Voting, two styles (host picks): Secret (pass the device, vote privately) or
  Open (show of hands; host enters who was voted out). Ties: one revote, then
  nobody is eliminated if still tied (configurable). Botfia announces the result.

END
- Town wins when all Mafia are eliminated. Mafia wins when Mafia equal or
  outnumber everyone else. Botfia announces the winner and reveals every role.
  A clean end screen summarizes the game (who did what each night).

HOST CONTROLS (always available, behind a deliberate gesture so players don't hit
them by accident): pause, repeat last line, skip, volume, light test, end, restart.

## Architecture

- RASPBERRY PI 5 (1GB), mounted at the wall on a 5V power bank. The brain: game
  engine, web app server, Claude API, text-to-speech, music, and the light-switch
  servo (local, hardware PWM — already working; keep that code). Audio goes to the
  Sony speaker over Bluetooth.
- ESP32-WROOM-32 on the table, powered by a USB charger. Drives the two red eye
  LEDs, the smile LEDs, and a photoresistor that confirms the room is dark. Talks
  to the Pi over Wi-Fi with auto-reconnect and a heartbeat. THIS BOARD HAS NO 5V
  PIN — LEDs run from its 3.3V GPIO.
- SONY SPEAKER: Bluetooth from the Pi; auto-reconnect on boot; status shown on the
  host screen.
- SHARED DEVICE: any phone/tablet/laptop on the Pi's Wi-Fi opens the web app.
  Make connecting effortless (mDNS `botfia.local`, clear IP fallback, PWA install).
- NOT USED: Arduino, USB camera, touch pads, personal phones, physical cards, and
  motors (shuffle drum, head turning). Motors are a possible later phase — leave a
  clean, empty hook (`pi/hardware/motors.py` stub) and nothing more.

Communication (Pi -> ESP32): HTTP + JSON on the local network. The light-switch
servo is local to the Pi (direct GPIO), no network.

## Lights and eyes

- Night: Pi flips the light off. ESP32 photoresistor checks the room went dark; if
  still bright, retry the flip (up to 2x). Once dark, eyes and smile fade on.
- If still not dark after retries: continue the game, show a quiet warning on the
  host screen. Never block the game.
- Morning: light on, eyes and smile fade off.
- Auto-calibrate the "dark" threshold at setup by reading the room light-on and
  light-off.
- If the ESP32 is offline, the game continues normally without the eyes.

## Claude narration

- Anthropic Python SDK. API key in `.env` (`ANTHROPIC_API_KEY`), never committed.
- Model in config. Default for narration: `claude-sonnet-4-6` (the current Sonnet;
  `claude-sonnet-5-5` is not a real model id).
- The narration prompt includes the STYLE RULES word for word. Max two sentences
  per line.
- GAME LOGIC IS PLAIN CODE. Claude only writes lines and picks music. Claude never
  decides outcomes.
- NEVER LEAK SECRETS. Public narration and its prompts only ever get public
  information — never who is Mafia, who the doctor saved, or detective results.
  Automated tests prove secrets never reach the narration layer.
- No waiting: pre-generate upcoming lines while the game runs (e.g. write both
  possible morning outcomes during the night) so Botfia speaks instantly.
- If the API or internet fails, fall back to a large bank of prewritten lines that
  follow the style rules. The game must never break.

## Voice and music

- TTS: Piper, local on the Pi. Pick the calmest natural voice. Provide a command
  to audition candidate voices. Keep TTS swappable. Pre-render lines to audio so
  there is no delay.
- Music: a `music/` folder + `music/tracks.json` (id, file, mood: calm, uneasy,
  tense, final). Claude picks a track id from the list by game state; code checks
  the id exists before playing. Low volume, smooth crossfades, music ducks under
  narration.

## Reliability

- Everything starts on boot via systemd. Plug in the power bank and Botfia is
  ready.
- Health screen in the host controls: Wi-Fi, ESP32, speaker, Claude API, light.
- Keep it light for 1GB RAM. No local LLMs or heavy vision.
- A full simulation mode runs on a laptop with no hardware (mocked light, mocked
  ESP32, audio on the laptop) so a whole game is playable for testing.
- Automated tests: game logic, win conditions, secret-leak checks, equal turn
  timing, hand-off privacy.
- Run a complete simulated game end to end before declaring done.

## Hardware inventory — ONLY THESE PARTS EXIST

- Raspberry Pi 5 1GB (brain, at the wall switch, 5V power bank).
- ESP32-WROOM-32 dev board (CP2102), on the table, USB-charger powered. NO 5V pin.
- SG90 servo — the light switch, on the Pi (already wired and calibrated).
- Elegoo starter-kit parts still in use: 2 red LEDs (eyes), 2 LEDs (smile), 220 ohm
  resistors, photoresistor, 10k resistor, breadboard, jumper wires.
- Sony Bluetooth speaker.
- 5V power bank (Pi), USB charger (ESP32).
- NOT USED: Arduino Uno, USB webcam, NEMA 17 + TMC2209, gear motor + TB6612.

DO NOT DESIGN AROUND NEW PARTS UNLESS I APPROVE IT. There is ONE servo and it
belongs to the light switch (on the Pi).

## Pin map

Raspberry Pi 5 (light switch) — BCM numbering, already wired:
- SG90 signal (orange): GPIO 18 (hardware PWM), physical pin 12
- SG90 power (red): 5V, physical pin 2
- SG90 ground (brown): GND, physical pin 6
- Hardware PWM: `/boot/firmware/config.txt` has
  `dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2` → GPIO 18 = pwmchip0 ch2.

ESP32-WROOM-32 (table unit). Avoid flash pins (6-11) and strapping pins (0,2,5,12,15):
- Left eye LED: GPIO 25 (PWM via LEDC) → 220 ohm → LED → GND
- Right eye LED: GPIO 26 (PWM) → 220 ohm → LED → GND
- Smile (2 LEDs): GPIO 27 (PWM); each LED has its own 220 ohm to GND (parallel)
- Photoresistor: GPIO 34 (ADC1, input only). Divider: 3.3V → photoresistor → GPIO 34
  → 10k → GND. ESP32 ADC reads 0-4095 (ADC1 works with Wi-Fi on; ADC2 does not).
- Power: ESP32 from a USB charger. LEDs run off its 3.3V GPIO (≈6 mA/LED through
  220 ohm). Keep the photoresistor on ADC1.

## Pi <-> ESP32 HTTP contract

ESP32 serves JSON on port 80, reachable at `botfia-robot.local` and by IP. The Pi
polls `GET /status` as the heartbeat (timeout = offline; game continues).

- `GET  /status` → `{name, ip, rssi, uptime_s, light_raw, dark, threshold, eyes, smile}`
- `POST /face/on`  (body `{fade_ms}`) → eyes + smile fade on
- `POST /face/off` (body `{fade_ms}`) → eyes + smile fade off
- `POST /eyes/on` / `POST /eyes/off` / `POST /smile/on` / `POST /smile/off`
- `GET  /light` → `{raw, dark, threshold}`
- `POST /calibrate` (body `{state:"light"|"dark"}`) → store that ambient reading;
  threshold is set midway between the two.

## Folder layout

botfia/
- CLAUDE.md, WIRING.md, README.md
- .env (ANTHROPIC_API_KEY; gitignored), wifi_secrets (gitignored)
- pi/
  - app.py                  web server: PWA + host console + game API
  - game/engine.py          pass-and-play state machine (plain code)
  - game/roles.json         role counts per player count + defaults
  - narration/claude.py     Anthropic SDK narration (secret-safe, pre-generated)
  - narration/fallback.py   large prewritten line bank (style-compliant)
  - narration/prompts.py    the prompt (STYLE RULES verbatim) + PUBLIC-only inputs
  - audio/tts.py            Piper wrapper + audition command + pre-render cache
  - audio/music.py          track selection, crossfade, duck-under-narration
  - hardware/light.py       light switch (reuses the working servo code)
  - hardware/esp32.py       HTTP client for the table unit (eyes/smile/light)
  - hardware/speaker.py     Bluetooth connect/status
  - hardware/motors.py      empty stub for a possible later phase
  - sim/                    laptop simulation (mock light, mock ESP32, laptop audio)
  - static/                 the PWA (index.html, app.js, styles.css, manifest, sw.js)
  - tests/                  logic, win conditions, secret leaks, turn timing, hand-off
  - light_switch.py         (existing) servo driver; light.py builds on it
- esp32-robot/              PlatformIO firmware: eyes, smile, photoresistor, Wi-Fi
- music/                    instrumental tracks + tracks.json
- systemd/                  botfia.service (+ bluetooth) for autostart

## Core code rules

- Game logic is plain code, never Claude. A state machine decides everything.
- Never leak secrets to narration; prove it with tests.
- The game keeps working if Claude/API/internet fails (fallback lines), if the
  ESP32 is offline (no eyes), or if the speaker is absent (text on screen).
- Keep it light for 1GB RAM.
- `.env` and Wi-Fi secrets are gitignored and never committed.

## Deliverables when the software is done

1. WIRING.md: exact ESP32 wiring (each eye LED, the 2 smile LEDs, the
   photoresistor, resistors, exact pins), how to power it. Plain words, step by
   step, for a first-timer.
2. Speaker pairing steps.
3. Setup checklist: API key, Wi-Fi, music import, voice choice, light calibration.
4. Game-night checklist: what to do, in order, to start a game.

## How to work with me

- I'm learning. Explain wiring in plain words before any code that depends on it.
- Keep code simple, organized, plainly commented.
- Don't add parts or features not in this file without asking.
- Keep the pin map, the HTTP contract, and this file up to date.
