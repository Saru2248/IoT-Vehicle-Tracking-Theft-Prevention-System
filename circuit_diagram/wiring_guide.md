# Circuit Connection Guide: IoT Vehicle Tracking & Theft Prevention System

This guide outlines the wiring schematics, connection pins, and hardware debugging protocols for setting up the physical project using an **ESP32 NodeMCU** development board.

---

## 1. Electrical Schematic Connections

| Component | Pin Label | Pin Type | ESP32 GPIO Target | Remarks |
| :--- | :--- | :--- | :--- | :--- |
| **NEO-6M GPS Receiver** | VCC | Power | 3.3V | Runs on 3V3 rail. Do not overload. |
| | GND | Ground | GND | Common ground loop. |
| | TXD | Output | GPIO 16 (RX2) | Hardware Serial 2 RX. |
| | RXD | Input | GPIO 17 (TX2) | Hardware Serial 2 TX. |
| **SW-420 Vibration Sensor** | VCC | Power | 3.3V | Pinout power. |
| | GND | Ground | GND | Common ground. |
| | DO | Output | GPIO 25 | Digital signal (Interrupt pin). |
| **5V Relay Module** | VCC | Power | Vin (5V) | Power from USB Vin line. |
| | GND | Ground | GND | Common ground. |
| | IN | Input | GPIO 27 | Control signal (Active LOW). |
| **5V Active Buzzer** | Positive (+) | Input | GPIO 26 | High signal sounds the buzzer. |
| | Negative (-) | Ground | GND | Common ground. |
| **LED Green (Status)** | Anode (+) | Input | GPIO 32 | Status indicator (via 220Ω resistor). |
| | Cathode (-) | Ground | GND | Common ground. |
| **LED Red (Alert)** | Anode (+) | Input | GPIO 33 | Alarm indicator (via 220Ω resistor). |
| | Cathode (-) | Ground | GND | Common ground. |

---

## 2. Relay Wiring & Failsafe Starter Loop

The starter motor cutoff relay should be integrated into the car's ignition circuit as a **Normally Closed (NC)** switch. This ensures that the engine can start normally if the tracking unit is powered off, preventing emergency lockouts.

```
       +---------------------------------------------+
       |             Ignition Switch Key             |
       +----------------------o----------------------+
                              |
                              | [Original Wire Cut Here]
                              v
                  +-----------o-----------+
                  |  Normally Closed (NC) |
                  |                       |
                  |     5V SPDT Relay     |
                  |                       |
                  |     Common (COM)      |
                  +-----------o-----------+
                              |
                              v
       +----------------------o----------------------+
       |           Starter Motor / Solenoid          |
       +---------------------------------------------+
```

---

## 3. Hardware Assembly Tips
1.  **Common Grounding:** Ensure all ground pins (GND) are connected to a single point. ESP32, GPS, Relay, and sensors must share a common ground, otherwise serial communication and control lines will capture electrical noise.
2.  **GPS Sat Lock:** The NEO-6M GPS module has a tiny status LED. If it is blinking (typically once per second), it has successfully obtained a satellite position lock. If it remains solid or off, it is still searching for satellites. Testing must be done outdoors or near a window.
3.  **Resistors for LEDs:** Always use a current-limiting resistor (e.g., 220 Ohm or 330 Ohm) in series with the indicator LEDs. Connecting them directly to the ESP32 GPIOs will draw too much current and burn out the ESP32 pin.
