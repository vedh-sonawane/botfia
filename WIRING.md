# Wiring the ESP32 table unit

This is the table unit: an ESP32 with two red eye LEDs, two smile LEDs, and one
photoresistor that tells the Pi whether the room is dark. The Pi talks to it over
Wi-Fi. The light switch itself is on the Pi, not here, so there is no servo on this
board.

Follow the steps in order. Take your time. If something does not light up, the
"Test it" section at the bottom tells you how to check each part.

## Parts you need

- ESP32-WROOM-32 dev board
- Breadboard
- 2 red LEDs (the eyes)
- 2 LEDs (the smile)
- 4 resistors, 220 ohm (one per LED)
- 1 photoresistor (light sensor)
- 1 resistor, 10k ohm (for the light sensor)
- Jumper wires
- A USB cable and a USB charger (to power the ESP32)

All of these are already in the kit. You do not need anything else.

## LED basics, read this first

An LED only works one way round. Look at the two legs:

- The long leg is the plus side (the anode, +).
- The short leg is the minus side (the cathode, -). The flat notch on the rim of
  the LED is also the minus side.

Two rules, every time:

- Current flows in the long leg and out the short leg. Long leg toward the ESP32
  pin, short leg toward ground.
- Every LED gets its own 220 ohm resistor in series. Never connect an LED straight
  to a pin with no resistor, without the resistor the LED draws too much current
  and can burn out the pin or the LED.

The resistor can go on either leg; it just has to be in the line between the pin
and ground. In the steps below we put the resistor on the long-leg (signal) side.

## How this board is powered

The ESP32 runs from a USB charger. Plug the USB cable into the ESP32 and into the
charger. That is the only power this unit needs.

This board has NO 5V pin, so the LEDs run off its 3.3V GPIO pins directly. Through a
220 ohm resistor each LED draws about 6 mA, which the GPIO pins handle fine.

One wiring detail that matters: the light sensor must stay on GPIO 34. GPIO 34 is an
ADC1 pin. The ESP32's other analog pins (ADC2) stop reading once Wi-Fi is on, and
this board is always on Wi-Fi, so the sensor would read garbage anywhere else.

## Ground rail

Pick one long rail on the edge of the breadboard to be your ground rail. Run one
jumper from any ESP32 pin marked GND to that rail. Everything that goes "to ground"
in the steps below connects to this one rail. Get this wire in first.

## Step by step

### Left eye LED, GPIO 25

1. Put the LED on the breadboard so its two legs are in different rows.
2. Put a 220 ohm resistor from the LED's long leg (+) across to an empty row.
3. Run a jumper from ESP32 GPIO 25 to that resistor row.
4. Run a jumper from the LED's short leg (-) to the ground rail.

Path: GPIO 25 -> 220 ohm -> LED long leg -> LED short leg -> GND rail.

### Right eye LED, GPIO 26

Same as the left eye, on GPIO 26.

1. Put the second red LED on the breadboard.
2. 220 ohm resistor from its long leg (+) to an empty row.
3. Jumper from GPIO 26 to that resistor row.
4. Jumper from the LED's short leg (-) to the ground rail.

Path: GPIO 26 -> 220 ohm -> LED long leg -> LED short leg -> GND rail.

### Smile, two LEDs, both on GPIO 27 (in parallel)

The two smile LEDs turn on and off together, so they share one pin. But each LED
still needs its own 220 ohm resistor and its own wire to ground. Do not try to make two LEDs share a single resistor.

For each of the two smile LEDs:

1. Put the LED on the breadboard.
2. 220 ohm resistor from its long leg (+) to an empty row.
3. Jumper from GPIO 27 to that resistor row. (Both smile LEDs' resistor rows connect
   back to GPIO 27, that is what "in parallel" means here.)
4. Jumper from the LED's short leg (-) to the ground rail.

Path (each LED): GPIO 27 -> 220 ohm -> LED long leg -> LED short leg -> GND rail.

So GPIO 27 fans out to two 220 ohm resistors, one per smile LED, and both LEDs
return to the ground rail.

### Photoresistor (light sensor), GPIO 34

The photoresistor changes its resistance with light. We put it in a voltage divider
with the 10k resistor so the ESP32 can read a changing voltage on GPIO 34.

A photoresistor has no plus or minus, either leg can go either way.

1. Run a jumper from the ESP32 3V3 pin to one leg of the photoresistor.
2. The other leg of the photoresistor goes to a junction row. Call this the junction.
3. From the junction, run a jumper to GPIO 34.
4. From the junction, put the 10k resistor down to the ground rail.

Path: 3V3 -> photoresistor -> junction -> GPIO 34, and junction -> 10k -> GND.

What the reading means: in bright light the photoresistor's resistance drops, so
more voltage reaches the junction and GPIO 34 reads higher. In the dark its
resistance rises, so the junction voltage drops and GPIO 34 reads lower. So
**brighter light = higher reading, darker room = lower reading.** The ESP32 reads
this as a number from 0 to 4095. The "dark" threshold is set during calibration (see
docs/SETUP.md), so you do not need to pick a number by hand.

## Breadboard layout (rough)

```
                 ESP32-WROOM-32
          +-----------------------------+
          |                             |
   GPIO25 |o---[220]---(>|)----+        |   left eye LED  (> = long leg)
   GPIO26 |o---[220]---(>|)----+        |   right eye LED
   GPIO27 |o---[220]---(>|)----+        |   smile LED 1
          |  \-[220]---(>|)----+        |   smile LED 2  (same pin, own resistor)
          |                    |        |
      3V3 |o---[photoresistor]-+--GPIO34|   sensor junction -> GPIO34
          |                    |        |
          |                  [10k]      |
          |                    |        |
      GND |o-------------------+--------|---> ground rail
          +-----------------------------+

   ground rail: ========================================  (all - legs land here)
```

Everything with a `-` (every LED short leg, the 10k, and the junction's lower leg)
lands on the one ground rail that connects back to the ESP32 GND pin.

## Test it

1. Flash the firmware in `esp32-robot/` to the board (PlatformIO upload).
2. Power the ESP32 from the USB charger and let it join Wi-Fi. It should appear at
   `botfia-robot.local`.
3. Eyes: send `POST /eyes/on`, confirm both red eye LEDs light, then `POST /eyes/off`.
4. Smile: send `POST /smile/on`, confirm both smile LEDs light, then `POST /smile/off`.
   (Or use the light test in the host controls on the shared device, which drives the
   same endpoints.)
5. Both together: `POST /face/on` fades eyes and smile on; `POST /face/off` fades
   them off.
6. Light sensor: open `GET /light` and read the `raw` number. Cover the photoresistor
   with your hand, `raw` should drop and `dark` should flip to true. Uncover it and
   `raw` should climb back up.

If an LED does not light, check its direction first (long leg toward the resistor and
pin, short leg toward ground), then check the resistor and the ground wire. If the
light reading never changes, check the 3V3 wire and that the sensor is on GPIO 34.
