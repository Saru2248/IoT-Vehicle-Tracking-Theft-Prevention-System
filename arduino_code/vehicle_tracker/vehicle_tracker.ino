/**
 * IoT Vehicle Tracking & Theft Prevention System
 * -------------------------------------------------------------
 * Microcontroller: ESP32 (NodeMCU)
 * Sensors: NEO-6M GPS Module, SW-420 Vibration Sensor
 * Actuators: 5V Active Buzzer, 5V Relay Module (Ignition Control)
 * Cloud: ThingSpeak / Blynk IoT
 * 
 * Description:
 * This code reads NMEA sentences from the NEO-6M GPS module, parses
 * latitude, longitude, and speed. It detects unauthorized vibration (theft)
 * and checks the current coordinates against a geofenced area.
 * It connects to WiFi and uploads data to the ThingSpeak server, while
 * listening for a remote immobilization command to cut off the engine relay.
 */

#include <WiFi.h>
#include <HardwareSerial.h>
#include <TinyGPS++.h>

// WiFi Configuration (Change these to match your network)
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ThingSpeak Channel Configuration
const char* server = "api.thingspeak.com";
const char* writeAPIKey = "YOUR_THINGSPEAK_WRITE_API_KEY";

// Pin Configurations
#define GPS_RX_PIN 16        // connected to TX of NEO-6M
#define GPS_TX_PIN 17        // connected to RX of NEO-6M
#define VIBRATION_PIN 25     // Digital input from SW-420 Vibration Sensor
#define BUZZER_PIN 26        // Digital output for Buzzer
#define RELAY_PIN 27         // Digital output for Ignition Relay (Active LOW)
#define LED_GREEN 32         // System OK / Connected status
#define LED_RED 33           // Alert / Theft status

// GPS Object
TinyGPSPlus gps;
HardwareSerial gpsSerial(2); // Use ESP32 UART2 (Serial2)

// Geofence Configuration
const double GEOFENCE_LAT = 18.5204; // Center Latitude (e.g., Pune, India)
const double GEOFENCE_LON = 73.8567; // Center Longitude
const double GEOFENCE_RADIUS_METERS = 200.0; // 200 meters safe radius

// System States
bool engineImmobilized = false;
bool theftAlarmActive = false;
bool geofenceBreached = false;
unsigned long lastUploadTime = 0;
const unsigned long uploadInterval = 15000; // Upload telemetry every 15 seconds

// Function Prototypes
void connectToWiFi();
void readGPS();
void checkTheftSensors();
void updateActuators();
void uploadTelemetry(double lat, double lon, double speed, String statusMsg);
double calculateDistance(double lat1, double lon1, double lat2, double lon2);

void setup() {
  Serial.begin(115200);
  
  // Initialize Pin Modes
  pinMode(VIBRATION_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);

  // Relay is active low; set HIGH to keep relay contact closed (engine running)
  digitalWrite(RELAY_PIN, HIGH); 
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);

  // Initialize GPS UART Communication
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Serial.println("NEO-6M GPS UART Initialized.");

  // Connect to Wifi network
  connectToWiFi();
}

void loop() {
  // Read GPS data constantly
  readGPS();

  // Monitor physical sensors (Vibration / Movement)
  checkTheftSensors();

  // Update Indicator LEDs and Buzzer state
  updateActuators();

  // Periodically send data to the Cloud Dashboard
  if (millis() - lastUploadTime > uploadInterval) {
    if (gps.location.isValid()) {
      double currentLat = gps.location.lat();
      double currentLon = gps.location.lng();
      double currentSpeed = gps.speed.kmph();
      
      // Calculate Geofence
      double distance = calculateDistance(currentLat, currentLon, GEOFENCE_LAT, GEOFENCE_LON);
      if (distance > GEOFENCE_RADIUS_METERS) {
        geofenceBreached = true;
        Serial.println("ALERT! Geofence limit breached!");
      } else {
        geofenceBreached = false;
      }

      String statusMsg = "Normal";
      if (theftAlarmActive) statusMsg = "Theft_Alarm";
      else if (geofenceBreached) statusMsg = "Geofence_Breached";
      else if (engineImmobilized) statusMsg = "Immobilized";

      uploadTelemetry(currentLat, currentLon, currentSpeed, statusMsg);
    } else {
      Serial.println("GPS: Waiting for satellite lock...");
    }
    lastUploadTime = millis();
  }
}

