import math
import random
import os
import csv
from datetime import datetime


class VehicleSimulator:
    """Single vehicle simulator with comprehensive telemetry"""

    def __init__(self, vehicle_id="V001", vehicle_name="Alpha Truck", log_filepath="data/location_history.csv"):
        self.vehicle_id = vehicle_id
        self.vehicle_name = vehicle_name
        self.log_filepath = log_filepath

        # Geofence
        self.geofence_lat = 18.5204
        self.geofence_lon = 73.8567
        self.geofence_radius = 200.0
        self.geofence_zones = [{"name": "Home Base", "lat": 18.5204, "lon": 73.8567, "radius": 200}]

        # GPS state
        self.current_lat = self.geofence_lat
        self.current_lon = self.geofence_lon
        self.speed = 0.0
        self.heading = 0.0
        self.prev_lat = self.geofence_lat
        self.prev_lon = self.geofence_lon

        # Vehicle states
        self.ignition = False
        self.vibration = False
        self.relay_locked = False
        self.status = "Parked"
        self.alert_type = "None"

        # Speed limiter
        self.speed_limit = 80.0
        self.speed_alert = False

        # Trip
        self.trip_distance = 0.0

        # Driver behaviour
        self.driver_score = 100.0
        self.harsh_braking_events = 0
        self.overspeed_events = 0
        self.prev_speed = 0.0

        # OBD-II
        self.engine_rpm = 0
        self.fuel_level = round(random.uniform(45, 90), 1)
        self.battery_voltage = 12.6
        self.engine_temp = 28.0
        self.engine_load = 0.0

        # Analytics
        self.total_alerts = 0
        self.alert_history = []  # for heatmap
        self.theft_risk_score = 0

        # Trajectory
        self.route_step = 0
        self.trajectory_angle = random.uniform(0, 6.28)

        self._ensure_log_file()

    def _ensure_log_file(self):
        d = os.path.dirname(self.log_filepath)
        if d and not os.path.exists(d):
            os.makedirs(d)
        if not os.path.exists(self.log_filepath):
            with open(self.log_filepath, mode='w', newline='') as f:
                csv.writer(f).writerow([
                    "Timestamp", "Vehicle_ID", "Latitude", "Longitude",
                    "Speed_kmh", "Heading", "Ignition", "Vibration",
                    "Fuel_Level", "Battery_Voltage", "Engine_RPM",
                    "Engine_Temp", "Driver_Score", "Trip_Distance_km",
                    "Immobilized", "Status", "Alert_Type", "Theft_Risk_Score"
                ])

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return 6371000.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def set_speed_limit(self, limit):
        self.speed_limit = float(limit)

    def set_geofence_radius(self, radius):
        self.geofence_radius = float(radius)
        if self.geofence_zones:
            self.geofence_zones[0]["radius"] = float(radius)

    def add_geofence_zone(self, name, lat, lon, radius):
        self.geofence_zones.append({"name": name, "lat": float(lat), "lon": float(lon), "radius": float(radius)})

    def _update_obd(self):
        if self.ignition:
            self.engine_rpm = int(800 + (self.speed/120)*4000 + random.uniform(-150, 150))
            self.engine_load = round(20 + (self.speed/120)*70 + random.uniform(-4, 4), 1)
            self.engine_temp = round(min(96, self.engine_temp + random.uniform(0.05, 0.3)), 1)
            self.fuel_level = max(0, self.fuel_level - self.speed/200000)
            self.battery_voltage = round(13.8 + random.uniform(-0.15, 0.15), 2)
        else:
            self.engine_rpm = 0
            self.engine_load = 0.0
            self.engine_temp = max(28, self.engine_temp - random.uniform(0.05, 0.2))
            self.battery_voltage = round(12.6 + random.uniform(-0.05, 0.05), 2)

    def _update_driver_score(self):
        if self.ignition:
            if self.prev_speed > 40 and self.speed < self.prev_speed - 25:
                self.harsh_braking_events += 1
                self.driver_score = max(0, self.driver_score - 5)
            if self.speed > self.speed_limit:
                self.overspeed_events += 1
                self.driver_score = max(0, self.driver_score - 1.5)
                self.speed_alert = True
            else:
                self.speed_alert = False
                self.driver_score = min(100, self.driver_score + 0.05)

    def _calc_theft_risk(self):
        risk = 0
        h = datetime.now().hour
        if h >= 23 or h <= 5:
            risk += 25
        if self.vibration and not self.ignition:
            risk += 40
        if self.speed > 2 and not self.ignition and not self.relay_locked:
            risk += 30
        dist = self.calculate_distance(self.current_lat, self.current_lon, self.geofence_lat, self.geofence_lon)
        if dist > self.geofence_radius and not self.ignition:
            risk += 20
        self.theft_risk_score = min(100, risk)

    def _update_odometer(self):
        if self.ignition and self.speed > 1:
            self.trip_distance += self.calculate_distance(self.current_lat, self.current_lon, self.prev_lat, self.prev_lon) / 1000.0
        self.prev_lat = self.current_lat
        self.prev_lon = self.current_lon

    def set_mode(self, mode):
        mode_map = {
            "parked":          (False, False, "Parked", "None"),
            "stolen":          (False, True,  "Stolen (Towed)", "Theft Alarm"),
            "geofence_breach": (True,  False, "Geofence Breach", "Geofence Breach"),
        }
        if mode in mode_map:
            ign, vib, st, al = mode_map[mode]
            self.ignition, self.vibration, self.status, self.alert_type = ign, vib, st, al
            if mode == "parked":
                self.speed = 0.0
                self.current_lat = self.geofence_lat
                self.current_lon = self.geofence_lon
                self.route_step = 0
                self.trip_distance = 0.0
        elif mode == "driving":
            self.ignition, self.vibration, self.status, self.alert_type = True, False, "Driving", "None"
        elif mode == "immobilize":
            self.relay_locked = True
            self.speed = 0.0
            self.ignition = False
            self.status = "Immobilized"
            self.alert_type = "Remote Lock Activated"
        elif mode == "reset_immobilize":
            self.relay_locked = False
            self.status = "Parked"
            self.alert_type = "None"

    def update(self):
        self.prev_speed = self.speed

        if self.relay_locked:
            self.speed, self.ignition, self.vibration = 0.0, False, False
            self.status, self.alert_type = "Immobilized", "Remote Lock Activated"
        elif self.status == "Parked":
            self.speed = 0.0
            self.vibration = random.random() > 0.97
            self.current_lat = self.geofence_lat + random.uniform(-0.00002, 0.00002)
            self.current_lon = self.geofence_lon + random.uniform(-0.00002, 0.00002)
            self.alert_type = "None"
        elif self.status == "Driving":
            self.speed = random.uniform(30, 78)
            self.trajectory_angle += 0.05
            self.current_lat = self.geofence_lat + 0.0009 * math.sin(self.trajectory_angle)
            self.current_lon = self.geofence_lon + 0.0009 * math.cos(self.trajectory_angle)
            dist = self.calculate_distance(self.current_lat, self.current_lon, self.geofence_lat, self.geofence_lon)
            self.alert_type = "Geofence Breach" if dist > self.geofence_radius else "None"
        elif self.status == "Stolen (Towed)":
            self.speed = random.uniform(10, 28)
            self.route_step += 1
            off = 0.00015 * self.route_step
            self.current_lat = self.geofence_lat + off
            self.current_lon = self.geofence_lon + off
            dist = self.calculate_distance(self.current_lat, self.current_lon, self.geofence_lat, self.geofence_lon)
            self.alert_type = "Theft + Geofence Breach" if dist > self.geofence_radius else "Theft Alarm"
        elif self.status == "Geofence Breach":
            self.speed = random.uniform(65, 100)
            self.route_step += 1
            off = 0.0005 * self.route_step
            self.current_lat = self.geofence_lat + off
            self.current_lon = self.geofence_lon + off
            self.alert_type = "Geofence Breach"

        self._update_obd()
        self._update_driver_score()
        self._calc_theft_risk()
        self._update_odometer()

        if self.speed > self.speed_limit and self.alert_type == "None":
            self.alert_type = f"Speed Limit Exceeded ({self.speed:.0f} km/h)"
            self.speed_alert = True

        if self.alert_type != "None":
            self.total_alerts += 1
            self.alert_history.append([self.current_lat, self.current_lon, 0.8])
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]

        dlat = self.current_lat - self.prev_lat
        dlon = self.current_lon - self.prev_lon
        if dlat or dlon:
            self.heading = round((math.degrees(math.atan2(dlon, dlat)) + 360) % 360, 1)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log(ts)
        return self._state(ts)

    def _state(self, ts):
        dist = self.calculate_distance(self.current_lat, self.current_lon, self.geofence_lat, self.geofence_lon)
        zones = [{"name": z["name"], "inside": self.calculate_distance(self.current_lat, self.current_lon, z["lat"], z["lon"]) <= z["radius"], "distance": round(self.calculate_distance(self.current_lat, self.current_lon, z["lat"], z["lon"]), 1)} for z in self.geofence_zones]
        return {
            "timestamp": ts, "vehicle_id": self.vehicle_id, "vehicle_name": self.vehicle_name,
            "latitude": round(self.current_lat, 6), "longitude": round(self.current_lon, 6),
            "speed": round(self.speed, 2), "heading": self.heading,
            "ignition": self.ignition, "vibration": self.vibration, "relay_locked": self.relay_locked,
            "status": self.status, "alert_type": self.alert_type,
            "speed_alert": self.speed_alert, "speed_limit": self.speed_limit,
            "distance_from_center": round(dist, 1), "geofence_radius": self.geofence_radius,
            "trip_distance": round(self.trip_distance, 2),
            "driver_score": round(self.driver_score, 1),
            "harsh_braking_events": self.harsh_braking_events, "overspeed_events": self.overspeed_events,
            "theft_risk_score": self.theft_risk_score,
            "fuel_level": round(self.fuel_level, 1), "battery_voltage": self.battery_voltage,
            "engine_rpm": self.engine_rpm, "engine_temp": round(self.engine_temp, 1), "engine_load": self.engine_load,
            "total_alerts": self.total_alerts, "alert_history": self.alert_history[-30:],
            "zone_statuses": zones,
            "geofence_center": {"lat": self.geofence_lat, "lon": self.geofence_lon}
        }

    def _log(self, ts):
        with open(self.log_filepath, mode='a', newline='') as f:
            csv.writer(f).writerow([
                ts, self.vehicle_id, round(self.current_lat, 6), round(self.current_lon, 6),
                round(self.speed, 2), self.heading, self.ignition, self.vibration,
                round(self.fuel_level, 1), self.battery_voltage, self.engine_rpm,
                round(self.engine_temp, 1), round(self.driver_score, 1), round(self.trip_distance, 2),
                self.relay_locked, self.status, self.alert_type, self.theft_risk_score
            ])

    def get_history(self, limit=60):
        rows = []
        if not os.path.exists(self.log_filepath):
            return rows
        with open(self.log_filepath) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Vehicle_ID", self.vehicle_id) == self.vehicle_id:
                    rows.append(row)
        return rows[-limit:]


class FleetManager:
    """Manages 5 simulated vehicles"""

    CONFIGS = [
        ("V001", "Alpha Truck",   0,      0),
        ("V002", "Beta Van",      0.003,  0.002),
        ("V003", "Gamma Bike",   -0.002,  0.004),
        ("V004", "Delta Car",     0.001, -0.003),
        ("V005", "Epsilon Bus",  -0.003, -0.001),
    ]

    def __init__(self):
        self.vehicles = {}
        modes = ["parked", "driving", "parked", "driving", "parked"]
        for i, (vid, name, dlat, dlon) in enumerate(self.CONFIGS):
            sim = VehicleSimulator(vid, name, f"data/fleet_{vid}.csv")
            sim.geofence_lat += dlat
            sim.geofence_lon += dlon
            sim.current_lat = sim.geofence_lat
            sim.current_lon = sim.geofence_lon
            sim.set_mode(modes[i])
            self.vehicles[vid] = sim

    def update_all(self):
        return [v.update() for v in self.vehicles.values()]

    def set_mode(self, vid, mode):
        v = self.vehicles.get(vid)
        if v:
            v.set_mode(mode)
            return True
        return False
