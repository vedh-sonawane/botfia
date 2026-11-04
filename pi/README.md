# Botfia — Pi

The Raspberry Pi 5 is the brain and sits at the wall switch, powered by a 5V power
bank. Phase 1 is here: the light switch, driven by the SG90 on the Pi's GPIO.

## Wiring (Pi 5, BCM numbering)

| SG90 wire        | Pi pin                    |
|------------------|---------------------------|
| signal (orange)  | GPIO 18 — physical pin 12 |
| power (red)      | 5V — physical pin 2       |
| ground (brown)   | GND — physical pin 6      |

The switch is a slide dimmer; only its bottom on/off rocker is used. The arm
presses the top of the rocker for ON, the bottom for OFF, then returns to REST so
the switch still works by hand.

## One-time hardware PWM setup on the Pi

1. Enable hardware PWM on GPIO 18. Add this line to `/boot/firmware/config.txt`:

   ```
   dtoverlay=pwm-2chan
   ```

2. Reboot the Pi.

(On the Pi 5, GPIO 18 is hardware PWM channel 2 on chip 2 — already set in
`light_switch.py` as `PWM_CHANNEL` / `PWM_CHIP`. If the arm doesn't move, that
mapping is the first thing to check.)

## Install

```
cd pi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Calibrate

```
python light_calibrate.py
```

Open `http://<pi-ip>:8000` from a phone or laptop on the same network. Drag the
sliders to move the arm live, set ON / OFF / REST, then Save. Angles are written
to `light_config.json` and survive a reboot.

Set the angles so:
- **REST** — arm clear of the switch, nothing pressed.
- **ON** — arm pressed against the top of the bottom rocker.
- **OFF** — arm pressed against the bottom of the rocker.

Leave a few degrees of margin from the 0°/180° hard stops so the servo isn't
grinding against its own end stop while holding.

## Command line

```
python light_switch.py on       # flip on
python light_switch.py off       # flip off
python light_switch.py rest      # park at REST
python light_switch.py status    # print state and angles
python light_switch.py test 20   # flip the light 20 times in a row (Phase 1 test)
```

**Phase 1 is done when `test 20` flips the real light 20 times in a row.**

## Note

Off the Pi (e.g. a laptop), the code runs in SIMULATION mode — it logs moves
instead of driving a servo, so you can develop the UI without hardware.
