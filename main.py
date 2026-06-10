"""
IoT Vehicle Tracking & Theft Prevention System — Flask Backend
Compatible with:  Render (gunicorn)  •  Vercel (@vercel/python)  •  local dev
"""
import os
import requests as http
from flask import Flask, jsonify, request, send_from_directory, send_file

from python_simulation.simulation_engine import VehicleSimulator, FleetManager
from python_simulation.report_generator import generate_pdf_report

# ── Environment detection ──────────────────────────────────────────────────────
# Vercel injects VERCEL=1 at runtime. Its filesystem is read-only except /tmp.
# Render and local dev have a writable working directory.
IS_VERCEL  = bool(os.environ.get("VERCEL"))
_WRITE_DIR = "/tmp" if IS_VERCEL else "."

DATA_DIR   = os.path.join(_WRITE_DIR, "data")
OUTPUT_DIR = os.path.join(_WRITE_DIR, "outputs")
CSV_PATH   = os.path.join(DATA_DIR, "location_history.csv")
PDF_PATH   = os.path.join(OUTPUT_DIR, "location_report.pdf")

# Absolute path to the dashboard folder — critical on Vercel where cwd is
# unpredictable inside the serverless function container.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_DASHBOARD    = os.path.join(_PROJECT_ROOT, "dashboard")

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=_DASHBOARD, static_url_path="")

# ── Settings (plain dict — no I/O, safe at module level) ─────────────────────
settings = {
    "telegram_token":   "",
    "telegram_chat_id": "",
    "discord_webhook":  "",
    "speed_limit":      80.0,
    "geofence_radius":  200.0,
    "voice_alerts":     True,
}

# ── Lazy initialisation ────────────────────────────────────────────────────────
# DO NOT instantiate VehicleSimulator or FleetManager at module level.
# Both call _ensure_log_file() → os.makedirs() + open() on import, which
# crashes Vercel's read-only filesystem before a single request is served.
# Instead, initialise on the first real request via these getters.

_simulator: VehicleSimulator | None = None
_fleet:     FleetManager     | None = None


