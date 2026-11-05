# Botfia

Botfia is a physical robot that hosts the party game Mafia. It sits on the table, shuffles the role cards, runs the night and day phases, turns the room's light off and on, and narrates the game out loud. Players use their phones to confirm their role, make night moves, and vote.

## STYLE RULES — READ FIRST, APPLY TO EVERYTHING

NOTHING IN THIS PROJECT SHOULD BE CRINGE. THIS APPLIES TO NARRATION, CLAUDE PROMPTS, THE PHONE UI, MUSIC, NAMES, CODE COMMENTS, AND DOCS.

- NARRATION IS SHORT, CALM, DRY, AND SERIOUS. A quiet, confident narrator. Understated is creepier than dramatic.
- NO JOKES, NO PUNS, NO CATCHPHRASES, NO EVIL LAUGHS, NO "MWAHAHA", NO EMOJIS, NO EXCLAMATION MARKS.
- NO CLICHES: no "darkness descends", "fate", "sinister", "doom", "the night is young", "a chill in the air".
- SAY THE MINIMUM. Right tone: "The town is asleep. Close your eyes." / "Morning. Daniel did not wake up."
- PHONE UI IS MINIMAL, DARK, AND CLEAN. Plain fonts. No emojis, no neon, no spooky fonts, no skulls, no blood, no glow effects, no confetti.
- MUSIC IS INSTRUMENTAL ONLY AND QUIET. NO SOUND EFFECTS: no thunder, wolves, screams, or creaking doors.
- NAMES AND TEXT ARE PLAIN AND PROFESSIONAL. No hype words, no "MafiaMaster3000"-style names.
- IF YOU ARE UNSURE WHETHER SOMETHING IS CRINGE, IT IS. LEAVE IT OUT.

## How a game works

