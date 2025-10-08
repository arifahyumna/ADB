#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_MAX31855.h>
#include <ArduinoJson.h>

// CONFIG WIFI
#define WIFI_SSID   "YOUR_SSID"
#define WIFI_PASS   "YOUR_PASSWORD"

// CONFIG MQTT
#define MQTT_SERVER   "192.168.1.100"  
#define MQTT_PORT 	1883
#define MQTT_USER 	""           	
#define MQTT_PASSWD   ""

#define TOPIC_TELE	"press/temp"
#define TOPIC_ALERT   "press/alert"

// TEMPERATURE CONFIG
#define TEMP_TARGET_LOW   150.0
#define TEMP_TARGET_HIGH  200.0
#define HOLD_TIME_SEC 	300   // 5 menit
#define COOL_DOWN_READY   30.0
#define OVERHEAT_LIMIT	220.0

//  PIN CONFIG
#define PIN_SCK   18 
#define PIN_CS	5
#define PIN_MISO  19
#define SSR_PIN   14

// OBJECTS
Adafruit_MAX31855 thermocouple(PIN_SCK, PIN_CS, PIN_MISO);

WiFiClient espClient;
PubSubClient mqtt(espClient);

enum State { ST_IDLE, ST_HEATING, ST_HOLD, ST_COOLING, ST_DONE, ST_ERROR };
State state = ST_IDLE;

unsigned long holdStart = 0;
unsigned long lastTemp = 0;
float currentTemp = 0.0;

// FUNCTIONS
void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
delay(500);
Serial.print(".");
  }
  Serial.println(" Connected!");
}

void reconnectMQTT() {
  while (!mqtt.connected()) {
Serial.print("Connecting MQTT...");
if (mqtt.connect("ESP32Client",MQTT_USER, MQTT_PASSWD)) {
      Serial.println("connected");
} else {
  Serial.print("failed, rc=");
  Serial.print(mqtt.state());
  delay(2000);
}
  }
}

void publishTemp() {
  StaticJsonDocument<256> doc;
  doc["temp_c"] = currentTemp;
  doc["state"] = (int)state;
  doc["ts"] = millis()/1000;

  char buf[256];
  size_t n = serializeJson(doc, buf);
  mqtt.publish(TOPIC_TELE, buf, n);
}

void publishAlert(const char* msg) {
  StaticJsonDocument<200> doc;
  doc["alert"] = msg;
  doc["temp_c"] = currentTemp;
  doc["ts"] = millis()/1000;

  char buf[200];
  size_t n = serializeJson(doc, buf);
  mqtt.publish(TOPIC_ALERT, buf, n);
}

// SETUP
void setup() {
  Serial.begin(115200);
  pinMode(SSR_PIN, OUTPUT);
  digitalWrite(SSR_PIN, LOW);

  setupWiFi();
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
}

void loop() {
  if (!mqtt.connected()) reconnectMQTT();
  mqtt.loop();

  currentTemp = thermocouple.readCelsius();

  if (currentTemp > OVERHEAT_LIMIT) {
    digitalWrite(SSR_PIN, LOW);
    state = ST_ERROR;
    publishAlert("OVERHEAT");
  }

  switch(state) {
    case ST_IDLE:
      if (currentTemp > TEMP_TARGET_LOW) {
        state = ST_HEATING;
        publishAlert("Pemanasan");
      }
    break;

    case ST_HEATING:
      digitalWrite(SSR_PIN, HIGH);
      if (currentTemp >= TEMP_TARGET_LOW && currentTemp <= TEMP_TARGET_HIGH) {
        state = ST_HOLD;
        holdStart = millis();
        publishAlert("Pendinginan");
      }
    break;

    case ST_HOLD:
      digitalWrite(SSR_PIN, HIGH);
      if ((millis() - holdStart)/1000 >= HOLD_TIME_SEC) {
        state = ST_COOLING;
        digitalWrite(SSR_PIN, LOW);
      }
    break;

    case ST_COOLING:
      digitalWrite(SSR_PIN, LOW);
      if (currentTemp <= COOL_DOWN_READY) {
        state = ST_DONE;
        publishAlert("Proses Selesai");
      }
    break;

    case ST_ERROR:
      digitalWrite(SSR_PIN, LOW);
      publishAlert("ERROR");
    break;
    }

  if (millis() - lastTemp >= 60000) {
  publishTemp();
  lastTemp = millis();
  }

  delay(500);
}



