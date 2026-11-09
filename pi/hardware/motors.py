"""Motors, intentionally empty.

Botfia v1 does not use any motors. The shuffle drum and head turning are a
possible later phase. This is the clean hook for them: build the gear motor
(TB6612 + encoder) and head stepper (TMC2209) here on the ESP32 when that phase
is approved. Until then, nothing here moves anything.
"""


class Motors:
    """Placeholder so the rest of the code can import a stable name later."""

    available = False

    def __init__(self, *args, **kwargs):
        pass
