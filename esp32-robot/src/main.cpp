// Botfia table unit, ESP32-WROOM-32.
//
// Sits on the table and drives the robot's face: two red eye LEDs and the smile
// LEDs, all on LEDC PWM so they fade smoothly. A photoresistor on ADC1 lets the
// Pi confirm the room went dark before the eyes come on.
//
// The Pi is the brain. This board only takes HTTP commands and reports the light
// level. It joins Wi-Fi in station mode, announces itself at botfia-robot.local,
// reconnects on its own if the link drops, and serves JSON on port 80.

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>

#include "secrets.h"

// ---- Pins (from CLAUDE.md). No motors or servo on this board. ----
// Avoid the flash pins (6-11) and strapping pins (0, 2, 5, 12, 15).
static const int PIN_EYE_LEFT   = 25;  // left red eye LED  -> 220 ohm -> LED -> GND
static const int PIN_EYE_RIGHT  = 26;  // right red eye LED -> 220 ohm -> LED -> GND
static const int PIN_SMILE      = 27;  // two smile LEDs, each via its own 220 ohm
static const int PIN_LIGHT_SENS = 34;  // photoresistor on ADC1 (input only)

// ---- LEDC (PWM) setup for the LEDs. ----
// 12-bit duty (0-4095) at 5 kHz. The ESP32 core (v3, used by recent
// espressif32 platforms) auto-assigns a channel per pin via ledcAttach.
static const int LEDC_FREQ_HZ  = 5000;
static const int LEDC_BITS     = 12;
static const int DUTY_MAX      = (1 << LEDC_BITS) - 1;  // 4095 = full brightness

// ---- Light sensor polarity ----
// Divider: 3.3V -> photoresistor -> GPIO34 -> 10k -> GND.
// A photoresistor's resistance DROPS as light increases, so in bright light more
// voltage reaches GPIO34 and analogRead() is HIGHER. In the dark the reading is
// LOWER. So: dark = (light_raw < threshold).
static const int ADC_MAX = 4095;

// Default threshold until the room is calibrated. Midway is a safe placeholder;
// the real value comes from POST /calibrate and is stored in NVS.
static const int DEFAULT_THRESHOLD = ADC_MAX / 2;

// ---- Persisted calibration (NVS via Preferences) ----
Preferences prefs;
int lightReading = -1;       // ADC reading taken with the room light ON
int darkReading  = -1;       // ADC reading taken with the room light OFF
int threshold    = DEFAULT_THRESHOLD;

// ---- Face state (what we last commanded, for /status) ----
bool eyesOn  = false;
bool smileOn = false;

WebServer server(80);

// ---------------------------------------------------------------------------
// Light sensor
// ---------------------------------------------------------------------------

// Average a few reads to steady the value.
int readLight() {
  long sum = 0;
  const int n = 8;
  for (int i = 0; i < n; i++) {
    sum += analogRead(PIN_LIGHT_SENS);
    delay(2);
  }
  return (int)(sum / n);
}

bool isDark(int raw) {
  // Lower reading = less light = dark. See the polarity note above.
  return raw < threshold;
}

// Recompute the threshold as the midpoint of the two calibrated readings.
void updateThreshold() {
  if (lightReading >= 0 && darkReading >= 0) {
    threshold = (lightReading + darkReading) / 2;
  }
}

void loadCalibration() {
  prefs.begin("botfia", true);  // read-only
  lightReading = prefs.getInt("light", -1);
  darkReading  = prefs.getInt("dark", -1);
  threshold    = prefs.getInt("thresh", DEFAULT_THRESHOLD);
  prefs.end();
}

void saveCalibration() {
  prefs.begin("botfia", false);  // read-write
  prefs.putInt("light", lightReading);
  prefs.putInt("dark", darkReading);
  prefs.putInt("thresh", threshold);
  prefs.end();
}

// ---------------------------------------------------------------------------
// LED fading
// ---------------------------------------------------------------------------

