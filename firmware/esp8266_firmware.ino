#include <ArduinoJson.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <FS.h>
#include <ModbusMaster.h>

#ifndef AGRI_WIFI_SSID
#error "Define AGRI_WIFI_SSID at build time"
#endif
#ifndef AGRI_WIFI_PASSWORD
#error "Define AGRI_WIFI_PASSWORD at build time"
#endif
#ifndef AGRI_API_URL
#error "Define AGRI_API_URL at build time"
#endif
#ifndef AGRI_SENSOR_TOKEN
#error "Define AGRI_SENSOR_TOKEN at build time"
#endif

const char *WIFI_SSID = AGRI_WIFI_SSID;
const char *WIFI_PASSWORD = AGRI_WIFI_PASSWORD;
const char *API_URL = AGRI_API_URL;
const char *SENSOR_TOKEN = AGRI_SENSOR_TOKEN;
ModbusMaster npk;

String readingPayload() {
  StaticJsonDocument<512> document;
  document["timestamp"] = String(millis());
  document["soil_moisture"] = 62;
  document["ph"] = 6.4;
  document["raw_n"] = 148;
  document["raw_p"] = 42;
  document["raw_k"] = 110;
  document["temperature"] = 28;
  document["humidity"] = 60;
  String output;
  serializeJson(document, output);
  return output;
}

void bufferReading(const String &payload) {
  String path = "/readings/" + String(millis()) + ".json";
  File file = SPIFFS.open(path, "w");
  if (file) { file.print(payload); file.close(); }
}

bool sendReading(const String &payload) {
  if (WiFi.status() != WL_CONNECTED) return false;
  WiFiClient client;
  HTTPClient http;
  http.begin(client, API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Sensor-Token", SENSOR_TOKEN);
  int status = http.POST(payload);
  http.end();
  return status == 200 || status == 201;
}

void flushBacklog() {
  Dir directory = SPIFFS.openDir("/readings");
  while (directory.next()) {
    File file = directory.openFile("r");
    String payload = file.readString();
    file.close();
    StaticJsonDocument<512> document;
    deserializeJson(document, payload);
    document["is_backlogged"] = true;
    String retryPayload;
    serializeJson(document, retryPayload);
    if (sendReading(retryPayload)) SPIFFS.remove(directory.fileName());
  }
}

void setup() {
  Serial.begin(9600);
  SPIFFS.begin();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) delay(250);
  flushBacklog();
  String payload = readingPayload();
  if (!sendReading(payload)) bufferReading(payload);
  ESP.deepSleep(15 * 60 * 1000000ULL);
}

void loop() {}