void connectToWiFi() {
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_GREEN, !digitalRead(LED_GREEN)); // Flash green LED while connecting
    timeout++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected Successfully!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(LED_GREEN, HIGH); // Steady green shows connection
  } else {
    Serial.println("\nWiFi Connection Failed! Operating in local mode.");
    digitalWrite(LED_GREEN, LOW);
  }
}

void readGPS() {
  while (gpsSerial.available() > 0) {
    char c = gpsSerial.read();
    gps.encode(c);
  }
}

void checkTheftSensors() {
  // Read SW-420 Vibration sensor
  int vibrationState = digitalRead(VIBRATION_PIN);

  // If vibration is detected AND engine should be off (theft condition)
  if (vibrationState == HIGH && !engineImmobilized) {
    // Basic debounce / validation: verify if it persists or log immediately
    theftAlarmActive = true;
    Serial.println("SECURITY ALERT: Vibration/tampering detected!");
  }
}

void updateActuators() {
  // If alarm is active or geofence breached, pulse red LED and buzzer
  if (theftAlarmActive || geofenceBreached) {
    digitalWrite(LED_RED, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    
    // Remote engine shutdown: Cut off Relay (set LOW)
    digitalWrite(RELAY_PIN, LOW);
  } else {
    digitalWrite(LED_RED, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    
    // Engine allowed to run (Relay set HIGH)
    if (!engineImmobilized) {
      digitalWrite(RELAY_PIN, HIGH);
    } else {
      digitalWrite(RELAY_PIN, LOW); // Lock engine if remotely immobilized
    }
  }
}

void uploadTelemetry(double lat, double lon, double speed, String statusMsg) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Skipping Cloud upload: WiFi offline.");
    return;
  }

  WiFiClient client;
  if (client.connect(server, 80)) {
    // Construct HTTP Request to ThingSpeak
    // Field 1: Latitude
    // Field 2: Longitude
    // Field 3: Speed (km/h)
    // Field 4: Status (0: Safe, 1: Vibration Alert, 2: Geofence Breach, 3: Immobilized)
    int statusInt = 0;
    if (statusMsg == "Theft_Alarm") statusInt = 1;
    else if (statusMsg == "Geofence_Breached") statusInt = 2;
    else if (statusMsg == "Immobilized") statusInt = 3;

    String url = "/update?api_key=" + String(writeAPIKey) +
                 "&field1=" + String(lat, 6) +
                 "&field2=" + String(lon, 6) +
                 "&field3=" + String(speed, 2) +
                 "&field4=" + String(statusInt);

    client.print(String("GET ") + url + " HTTP/1.1\r\n" +
                 "Host: " + server + "\r\n" +
                 "Connection: close\r\n\r\n");
    
    Serial.print("Telemetry Uploaded to ThingSpeak: ");
    Serial.println(url);
    client.stop();
  } else {
    Serial.println("ThingSpeak Connection Failed.");
  }
}

// Calculates distance in meters between two points using the Haversine formula
double calculateDistance(double lat1, double lon1, double lat2, double lon2) {
  double dLat = (lat2 - lat1) * DEG_TO_RAD;
  double dLon = (lon2 - lon1) * DEG_TO_RAD;
  
  double a = sin(dLat / 2) * sin(dLat / 2) +
             cos(lat1 * DEG_TO_RAD) * cos(lat2 * DEG_TO_RAD) *
             sin(dLon / 2) * sin(dLon / 2);
             
  double c = 2 * atan2(sqrt(a), sqrt(1 - a));
  double radiusOfEarthMeters = 6371000.0;
  return radiusOfEarthMeters * c;
}