def _ensure_dirs() -> None:
    """Create data/output dirs safely. /tmp is always writable; . is writable on Render."""
    try:
        os.makedirs(DATA_DIR,   exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    except OSError:
        pass  # Already exists or genuinely read-only — file writes will surface the real error


def get_simulator() -> VehicleSimulator:
    global _simulator
    if _simulator is None:
        _ensure_dirs()
        _simulator = VehicleSimulator(log_filepath=CSV_PATH)
    return _simulator


def get_fleet() -> FleetManager:
    global _fleet
    if _fleet is None:
        _ensure_dirs()
        _fleet = FleetManager(data_dir=DATA_DIR)
    return _fleet


# ── Static ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(_DASHBOARD, "index.html")


# ── Primary vehicle telemetry ──────────────────────────────────────────────────
@app.route("/api/telemetry")
def get_telemetry():
    try:
        return jsonify(get_simulator().update())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/set_mode", methods=["POST"])
def set_mode():
    try:
        mode = request.args.get("mode", "")
        vid  = request.args.get("vehicle_id", None)
        sim  = get_simulator()
        if vid and vid != sim.vehicle_id:
            get_fleet().set_mode(vid, mode)
        else:
            sim.set_mode(mode)
        return jsonify({"status": "success", "mode": mode})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Fleet ──────────────────────────────────────────────────────────────────────
@app.route("/api/fleet")
def get_fleet_data():
    try:
        return jsonify(get_fleet().update_all())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/fleet/set_mode", methods=["POST"])
def fleet_set_mode():
    try:
        data = request.get_json(force=True)
        get_fleet().set_mode(data.get("vehicle_id"), data.get("mode"))
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Analytics / Charts ─────────────────────────────────────────────────────────
@app.route("/api/analytics")
def analytics():
    try:
        rows   = get_simulator().get_history(60)
        speeds = [{"t": r["Timestamp"], "v": float(r.get("Speed_kmh",   0))}   for r in rows]
        fuel   = [{"t": r["Timestamp"], "v": float(r.get("Fuel_Level",  0))}   for r in rows]
        scores = [{"t": r["Timestamp"], "v": float(r.get("Driver_Score", 100))} for r in rows]
        counts: dict = {}
        for r in rows:
            a = r.get("Alert_Type", "None")
            if a != "None":
                counts[a] = counts.get(a, 0) + 1
        return jsonify({"speeds": speeds, "fuel": fuel, "driver_scores": scores,
                        "alert_counts": counts, "total": len(rows)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Route playback ─────────────────────────────────────────────────────────────
@app.route("/api/playback")
def playback():
    try:
        rows = get_simulator().get_history(100)
        path = [{"lat":       float(r.get("Latitude",   0)),
                 "lon":       float(r.get("Longitude",  0)),
                 "timestamp": r.get("Timestamp", ""),
                 "speed":     float(r.get("Speed_kmh",  0)),
                 "status":    r.get("Status", "")} for r in rows]
        return jsonify(path)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Geofence zones ─────────────────────────────────────────────────────────────
@app.route("/api/zones")
def get_zones():
    try:
        return jsonify(get_simulator().geofence_zones)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/zones/add", methods=["POST"])
def add_zone():
    try:
        d = request.get_json(force=True)
        sim = get_simulator()
        sim.add_geofence_zone(d["name"], d["lat"], d["lon"], d["radius"])
        return jsonify({"status": "ok", "zones": sim.geofence_zones})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/zones/clear", methods=["POST"])
def clear_zones():
    try:
        sim = get_simulator()
        sim.geofence_zones = [sim.geofence_zones[0]]
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Settings ───────────────────────────────────────────────────────────────────
@app.route("/api/settings", methods=["GET", "POST"])
def handle_settings():
    global settings
    try:
        if request.method == "POST":
            d = request.get_json(force=True)
            settings.update(d)
            sim = get_simulator()
            if "speed_limit"     in d: sim.set_speed_limit(d["speed_limit"])
            if "geofence_radius" in d: sim.set_geofence_radius(d["geofence_radius"])
            return jsonify({"status": "ok", "settings": settings})
        return jsonify(settings)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Telegram alert ─────────────────────────────────────────────────────────────
@app.route("/api/alert/telegram", methods=["POST"])
def send_telegram():
    token   = settings.get("telegram_token", "")
    chat_id = settings.get("telegram_chat_id", "")
    if not token or not chat_id:
        return jsonify({"status": "error", "message": "Telegram not configured"}), 400
    try:
        s   = get_simulator().update()
        msg = (f"\U0001f6a8 *VEHICLE ALERT*\n\n*Status:* {s['status']}\n*Alert:* {s['alert_type']}\n"
               f"*Speed:* {s['speed']} km/h\n*Location:* {s['latitude']}, {s['longitude']}\n"
               f"\U0001f5fa\ufe0f [Maps](https://maps.google.com/?q={s['latitude']},{s['longitude']})")
        r = http.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=6)
        return jsonify({"status": "ok", "response": r.json()})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ── Discord alert ──────────────────────────────────────────────────────────────
@app.route("/api/alert/discord", methods=["POST"])
def send_discord():
    wh = settings.get("discord_webhook", "")
    if not wh:
        return jsonify({"status": "error", "message": "Discord webhook not configured"}), 400
    try:
        s = get_simulator().update()
        payload = {
            "username": "TrackSafe IoT",
            "embeds": [{"title": "\U0001f6a8 Vehicle Security Alert", "color": 16711680,
                        "fields": [
                            {"name": "Status", "value": s["status"],     "inline": True},
                            {"name": "Alert",  "value": s["alert_type"], "inline": True},
                            {"name": "Speed",  "value": f"{s['speed']} km/h", "inline": True},
                            {"name": "GPS",    "value": f"{s['latitude']}, {s['longitude']}", "inline": False},
                            {"name": "Maps",   "value": f"[View](https://maps.google.com/?q={s['latitude']},{s['longitude']})", "inline": False},
                        ]}],
        }
        http.post(wh, json=payload, timeout=6)
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ── Reports ────────────────────────────────────────────────────────────────────
@app.route("/api/export_csv")
def export_csv():
    if os.path.exists(CSV_PATH):
        return send_file(CSV_PATH, mimetype="text/csv", as_attachment=True,
                         download_name="location_history.csv")
    return jsonify({"status": "error", "message": "No CSV data yet — trigger /api/telemetry first"}), 404


@app.route("/api/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        _ensure_dirs()
        generate_pdf_report(CSV_PATH, PDF_PATH)
        return jsonify({"status": "success", "download_url": "/api/download_pdf"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/download_pdf")
def download_pdf():
    if os.path.exists(PDF_PATH):
        return send_file(PDF_PATH, mimetype="application/pdf", as_attachment=True,
                         download_name="vehicle_tracking_report.pdf")
    return jsonify({"status": "error", "message": "Generate the PDF first via POST /api/generate_pdf"}), 404


# ── Dev server entry point ─────────────────────────────────────────────────────
# gunicorn/Vercel import this module directly — __main__ block is skipped.
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 54)
    print(f"  IoT Vehicle Tracking  →  http://127.0.0.1:{port}")
    print("=" * 54)
    app.run(debug=True, host="0.0.0.0", port=port)
