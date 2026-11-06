"""The wall light, controlled by the Pi's servo.

Thin wrapper over the already-working light_switch module (hardware PWM on the
Pi, calibrated ON/OFF/REST angles). Off the Pi, light_switch runs in simulation
and just logs, so this works on a laptop too.
"""

from ..light_switch import LightSwitch


class Light:
    def __init__(self):
        self._sw = LightSwitch()

    def on(self):
        self._sw.on()

    def off(self):
        self._sw.off()

    def rest(self):
        self._sw.rest()

    def status(self):
        return self._sw.status()

    def close(self):
        self._sw.close()
