#include <WiFi.h>
#include <PubSubClient.h>
#include <MAX6675.h>
#include <ArduinoJson.h>

// === Konfigurasi WiFi ===
const char* ssid = "anum";
const char* password = "gojek123";

// === Konfigurasi MQTT Broker ===
#define mqtt_server "192.168.43.9" //ganti dengan mqtt-server yang digunakan
#define mqtt_port 1883 
#define mqtt_user ""
#define mqtt_passwd ""

// === Topik MQTT ===
#define topik_suhu "esp32/suhu"
#define topik_alert "esp32/alert"
#define topik_daya "esp32/daya"

// === Temperature Config ===
#define TEMP_TARGET_LOW 150.0
#define TEMP_TARGET_HIGH 200.0
#define HOLD_TIME_SEC 300
#define COOL_DOWN_READY 30.0
#define OVERHEAT_LIMIT 220.0

// === Pin MAX6675 ===
int thermoSO = 19;
int thermoCS = 23;
int thermoSCK = 5;
MAX6675 thermocouple(thermoSCK, thermoCS, thermoSO);
int SSR_PIN = 14;

WiFiClient espClient;
PubSubClient mqtt(espClient);

enum State { ST_IDLE, ST_HEATING, ST_HOLD, ST_COOLING, ST_DONE, ST_ERROR };
State state = ST_IDLE;

unsigned long holdStart = 0;
unsigned long lastTemp = 0;
float currentTemp = 0.0;
float daya = 0.0;


// === Fungsi koneksi WiFi ===
void setup_wifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println("Connected!");

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

// === connect MQTT ===
void reconnectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("Connecting MQTT...");
    if (mqtt.connect("ESP32Client", mqtt_user, mqtt_passwd)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt.state());
      delay(2000);
    }
  }
}

// === publish code ===
void publishSuhu() {
  StaticJsonDocument<256> doc;
  doc["temp_c"] = currentTemp;
  doc["state"] = (int)state;
  doc["ts"] = millis() / 1000;

  char buf[256];
  size_t n = serializeJson(doc, buf);
  mqtt.publish(topik_suhu, buf, n);
}

void publishAlert(const char* msg) {
  StaticJsonDocument<200> doc;
  doc["alert"] = msg;
  doc["temp_c"] = currentTemp;
  doc["ts"] = millis() / 1000;

  char buf[200];
  size_t n = serializeJson(doc, buf);
  mqtt.publish(topik_alert, buf, n);
}

void publishDaya() {
  StaticJsonDocument<128> doc;
  doc["daya_watt"] = daya;
  doc["ts"] = millis() / 1000;

  char buf[128];
  size_t n = serializeJson(doc, buf);
  mqtt.publish(topik_daya, buf, n);
}

// === Setup ===
void setup() {
  Serial.begin(115200);
  setup_wifi();

  mqtt.setServer(mqtt_server, mqtt_port);
  delay(2000); // Stabilkan pembacaan awal
}

// === Loop utama ===
void loop() {
  if (!mqtt.connected()) {
    reconnectMQTT();
  }
  mqtt.loop();

  // Baca suhu dari MAX6675
  currentTemp = thermocouple.getCelsius();

  if (currentTemp > OVERHEAT_LIMIT) {
    state = ST_ERROR;
    publishAlert("OVERHEAT");
  }

  switch (state) {
    case ST_IDLE:
      if (currentTemp > TEMP_TARGET_LOW) {
        state = ST_HEATING;
        publishAlert("Pemanasan dimulai");
      }
      break;

    case ST_HEATING:
      if (currentTemp >= TEMP_TARGET_LOW && currentTemp <= TEMP_TARGET_HIGH) {
        state = ST_HOLD;
        holdStart = millis();
        publishAlert("Suhu stabil (Hold)");
      }
      break;

    case ST_HOLD:
      if ((millis() - holdStart) / 1000 >= HOLD_TIME_SEC) {
        state = ST_COOLING;
        publishAlert("Pendinginan dimulai");
      }
      break;

    case ST_COOLING:
      if (currentTemp <= COOL_DOWN_READY) {
        state = ST_DONE;
        publishAlert("Proses selesai");
      }
      break;

    case ST_ERROR:
      publishAlert("ERROR");
      break;

    case ST_DONE:
      break;
  }

  if (millis() - lastTemp >= 10000) {
    publishSuhu();
    publishDaya();
    lastTemp = millis();
  }

  delay(500);
  
}
