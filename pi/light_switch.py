"""Botfia light switch — drives the SG90 on the Pi to flip the wall switch.

Wiring (Raspberry Pi 5, BCM numbering):
  SG90 signal (orange) -> GPIO 18 (hardware PWM), physical pin 12
  SG90 power  (red)    -> 5V, physical pin 2
  SG90 ground (brown)  -> GND, physical pin 6

The wall switch is a slide dimmer; we only use its bottom on/off rocker. The arm
presses the top of the rocker for ON, the bottom for OFF, then returns to REST so
the switch still works by hand. The ON/OFF/REST angles are saved to
light_config.json on the Pi so they survive a reboot.

Hardware PWM setup on the Pi (once):
  1. Add to /boot/firmware/config.txt:   dtoverlay=pwm-2chan
  2. Reboot.
  On the Pi 5, GPIO 18 is hardware PWM channel 2 on chip 2 (see PWM_CHANNEL/PWM_CHIP).

If the rpi_hardware_pwm library or the PWM hardware is not available (e.g. running
on a laptop), this module falls back to SIMULATION mode: it logs moves instead of
driving a servo, so the calibration page and CLI still work for development.
"""

import json
import sys
import time
from pathlib import Path

# ---- Servo timing ----
SERVO_HZ = 50
MIN_US = 500             # pulse width at 0 degrees
MAX_US = 2500            # pulse width at 180 degrees
PERIOD_US = 1_000_000 / SERVO_HZ   # 20000 us at 50 Hz

PRESS_DWELL_S = 0.5      # hold the arm against the rocker this long
SETTLE_S = 0.3          # let the arm settle after returning to REST

# ---- Pi 5 hardware PWM mapping for GPIO 18 ----
PWM_CHANNEL = 2
PWM_CHIP = 2

CONFIG_PATH = Path(__file__).with_name("light_config.json")
DEFAULT_ANGLES = {"on": 60, "off": 120, "rest": 90}

try:
    from rpi_hardware_pwm import HardwarePWM
except Exception:
    HardwarePWM = None


class LightSwitch:
    def __init__(self):
        self.angles = self._load_angles()
        self.state = "unknown"
        self._pwm = None

        if HardwarePWM is not None:
            try:
                self._pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=SERVO_HZ, chip=PWM_CHIP)
                self._pwm.start(self._duty(self.angles["rest"]))
            except Exception as e:
                print(f"[light] hardware PWM unavailable ({e}); SIMULATION mode.")
                self._pwm = None

        if self._pwm is None:
            print("[light] SIMULATION mode — no real servo movement.")

    # ---- angle helpers ----
    def _clamp(self, angle):
        return max(0, min(180, int(angle)))

    def _duty(self, angle):
        """Convert an angle (0-180) to a duty cycle percentage for the servo."""
        us = MIN_US + (MAX_US - MIN_US) * self._clamp(angle) / 180
        return us / PERIOD_US * 100

    def move_to(self, angle):
        """Move the arm to an angle and leave it there (used for live calibration)."""
        angle = self._clamp(angle)
        if self._pwm:
            self._pwm.change_duty_cycle(self._duty(angle))
        else:
            print(f"[light:sim] move to {angle} deg")

    # ---- flips ----
    def _flip(self, press_angle, new_state):
        self.move_to(press_angle)
        time.sleep(PRESS_DWELL_S)
        self.move_to(self.angles["rest"])   # return to REST so the switch works by hand
        time.sleep(SETTLE_S)
        self.state = new_state

    def on(self):
        self._flip(self.angles["on"], "on")

    def off(self):
        self._flip(self.angles["off"], "off")

    def rest(self):
        self.move_to(self.angles["rest"])

    # ---- calibration ----
    def set_angles(self, on=None, off=None, rest=None):
        if on is not None:
            self.angles["on"] = self._clamp(on)
        if off is not None:
            self.angles["off"] = self._clamp(off)
        if rest is not None:
            self.angles["rest"] = self._clamp(rest)
        self._save_angles()
        self.rest()                          # park at the new rest position

    def status(self):
        return {"state": self.state, "angles": self.angles, "simulated": self._pwm is None}

    def _load_angles(self):
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
                return {k: int(data.get(k, DEFAULT_ANGLES[k])) for k in DEFAULT_ANGLES}
            except Exception:
                pass
        return dict(DEFAULT_ANGLES)

    def _save_angles(self):
        CONFIG_PATH.write_text(json.dumps(self.angles, indent=2))

    def close(self):
        if self._pwm:
            self._pwm.stop()


# ---- CLI: python light_switch.py [on|off|rest|status|test [N]] ----
def _main():
    sw = LightSwitch()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if cmd == "on":
            sw.on()
        elif cmd == "off":
            sw.off()
        elif cmd == "rest":
            sw.rest()
        elif cmd == "test":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            state = "on"   # assume the light starts on; alternate from there
            for i in range(n):
                if state == "on":
                    print(f"flip {i + 1}/{n}: off")
                    sw.off()
                    state = "off"
                else:
                    print(f"flip {i + 1}/{n}: on")
                    sw.on()
                    state = "on"
                time.sleep(0.8)
            print("done")
        else:
            print(json.dumps(sw.status(), indent=2))
    finally:
        sw.close()


if __name__ == "__main__":
    _main()