// Smoothly ramp a pin's duty from its current level to a target over fade_ms.
void fadePin(int pin, int fromDuty, int toDuty, int fade_ms) {
  if (fade_ms <= 0) {
    ledcWrite(pin, toDuty);
    return;
  }
  const int steps = 60;
  const int stepDelay = fade_ms / steps;
  for (int i = 1; i <= steps; i++) {
    int duty = fromDuty + (long)(toDuty - fromDuty) * i / steps;
    ledcWrite(pin, duty);
    delay(stepDelay > 0 ? stepDelay : 1);
  }
  ledcWrite(pin, toDuty);
}

void fadeEyes(bool on, int fade_ms) {
  int target = on ? DUTY_MAX : 0;
  int start  = eyesOn ? DUTY_MAX : 0;
  // Both eyes move together.
  const int steps = 60;
  const int stepDelay = (fade_ms > 0) ? fade_ms / steps : 0;
  for (int i = 1; i <= steps; i++) {
    int duty = start + (long)(target - start) * i / steps;
    ledcWrite(PIN_EYE_LEFT, duty);
    ledcWrite(PIN_EYE_RIGHT, duty);
    if (stepDelay > 0) delay(stepDelay);
  }
  ledcWrite(PIN_EYE_LEFT, target);
  ledcWrite(PIN_EYE_RIGHT, target);
  eyesOn = on;
}

void fadeSmile(bool on, int fade_ms) {
  int target = on ? DUTY_MAX : 0;
  int start  = smileOn ? DUTY_MAX : 0;
  fadePin(PIN_SMILE, start, target, fade_ms);
  smileOn = on;
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

// Read fade_ms from the optional JSON body. Default 600 ms. Kept deliberately
// simple: we scan for the number after "fade_ms" rather than pulling in a JSON
// library, since the body is tiny and fixed-shape.
int fadeMsFromBody() {
  int fade_ms = 600;
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    int key = body.indexOf("fade_ms");
    if (key >= 0) {
      int colon = body.indexOf(':', key);
      if (colon >= 0) {
        int v = body.substring(colon + 1).toInt();
        if (v >= 0) fade_ms = v;
      }
    }
  }
  return fade_ms;
}

void sendLightJson() {
  int raw = readLight();
  String s = "{";
  s += "\"raw\":" + String(raw) + ",";
  s += "\"dark\":" + String(isDark(raw) ? "true" : "false") + ",";
  s += "\"threshold\":" + String(threshold);
  s += "}";
  server.send(200, "application/json", s);
}

// ---------------------------------------------------------------------------
// Endpoint handlers
// ---------------------------------------------------------------------------

void handleStatus() {
  int raw = readLight();
  String s = "{";
  s += "\"name\":\"botfia-robot\",";
  s += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  s += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  s += "\"uptime_s\":" + String(millis() / 1000) + ",";
  s += "\"light_raw\":" + String(raw) + ",";
  s += "\"dark\":" + String(isDark(raw) ? "true" : "false") + ",";
  s += "\"threshold\":" + String(threshold) + ",";
  s += "\"eyes\":" + String(eyesOn ? "true" : "false") + ",";
  s += "\"smile\":" + String(smileOn ? "true" : "false");
  s += "}";
  server.send(200, "application/json", s);
}

void handleFaceOn() {
  int fade_ms = fadeMsFromBody();
  fadeEyes(true, fade_ms);
  fadeSmile(true, fade_ms);
  handleStatus();
}

void handleFaceOff() {
  int fade_ms = fadeMsFromBody();
  fadeEyes(false, fade_ms);
  fadeSmile(false, fade_ms);
  handleStatus();
}

void handleEyesOn()   { fadeEyes(true,  fadeMsFromBody());  handleStatus(); }
void handleEyesOff()  { fadeEyes(false, fadeMsFromBody());  handleStatus(); }
void handleSmileOn()  { fadeSmile(true,  fadeMsFromBody()); handleStatus(); }
void handleSmileOff() { fadeSmile(false, fadeMsFromBody()); handleStatus(); }

