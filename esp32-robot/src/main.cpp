// Botfia robot hardware — ESP32-WROOM-32 on the table.
//
// Drives the eye LEDs, smile LEDs, light sensor, shuffle drum motor, and head
// stepper, taking commands from the Pi over Wi-Fi. This is a skeleton: it joins
// Wi-Fi, announces itself at botfia-robot.local, and answers GET /status. The
// hardware behavior is added in the build phases (4: eyes/smile/light sensor,
// 5: drum, 6: head) so we don't skip ahead.

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>

#include "secrets.h"

// ---- Pin map (from CLAUDE.md). Declared here for reference; wired up per phase. ----
// Avoid the flash pins (6-11) and strapping pins (0, 2, 5, 12, 15).
static const int PIN_EYE_LEFT   = 25;   // red eye LED (PWM)
static const int PIN_EYE_RIGHT  = 26;   // red eye LED (PWM)
static const int PIN_SMILE      = 27;   // smile LEDs (PWM)
static const int PIN_LIGHT_SENS = 34;   // photoresistor, ADC1 (input only)
static const int PIN_TB_PWMA    = 14;   // drum motor: PWM
static const int PIN_TB_AIN1    = 16;   // drum motor: direction
static const int PIN_TB_AIN2    = 17;   // drum motor: direction
static const int PIN_TB_STBY    = 4;    // drum motor: standby
static const int PIN_ENC_A      = 32;   // drum encoder A
static const int PIN_ENC_B      = 33;   // drum encoder B
static const int PIN_STEP       = 22;   // head stepper (TMC2209): STEP
static const int PIN_DIR        = 23;   // head stepper (TMC2209): DIR
static const int PIN_EN         = 21;   // head stepper (TMC2209): EN

WebServer server(80);

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

void handleStatus() {
  String s = "{";
  s += "\"name\":\"botfia-robot\",";
  s += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  s += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  s += "\"uptime_s\":" + String(millis() / 1000);
  s += "}";
  server.send(200, "application/json", s);
}

void setup() {
  Serial.begin(115200);
  delay(200);

  connectWifi();

  if (MDNS.begin("botfia-robot")) {
    MDNS.addService("http", "tcp", 80);
    Serial.println("mDNS: http://botfia-robot.local");
  }

  server.on("/status", HTTP_GET, handleStatus);
  server.begin();

  Serial.println("Robot hardware unit ready (skeleton).");
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
