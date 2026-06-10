import os
import requests as http
from flask import Flask, jsonify, request, send_from_directory, send_file
from python_simulation.simulation_engine import VehicleSimulator, FleetManager
from python_simulation.report_generator import generate_pdf_report

app = Flask(__name__, static_folder='dashboard', static_url_path='')

CSV_PATH  = "data/location_history.csv"
PDF_PATH  = "outputs/location_report.pdf"

simulator = VehicleSimulator(log_filepath=CSV_PATH)
fleet     = FleetManager()

settings = {
    "telegram_token":   "",
    "telegram_chat_id": "",
    "discord_webhook":  "",
    "speed_limit":      80.0,
    "geofence_radius":  200.0,
    "voice_alerts":     True
}

# ── Static ──────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('dashboard', 'index.html')

# ── Primary vehicle telemetry ────────────────────────────────────────────────
@app.route('/api/telemetry')
def get_telemetry():
    return jsonify(simulator.update())

@app.route('/api/set_mode', methods=['POST'])
def set_mode():
    mode = request.args.get('mode', '')
    vid  = request.args.get('vehicle_id', None)
    if vid and vid != simulator.vehicle_id:
        fleet.set_mode(vid, mode)
    else:
        simulator.set_mode(mode)
    return jsonify({"status": "success", "mode": mode})

# ── Fleet ────────────────────────────────────────────────────────────────────
@app.route('/api/fleet')
def get_fleet():
    return jsonify(fleet.update_all())

@app.route('/api/fleet/set_mode', methods=['POST'])
def fleet_set_mode():
    data = request.get_json(force=True)
    fleet.set_mode(data.get("vehicle_id"), data.get("mode"))
    return jsonify({"status": "ok"})

# ── Analytics / Charts ───────────────────────────────────────────────────────
@app.route('/api/analytics')
def analytics():
    rows   = simulator.get_history(60)
    speeds = [{"t": r["Timestamp"], "v": float(r.get("Speed_kmh", 0))} for r in rows]
    fuel   = [{"t": r["Timestamp"], "v": float(r.get("Fuel_Level", 0))} for r in rows]
    scores = [{"t": r["Timestamp"], "v": float(r.get("Driver_Score", 100))} for r in rows]
    counts = {}
    for r in rows:
        a = r.get("Alert_Type", "None")
        if a != "None":
            counts[a] = counts.get(a, 0) + 1
    return jsonify({"speeds": speeds, "fuel": fuel, "driver_scores": scores,
                    "alert_counts": counts, "total": len(rows)})

# ── Route playback ────────────────────────────────────────────────────────────
@app.route('/api/playback')
def playback():
    rows = simulator.get_history(100)
    path = [{"lat": float(r.get("Latitude",0)), "lon": float(r.get("Longitude",0)),
              "timestamp": r.get("Timestamp",""), "speed": float(r.get("Speed_kmh",0)),
              "status": r.get("Status","")} for r in rows]
    return jsonify(path)

# ── Geofence zones ────────────────────────────────────────────────────────────
@app.route('/api/zones')
def get_zones():
    return jsonify(simulator.geofence_zones)

@app.route('/api/zones/add', methods=['POST'])
def add_zone():
    d = request.get_json(force=True)
    simulator.add_geofence_zone(d["name"], d["lat"], d["lon"], d["radius"])
    return jsonify({"status": "ok", "zones": simulator.geofence_zones})

@app.route('/api/zones/clear', methods=['POST'])
def clear_zones():
    simulator.geofence_zones = [simulator.geofence_zones[0]]
    return jsonify({"status": "ok"})

# ── Settings ──────────────────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    global settings
    if request.method == 'POST':
        d = request.get_json(force=True)
        settings.update(d)
        if "speed_limit"     in d: simulator.set_speed_limit(d["speed_limit"])
        if "geofence_radius" in d: simulator.set_geofence_radius(d["geofence_radius"])
        return jsonify({"status": "ok", "settings": settings})
    return jsonify(settings)

# ── Telegram alert ────────────────────────────────────────────────────────────
@app.route('/api/alert/telegram', methods=['POST'])
def send_telegram():
    token   = settings.get("telegram_token", "")
    chat_id = settings.get("telegram_chat_id", "")
    if not token or not chat_id:
        return jsonify({"status": "error", "message": "Telegram not configured"}), 400
    s   = simulator.update()
    msg = (f"🚨 *VEHICLE ALERT*\n\n*Status:* {s['status']}\n*Alert:* {s['alert_type']}\n"
           f"*Speed:* {s['speed']} km/h\n*Location:* {s['latitude']}, {s['longitude']}\n"
           f"🗺️ [Maps](https://maps.google.com/?q={s['latitude']},{s['longitude']})")
    try:
        r = http.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=6)
        return jsonify({"status": "ok", "response": r.json()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ── Discord alert ─────────────────────────────────────────────────────────────
@app.route('/api/alert/discord', methods=['POST'])
def send_discord():
    wh = settings.get("discord_webhook", "")
    if not wh:
        return jsonify({"status": "error", "message": "Discord webhook not configured"}), 400
    s = simulator.update()
    payload = {
        "username": "TrackSafe IoT",
        "embeds": [{"title": "🚨 Vehicle Security Alert", "color": 16711680,
                    "fields": [
                        {"name": "Status",  "value": s["status"],     "inline": True},
                        {"name": "Alert",   "value": s["alert_type"], "inline": True},
                        {"name": "Speed",   "value": f"{s['speed']} km/h", "inline": True},
                        {"name": "GPS",     "value": f"{s['latitude']}, {s['longitude']}", "inline": False},
                        {"name": "Maps",    "value": f"[View](https://maps.google.com/?q={s['latitude']},{s['longitude']})", "inline": False}
                    ]}]
    }
    try:
        http.post(wh, json=payload, timeout=6)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ── Reports ───────────────────────────────────────────────────────────────────
@app.route('/api/export_csv')
def export_csv():
    if os.path.exists(CSV_PATH):
        return send_file(CSV_PATH, mimetype='text/csv', as_attachment=True,
                         download_name='location_history.csv')
    return jsonify({"status": "error", "message": "No CSV yet"}), 404

@app.route('/api/generate_pdf', methods=['POST'])
def generate_pdf():
    try:
        generate_pdf_report(CSV_PATH, PDF_PATH)
        return jsonify({"status": "success", "download_url": "/api/download_pdf"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/download_pdf')
def download_pdf():
    if os.path.exists(PDF_PATH):
        return send_file(PDF_PATH, mimetype='application/pdf', as_attachment=True,
                         download_name='vehicle_tracking_report.pdf')
    return jsonify({"status": "error", "message": "Generate PDF first"}), 404

if __name__ == '__main__':
    os.makedirs("data", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    print("=" * 52)
    print("  IoT Vehicle Tracking System  ->  http://127.0.0.1:5000")
    print("=" * 52)
    app.run(debug=True, host='127.0.0.1', port=5000)
