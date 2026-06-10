# IoT Vehicle Tracking & Theft Prevention System

An industry-oriented IoT course project implementing real-time geographic vehicle tracking, local geofencing, and active theft prevention mechanisms. This repository includes both a C++ firmware codebase for physical **ESP32 NodeMCU** hardware and a fully interactive **Python Web Simulator & Leaflet.js Dashboard** for environments lacking hardware.

---

## 📖 Project Overview & Problem Statement

Vehicle theft and inefficient fleet management represent massive financial risks for individuals and logistics corporations. Standard GPS trackers offer passive monitoring but lack active, immediate anti-theft countermeasures like remote ignition cutoff or local perimeter alerts.

This project solves this by combining:
1.  **Passive Tracking:** Live GPS coordinates parsed, mapped, and logged.
2.  **Active Tamper Detection:** Accelerometer/vibration triggers that sound a local alarm siren.
3.  **Local Geofencing:** Microcontroller-level boundary calculations using the spherical Haversine formula.
4.  **Remote Immobilization:** Cloud-to-device relay control capable of interrupting the starter coil to prevent hotwiring.

---

## 🛠️ Technology Stack

*   **Microcontroller Firmware:** C++ (Arduino IDE), TinyGPS++ library.
*   **Backend Server:** Python 3, Flask.
*   **Frontend Dashboard:** HTML5, Vanilla CSS3 (glassmorphism details), Vanilla Javascript.
*   **Mapping Engine:** Leaflet.js API (no API token required).
*   **Database & Reporting:** CSV logging (Python csv module) and PDF compiling (via `fpdf2`).

---

## 📂 Folder Structure

```
IoT-Vehicle-Tracking-Theft-Prevention-System/
├── arduino_code/            # ESP32 C++ source files
│   └── vehicle_tracker/
│       └── vehicle_tracker.ino
├── python_simulation/       # Python simulator and reporting engine
│   ├── __init__.py
│   ├── simulation_engine.py # Simulates movement and states
│   └── report_generator.py  # Exports data to CSV and PDF
├── dashboard/               # HTML/CSS/JS frontend dashboard
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/                    # CSV database of location history
│   └── location_history.csv
├── outputs/                 # PDF reports and screenshot output
├── images/                  # Project imagery for README
├── circuit_diagram/         # Circuit schematic documentation
│   └── wiring_guide.md
├── reports/                 # Analysis and reports (academic)
├── docs/                    # Detailed guides & interview prep
│   ├── interview_prep.md
│   └── implementation_plan.md
├── README.md                # GitHub main documentation
├── requirements.txt         # Python dependencies
└── main.py                  # Entrypoint to run server & simulation
```

---

## 🔌 Circuit Connection Schematic

The system uses an **ESP32 NodeMCU** core. Wire the physical modules as follows:

| Sensor / Module | Component Pin | ESP32 GPIO Pin |
| :--- | :--- | :--- |
| **NEO-6M GPS Receiver** | TXD | GPIO 16 (RX2) |
| | RXD | GPIO 17 (TX2) |
| **SW-420 Vibration Sensor**| DO (Digital Out) | GPIO 25 |
| **5V Relay Module** | IN (Control Input) | GPIO 27 |
| **5V Active Buzzer** | Positive (+) | GPIO 26 |
| **LED Green (Status)** | Anode (+) | GPIO 32 |
| **LED Red (Alert)** | Anode (+) | GPIO 33 |

> [!NOTE]
> Detailed connection explanations and failsafe starter coil schematics are available in the [Wiring Guide](docs/wiring_guide.md).

---

## 💻 Running the Web Simulation Engine

If you do not have the physical hardware, you can run the full system simulation on your local computer.

### 1. Prerequisites
Ensure you have Python 3.9+ installed.

### 2. Install Dependencies
Clone this repository, navigate to the folder, and run:
```bash
pip install -r requirements.txt
```

### 3. Start the Server
Run the Flask server entry point:
```bash
python main.py
```

### 4. Open the Dashboard
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🖥️ Live Dashboard Features

The running web portal contains three main sections accessible via the sidebar navigation:

1.  **Live Monitor (Interactive Map & Metrics):**
    *   *Real-time Map:* Shows the vehicle movement using Leaflet.js, tracing a dashed trail.
    *   *Geofence Perimeter:* Displays a blue safety circle of 200m.
    *   *Simulation Controls:* Switch the vehicle between **Parked**, **Driving Route** (moves within safe zone), **Vehicle Stolen** (moves and vibrates with engine off), and **Geofence Breach** (drives rapidly outside the perimeter).
    *   *Immobilizer Toggle:* Remotely cuts off the ignition system.
    *   *Live Alert Logger:* Instantly prints warnings when geofences are breached or vehicle tampering is detected.
2.  **Wiring Guide:** Shows the pinouts and electrical details.
3.  **Interview Prep:** Features interactive flip-cards with core IoT design questions and answers to prepare for project reviews.

---

## 📊 Generating Reports

*   **CSV Exports:** Click **Export CSV** in the top header to download the complete raw coordinate history from the database (`data/location_history.csv`).
*   **PDF Reports:** Click **Generate PDF Report** to create a formatted document under `outputs/location_report.pdf` featuring summary metrics (max speed, total alerts, counts of geofence breaches) and a zebra-striped table of coordinates.

---

## 🚀 Future Improvements

*   **Cellular Integration:** Interfacing with a SIM800L module to upload data over cellular GPRS connections.
*   **Low-Power Sleep Modes:** Placing the ESP32 in light-sleep mode, waking up only via external vibration sensor hardware interrupts.
*   **Advanced Encryption:** Using TLS/SSL certificates to encrypt MQTT or HTTP messages sent between the device and cloud dashboards.