1. Setup: players join a web page hosted by the Pi on the local Wi-Fi, enter their name, and pick their seat number. The host sets the number of players and roles.
2. Shuffle: the role cards go into a drum. The drum spins (gear motor), then stops with its opening facing up. Each player reaches in and draws one card without looking.
3. Roles: each player privately selects the role on their card in their phone page.
4. Night: Botfia announces the night. The Pi flips the wall light off with its own servo. The light sensor on the ESP32 (on the table) confirms the room is dark over Wi-Fi (if not, retry the flip). Then the red LED eyes and smile turn on and quiet music starts.
   - EVERY player taps something on their phone every night, so nobody can tell who has a real role. Mafia choose a victim, the doctor chooses someone to save, the detective chooses someone to check (the result appears privately on the detective's phone only), and villagers tap a neutral button.
5. Day: the light turns on, the eyes and smile turn off, and Botfia announces what happened in a short line written by Claude. Then a discussion timer runs, players vote on their phones, and the eliminated player is announced. Check for a win.
6. End: announce the winning side and reveal all roles.

Roles for v1: Mafia, Doctor, Detective, Villager. Role counts per player count live in a config file.

## Architecture

- Raspberry Pi 5 (1GB RAM): the brain. Mounted at the wall switch, powered by a 5V power bank. Runs the game engine, the phone web server, Claude API calls, text-to-speech, and music (to the Sony speaker over Bluetooth). Also drives the light-switch SG90 servo directly from its GPIO (hardware PWM), since the Pi sits right at the switch.
- ESP32-WROOM-32: on the table (the robot body). Drives the eye LEDs, smile LEDs, light sensor, shuffle drum motor (TB6612 + encoder), and head stepper (TMC2209). Receives commands from the Pi over Wi-Fi.
- Arduino Uno: NOT used in this design. Its jobs moved to the ESP32.
- Sony speaker: all audio. Connect over Bluetooth (the Pi 5 has no headphone jack).
- USB webcam: deferred to a later phase. The Pi now sits at the switch, not on the robot, so how the camera connects for head turning and reading card backs will be decided then.

Communication:
- Pi to ESP32: HTTP with simple JSON endpoints on the local network.
- The light-switch servo is local to the Pi (direct GPIO), so it needs no network.

## Hardware inventory — ONLY THESE PARTS EXIST

- Raspberry Pi 5 1GB
- ESP32-WROOM-32 dev board (CP2102 USB chip)
- Arduino Uno R3 (Elegoo Most Complete Starter Kit: LEDs, resistors, photoresistor, buttons, small 28BYJ-48 stepper with ULN2003, LCD, etc.) — NOT used in the current design, but the kit's LEDs, resistors, and photoresistor are still used (wired to the ESP32).
- NEMA 17 stepper (1.5A, 12V) + TMC2209 driver
- 12V encoder gear motor (100 RPM) + TB6612FNG driver
- ONE SG90 servo
- USB webcam
- Sony Bluetooth speaker
- 30V 5A bench power supply
- Old laptops, old mice, wires

THERE IS ONLY ONE SERVO, AND IT BELONGS TO THE LIGHT SWITCH (driven by the Pi). DO NOT USE SERVOS ANYWHERE ELSE. THERE IS NO ESP32-CAM. DO NOT DESIGN AROUND NEW PARTS UNLESS I APPROVE IT.

## Core rules for the code

- GAME LOGIC IS PLAIN CODE, NOT CLAUDE. A state machine decides phases, kills, saves, votes, and wins. Claude only writes narration lines and picks music. Claude never decides outcomes.
- NEVER LEAK SECRETS. Public narration, and the prompts used to write it, must never contain who is Mafia, who the doctor saved, or detective results. Only pass Claude public information. Write a test that checks this.
- The game must keep working if the Claude API or internet fails. Fall back to plain prewritten lines that follow the style rules.
- The game must keep working if the ESP32 (robot hardware) is unreachable over Wi-Fi. Log it and continue. The light switch is local to the Pi, so it does not depend on the network.
- Keep everything light enough for 1GB of RAM. No local language models, no heavy vision models.
- The API key lives in a .env file (ANTHROPIC_API_KEY) and is never committed. Add .env and Wi-Fi secrets to .gitignore.
- The Claude model is set in config. Default: claude-haiku-5-5 (fast and cheap for short lines).
- Call Claude once per narration moment, never in a loop.

## Voice

- Use a natural-sounding text-to-speech voice. Start with Piper (local, free) and keep the TTS code swappable.
- The narration prompt must include the STYLE RULES section word for word. Maximum two sentences per line.
- Lower the music volume while Botfia is speaking.

## Music

- A music/ folder of royalty-free instrumental tracks, plus music/tracks.json listing each track's id, file, and mood (calm, uneasy, tense, final).
- Claude picks a track id from that list based on the game state (phase, players left). The code checks that the id exists before playing.
- Low volume, crossfade between tracks.

## Hardware notes

- Motors run from the bench power supply at 12V. The Pi runs from a 5V power bank (USB-C).
- The ESP32 GND, the motor driver GNDs, and the power supply GND must all be connected together.
- TMC2209: set the motor current with the Vref screw for a 1.5A motor. Never unplug the motor while powered.
- TB6612FNG handles about 1.2A continuous. Keep the drum light.
- Photoresistor: voltage divider with a 10k resistor into an ESP32 ADC pin. Use an ADC1 pin (GPIO 32-39); ADC2 does not work while Wi-Fi is on. ESP32 ADC reads 0-3.3V.
- Every LED gets a 220 ohm resistor.
- The SG90 is powered from the Pi's 5V (header pin 2, fed by the power bank), ground on pin 6, signal on GPIO 18. An SG90 can briefly pull a few hundred mA; if the Pi browns out, power the servo from a separate 5V source and share ground with the Pi.

## Pin map (suggested — update this when things are actually wired)

Raspberry Pi 5 (light switch) — BCM GPIO numbering:
- SG90 signal (orange): GPIO 18 (hardware PWM), physical pin 12
- SG90 power (red): 5V, physical pin 2
- SG90 ground (brown): GND, physical pin 6

ESP32-WROOM-32 (robot hardware). Avoid the flash pins (6-11) and strapping pins (0, 2, 5, 12, 15) for these:
- Red eye LEDs: GPIO 25, GPIO 26 (PWM via LEDC, for fading)
- Smile LEDs: GPIO 27 (PWM)
- Photoresistor (light sensor): GPIO 34 (ADC1, input only)
- TB6612 (drum motor): PWMA GPIO 14, AIN1 GPIO 16, AIN2 GPIO 17, STBY GPIO 4
- Encoder: A GPIO 32, B GPIO 33
- TMC2209 (head stepper): STEP GPIO 22, DIR GPIO 23, EN GPIO 21

## Folder layout

botfia/
- CLAUDE.md
- pi/ (Python: game server, phone web app, narration, music, and the light-switch servo control)
- esp32-robot/ (ESP32 firmware: eyes, smile, light sensor, drum, head — PlatformIO)
- music/

## Build phases — DO ONE AT A TIME. EACH PHASE ENDS WITH A TEST I RUN.

1. Light switch on the Pi (SG90 on GPIO 18, hardware PWM). **DONE.** A Python module (`pi/light_switch.py`) flips the wall switch via sysfs hardware PWM; ON/OFF/REST angles save to `pi/light_config.json` and survive reboot. Calibration web page (`pi/light_calibrate.py`) with live sliders. REST is the flat/center position; each flip glides out to one side and straight back to flat so the arm never sweeps across and double-triggers. Verified flipping the real light 10+ times in a row.
   - Hardware PWM: `/boot/firmware/config.txt` has `dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2` → GPIO 18 = `pwmchip0` channel 2. Pulse range 400-2600us.
   - Power: the servo runs off the Pi's 5V (power bank). The power bank is marginal and occasionally brown-out-reboots the Pi on servo spikes. For long sessions, power the servo from a separate 5V source (shared ground). The code relaxes the servo at REST to minimize current.
2. Game engine + phone web app on the Pi, no hardware. **BUILT — ready for your test.** `pi/game/engine.py` is the plain-code state machine (lobby -> reveal -> night -> day -> vote -> end); role counts in `pi/game/roles.json`. `pi/app.py` serves the phone UI (`/`) and host console (`/host`) on port 5000; phones poll for state. Secret-safety test in `pi/tests/test_game.py` (public_state never leaks roles/actions). Done when a full game is playable on phones.
3. Voice, Claude narration, and music.
4. ESP32 over Wi-Fi: eyes, smile, light sensor, and the full night flow (Pi flips the light off, the ESP32 light sensor confirms dark, retry if not, then eyes on).
5. Shuffle drum (gear motor with encoder on the ESP32, stops with the opening facing up).
6. Head turning toward the player being addressed (NEMA 17 on the ESP32 + seat map).
7. Optional: USB camera reads patterns printed on card backs, so players no longer need to select their role. Decide how the camera connects given the Pi's location at the switch.

## How to work with me

- I'm learning. Explain wiring in plain words, and tell me exactly what to plug where BEFORE writing code that depends on it.
- Do not skip ahead to later phases.
- Keep code simple, organized, and plainly commented.
- Do not add features that are not in this file without asking me first.
- Keep the pin map and phase status in this file up to date.