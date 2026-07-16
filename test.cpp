#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "DHT.h"

#define DHTPIN 15
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

const char* ssid = "Wokwi-GUEST";
const char* password = "";

const char* mqtt_server = "broker.emqx.io";
const char* telemetry_topic = "selma/automotive/telemetry";
const char* control_topic = "selma/automotive/control";

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long faultTimerStart = 0;   
bool isTempCurrentlyHigh = false;    
bool isFaultConfirmed = false;       
const unsigned long FAULT_DEBOUNCE_TIME = 3000; 
const float TEMP_THRESHOLD = 40.0;             

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Command Received: ");
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);

  if (message == "FAN_ON") {
    Serial.println("Action: Fan Activated");
  } else if (message == "FAN_OFF") {
    Serial.println("Action: Fan Deactivated");
  }
}

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("\nConnecting to WiFi...");
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connected!");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP32Automotive-" + String(random(0, 1000));

    if (client.connect(clientId.c_str())) {
      Serial.println("connected to broker!");
      client.subscribe(control_topic);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 2 seconds");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  setup_wifi(); 
  dht.begin(); 
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback); 
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  float t = dht.readTemperature();

  if (isnan(t)) {
    Serial.println("Failed to read from DHT sensor!");
    delay(2000);
    return;
  }

  String dtcCode = "None";
  String severityLevel = "NONE";
  bool hasFault = false;

  if (t > TEMP_THRESHOLD) {
    if (!isTempCurrentlyHigh) {
      isTempCurrentlyHigh = true;
      faultTimerStart = millis(); 
      Serial.println("Warning: Temperature exceeded threshold! Evaluating...");
    } else {
      if (millis() - faultTimerStart >= FAULT_DEBOUNCE_TIME) {
        isFaultConfirmed = true;
        dtcCode = "P0118"; 
        severityLevel = "CRITICAL";
        hasFault = true;
        Serial.println("ALERT: Fault Confirmed! DTC P0118 Active.");
      }
    }
  } else {
    isTempCurrentlyHigh = false;
    isFaultConfirmed = false;
  }

  JsonDocument doc;
  doc["device_id"] = "ESP32Automotive_01";
  
  JsonObject telemetry = doc["telemetry"].to<JsonObject>();
  telemetry["temperature"] = t;
  telemetry["battery_status"] = "OK";

  JsonObject diagnostics = doc["diagnostics"].to<JsonObject>();
  diagnostics["has_fault"] = hasFault;
  diagnostics["dtc_code"] = dtcCode;
  diagnostics["severity"] = severityLevel;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  Serial.print("Sending data: ");
  Serial.println(jsonPayload);

  client.publish(telemetry_topic, jsonPayload.c_str());
  
  delay(2000); 
}