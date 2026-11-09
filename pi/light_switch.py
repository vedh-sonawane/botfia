"""Botfia light switch, drives the SG90 on the Pi to flip the wall switch.

Wiring (Raspberry Pi 5, BCM numbering):
  SG90 signal (orange) -> GPIO 18 (hardware PWM), physical pin 12
  SG90 power  (red)    -> 5V, physical pin 2
  SG90 ground (brown)  -> GND, physical pin 6

The wall switch is a slide dimmer; we only use its bottom on/off rocker. The arm
presses the top of the rocker for ON, the bottom for OFF, then returns to REST so
the switch still works by hand. The ON/OFF/REST angles are saved to
light_config.json on the Pi so they survive a reboot.

Hardware PWM is driven straight through the kernel's sysfs interface, so there is
no extra Python dependency. The one-time Pi setup (see README):
  /boot/firmware/config.txt:  dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
This maps GPIO 18 to PWM0_CHAN2, which shows up as pwmchip0 / channel 2. The
member of the 'gpio' group can drive it without root (a udev rule hands the
exported channel to that group a moment after export, so we wait for it).

Off the Pi (e.g. a laptop), there is no /sys/class/pwm, so this falls back to
SIMULATION mode: it logs moves instead of driving a servo.
"""

import json
import os
import sys
import time
from pathlib import Path

# ---- Servo timing ----
PERIOD_NS = 20_000_000       # 20 ms period = 50 Hz
MIN_US = 400                 # pulse width at 0 degrees (widened for more travel)
MAX_US = 3400                # pulse width at 180 degrees (wide enough for the arm to reach the ON throw)

PRESS_DWELL_S = 0.5          # hold the arm against the rocker this long
SETTLE_S = 0.3              # let the arm settle after returning to REST
# Glide: instead of snapping to a target, step toward it so the arm moves
# smoothly. Speed is GLIDE_STEP_DEG / GLIDE_STEP_DELAY_S (deg per second).
GLIDE_STEP_DEG = 2
GLIDE_STEP_DELAY_S = 0.02    # ~100 deg/s. Larger = slower.

# ---- Hardware PWM location (verified on this Pi 5) ----
PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_CHANNEL = 2              # GPIO 18 = PWM0_CHAN2

CONFIG_PATH = Path(__file__).with_name("light_config.json")
DEFAULT_ANGLES = {"on": 60, "off": 120, "rest": 90}


class _SysfsPWM:
    """Thin wrapper over /sys/class/pwm for one channel. Simulates if absent."""

    def __init__(self):
        self.chan = f"{PWM_CHIP}/pwm{PWM_CHANNEL}"
        self.sim = not os.path.isdir(PWM_CHIP)
        if self.sim:
            print("[light] no /sys/class/pwm, SIMULATION mode (no servo movement).")
            return
        self._export()
        self._write("enable", 0)         # configure while disabled
        self._write("period", PERIOD_NS)

    def _export(self):
        if not os.path.isdir(self.chan):
            try:
                with open(f"{PWM_CHIP}/export", "w") as f:
                    f.write(str(PWM_CHANNEL))
            except OSError:
                pass                      # already exported is fine
        # The udev rule hands the new channel to the 'gpio' group a moment
        # after export; wait until the enable file is writable.
        for _ in range(30):
            if os.path.isdir(self.chan) and os.access(f"{self.chan}/enable", os.W_OK):
                return
            time.sleep(0.1)

    def _write(self, name, value):
        if self.sim:
            return
        with open(f"{self.chan}/{name}", "w") as f:
            f.write(str(value))

    def set_duty_ns(self, duty_ns):
        if self.sim:
            print(f"[light:sim] duty {duty_ns} ns")
            return
        self._write("duty_cycle", int(duty_ns))
        self._write("enable", 1)

    def disable(self):
        """Stop driving the servo so it relaxes (no holding current, no stall)."""
        if self.sim:
            print("[light:sim] relax")
            return
        try:
            self._write("enable", 0)
        except OSError:
            pass

    def close(self):
        self.disable()


class LightSwitch:
    def __init__(self):
        self.angles = self._load_angles()
        self.state = "unknown"
        self._cur = self.angles["rest"]   # last angle commanded (for gliding)
        self._pwm = _SysfsPWM()
        self.rest()                       # park at REST so the switch works by hand

    # ---- angle helpers ----
    def _clamp(self, angle):
        return max(0, min(180, int(angle)))

    def _duty_ns(self, angle):
        pulse_us = MIN_US + (MAX_US - MIN_US) * self._clamp(angle) / 180
        return int(pulse_us * 1000)

    def move_to(self, angle):
        """Jump the arm to an angle (instant; used for live calibration sliders)."""
        angle = self._clamp(angle)
        self._pwm.set_duty_ns(self._duty_ns(angle))
        self._cur = angle

    def aim(self, which, angle):
        """Live calibration: record this angle (in memory) AND move the arm there,
        so the slider, the Test buttons, and Save all use the same value."""
        angle = self._clamp(angle)
        if which in self.angles:
            self.angles[which] = angle
        self.move_to(angle)

    def _glide(self, target):
        """Move smoothly from the current angle to target in small steps."""
        target = self._clamp(target)
        step = GLIDE_STEP_DEG if target >= self._cur else -GLIDE_STEP_DEG
        a = self._cur
        while a != target:
            a += step
            if (step > 0 and a > target) or (step < 0 and a < target):
                a = target
            self.move_to(a)
            time.sleep(GLIDE_STEP_DELAY_S)

    # ---- flips ----
    # REST is the flat/center position, between ON and OFF. A flip glides out to
    # one side, holds, then glides straight back to flat. Because it always
    # returns to flat (never continues to the other side), the arm never sweeps
    # across and knocks the switch the other way.
    def _flip(self, press_angle, new_state):
        self._glide(press_angle)            # out to the press side
        time.sleep(PRESS_DWELL_S)
        self._glide(self.angles["rest"])    # straight back to flat
        time.sleep(SETTLE_S)
        self._pwm.disable()                 # relax at flat
        self.state = new_state

    def on(self):
        self._flip(self.angles["on"], "on")

    def off(self):
        self._flip(self.angles["off"], "off")

    def rest(self):
        self._glide(self.angles["rest"])
        time.sleep(SETTLE_S)
        self._pwm.disable()                # relax at REST (no holding current)

    # ---- calibration ----
    def set_angles(self, on=None, off=None, rest=None):
        if on is not None:
            self.angles["on"] = self._clamp(on)
        if off is not None:
            self.angles["off"] = self._clamp(off)
        if rest is not None:
            self.angles["rest"] = self._clamp(rest)
        self._save_angles()
        self.rest()                        # park at the new rest position

    def status(self):
        return {"state": self.state, "angles": self.angles, "simulated": self._pwm.sim}

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
        self._pwm.close()


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
