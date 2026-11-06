# Botfia

Botfia is a physical robot that hosts the party game Mafia. It sits on the table,
runs the night and day phases, turns the room's light off and on, lights its eyes and
smile, and narrates the game out loud. It is pass-and-play on one shared device —
there are no personal phones, no cameras, and no physical role cards. Botfia assigns
roles itself and the device is passed around the circle.

## Hardware at a glance

- Raspberry Pi 5 (1GB), mounted at the wall switch on a 5V power bank. The brain:
  game engine, web app, Claude narration, text-to-speech, music, and the
  light-switch servo (SG90, hardware PWM).
- ESP32-WROOM-32 on the table, powered by a USB charger. Drives two red eye LEDs,
  two smile LEDs, and a photoresistor that confirms the room went dark. Talks to the
  Pi over Wi-Fi.
- Sony Bluetooth speaker for all audio.
- Shared device: any phone, tablet, or laptop on the Pi's Wi-Fi opens the web app at
  `botfia.local`.

Full wiring for the table unit is in [WIRING.md](WIRING.md).

## Software layout

The complete specification — architecture, pin map, the Pi/ESP32 HTTP contract, the
style rules, and the folder layout — lives in [CLAUDE.md](CLAUDE.md). CLAUDE.md is
the single source of truth; this README is just the short version.

In brief:

- `pi/` — the Pi software: web app (`app.py`), the plain-code game engine
  (`game/engine.py`), narration (`narration/`), audio (`audio/`), hardware clients
  (`hardware/`), the PWA (`static/`), and the simulation (`sim/`).
- `esp32-robot/` — PlatformIO firmware for the table unit (eyes, smile,
  photoresistor, Wi-Fi).
- `music/` — instrumental tracks and `tracks.json`.
- `systemd/` — autostart units.

The game is plain code. Claude only writes narration lines and picks music; it never
decides outcomes, and it never sees who is Mafia, who the doctor saved, or detective
results.

## Running it

On the Pi, everything starts on boot via systemd — plug in the power bank and Botfia
is ready. To run the web app by hand during development:

```
python -m pi.app
```

Then open `botfia.local` from a device on the same Wi-Fi.

## Simulation mode (on a laptop, no hardware)

A full simulation runs on a laptop with no hardware — the light, the ESP32, and the
audio are mocked or sent to the laptop — so you can play a whole game while testing:

```
python -m pi.sim
```

## Guides

- [WIRING.md](WIRING.md) — wire the ESP32 table unit, step by step.
- [docs/SETUP.md](docs/SETUP.md) — one-time setup: API key, Wi-Fi, music, voice,
  light calibration.
- [docs/SPEAKER.md](docs/SPEAKER.md) — pair the Sony speaker to the Pi.
- [docs/GAME_NIGHT.md](docs/GAME_NIGHT.md) — run a game, in order.