void handleLight() {
  sendLightJson();
}

// POST /calibrate with {"state":"light"} or {"state":"dark"}.
// Stores the current reading as the light-on or light-off ambient level, then
// sets the threshold midway between the two and saves to NVS.
void handleCalibrate() {
  String state;
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    int key = body.indexOf("state");
    if (key >= 0) {
      int colon = body.indexOf(':', key);
      if (colon >= 0) {
        // Grab the quoted value after the colon.
        int q1 = body.indexOf('"', colon);
        int q2 = (q1 >= 0) ? body.indexOf('"', q1 + 1) : -1;
        if (q1 >= 0 && q2 > q1) state = body.substring(q1 + 1, q2);
      }
    }
  }

  int raw = readLight();
  if (state == "light") {
    lightReading = raw;
  } else if (state == "dark") {
    darkReading = raw;
  } else {
    server.send(400, "application/json",
                "{\"error\":\"state must be 'light' or 'dark'\"}");
    return;
  }
  updateThreshold();
  saveCalibration();

  String s = "{";
  s += "\"stored\":\"" + state + "\",";
  s += "\"raw\":" + String(raw) + ",";
  s += "\"light\":" + String(lightReading) + ",";
  s += "\"dark\":" + String(darkReading) + ",";
  s += "\"threshold\":" + String(threshold);
  s += "}";
  server.send(200, "application/json", s);
}

// ---------------------------------------------------------------------------
// Wi-Fi
// ---------------------------------------------------------------------------

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname("botfia-robot");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected. IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("Wi-Fi failed. Check secrets.h. Will keep retrying in loop.");
  }
}

// ---------------------------------------------------------------------------
// Arduino lifecycle
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(200);

  // LEDs: attach LEDC PWM and start fully off.
  ledcAttach(PIN_EYE_LEFT,  LEDC_FREQ_HZ, LEDC_BITS);
  ledcAttach(PIN_EYE_RIGHT, LEDC_FREQ_HZ, LEDC_BITS);
  ledcAttach(PIN_SMILE,     LEDC_FREQ_HZ, LEDC_BITS);
  ledcWrite(PIN_EYE_LEFT, 0);
  ledcWrite(PIN_EYE_RIGHT, 0);
  ledcWrite(PIN_SMILE, 0);

  // Light sensor: 12-bit range, full 0-3.3V span.
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_LIGHT_SENS, ADC_11db);

  loadCalibration();

  connectWifi();

  if (MDNS.begin("botfia-robot")) {
    MDNS.addService("http", "tcp", 80);
    Serial.println("mDNS: http://botfia-robot.local");
  }

  server.on("/status",     HTTP_GET,  handleStatus);
  server.on("/face/on",    HTTP_POST, handleFaceOn);
  server.on("/face/off",   HTTP_POST, handleFaceOff);
  server.on("/eyes/on",    HTTP_POST, handleEyesOn);
  server.on("/eyes/off",   HTTP_POST, handleEyesOff);
  server.on("/smile/on",   HTTP_POST, handleSmileOn);
  server.on("/smile/off",  HTTP_POST, handleSmileOff);
  server.on("/light",      HTTP_GET,  handleLight);
  server.on("/calibrate",  HTTP_POST, handleCalibrate);
  server.onNotFound([]() {
    server.send(404, "application/json", "{\"error\":\"not found\"}");
  });
  server.begin();

  Serial.println("Table unit ready.");
}

void loop() {
  server.handleClient();

  // Reconnect quietly if Wi-Fi drops.
  static unsigned long lastCheck = 0;
  if (millis() - lastCheck > 10000) {
    lastCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi dropped, reconnecting...");
      WiFi.reconnect();
    }
  }
}
