/* ═══════════════════════════════════════════════════════════
   TrackSafe IoT – app.js  (Complete Feature Set)
═══════════════════════════════════════════════════════════ */

// ── Constants ────────────────────────────────────────────
const GEO_CENTER  = [18.5204, 73.8567];
const TILE_URLS   = {
  street:    ['https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', '© OpenStreetMap'],
  satellite: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', '© Esri'],
  terrain:   ['https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', '© OpenTopoMap'],
  dark:      ['https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', '© CartoDB']
};

const QA = [
  ["Explain your project.","I built an IoT Vehicle Tracking & Theft Prevention System using ESP32, NEO-6M GPS, and SW-420 vibration sensor. It tracks location, monitors a geofence using the Haversine formula, and sounds alarms / cuts ignition on theft detection. A Python simulation engine mirrors all this in software with a Leaflet.js web dashboard."],
  ["What are NMEA sentences?","NMEA-0183 is the standard GPS output protocol. The $GPRMC sentence contains UTC time, status, latitude, longitude, and speed. The TinyGPS++ library parses raw UART byte streams into clean floating-point values."],
  ["How does Geofencing work?","A virtual circle is drawn around an anchor point. I use the Haversine formula to compute great-circle distance between current GPS coordinates and the center. If distance > radius, a Geofence Breach is flagged."],
  ["Why ESP32 over Arduino Uno?","ESP32 has built-in Wi-Fi & Bluetooth, 240 MHz dual-core CPU, 520 KB SRAM, and 3 hardware UARTs — all essential for concurrent GPS parsing, Wi-Fi upload, and sensor reading. The Uno has none of these."],
  ["How does the engine immobilizer work?","A 5V SPDT relay is placed in the ignition coil circuit using COM→NC wiring. When the ESP32 energizes the relay coil, the contact opens and cuts starter power. NC wiring ensures the engine stays startable if the ESP32 loses power (failsafe)."],
  ["How do logistics companies use tracking?","They monitor fleet location, optimize routes, calculate ETAs, detect idle time (reducing fuel costs), verify delivery completion, and alert dispatchers on route deviations or geofence exits — exactly what this system demonstrates."],
  ["How do you secure credentials in production?","Sensitive keys (Wi-Fi, API tokens) are stored in a separate config.h added to .gitignore. On production, a captive portal (WiFiManager library) lets users input credentials dynamically without hardcoding them in firmware."],
  ["What is MQTT vs HTTP in IoT?","HTTP is connectionless with large header overhead per request. MQTT maintains a persistent TCP connection to a broker with only 2-byte minimum headers — making it far more efficient for high-frequency GPS telemetry over metered cellular."],
  ["How do you handle GPS signal loss?","Check gps.location.isValid() before using data. If false, transmit last known coordinates with a 'Low Accuracy' flag. Production systems use dead reckoning (IMU + speed integration) or cell tower LBS triangulation as fallback."],
  ["How does the vibration sensor work?","The SW-420 has an internal spring. Vibration moves the spring, momentarily opening a contact. An LM393 comparator outputs a digital HIGH pulse. We read this on GPIO 25 and flag Theft Alarm if it occurs while ignition is OFF."]
];

// ── State ─────────────────────────────────────────────────
let map, vehicleMarker, geofenceCircle, tileLayer, trailLine, heatLayer;
let fleetMap, fleetMarkers = {};
let geoMap, geoZoneCircles = [];
let pbMap, pbMarker, pbPolyline;
let chartSpeed, chartFuel, chartScore, chartAlerts, heatMapInstance;
let pathCoords = [], pbPath = [], pbStep = 0, pbInterval = null;
let voiceEnabled = true, lastAlert = "None", lastSpoken = "";
let currentTile = 'street';

// ── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initMap();
  initInterviewCards();
  initControls();
  initSettings();
  initPlaybackModal();
  setInterval(pollTelemetry, 1000);
  setTimeout(initFleetMap, 500);
});

// ── Tab Navigation ────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      const tab = document.getElementById(btn.dataset.tab);
      tab.classList.add('active');
      if (btn.dataset.tab === 'tab-monitor' && map) setTimeout(() => map.invalidateSize(), 120);
      if (btn.dataset.tab === 'tab-fleet' && fleetMap) setTimeout(() => fleetMap.invalidateSize(), 120);
      if (btn.dataset.tab === 'tab-analytics') loadAnalytics();
      if (btn.dataset.tab === 'tab-geofence') { initGeoMap(); loadZones(); }
    });
  });
}

// ── Main Map ──────────────────────────────────────────────
function initMap() {
  map = L.map('map', { zoomControl: true }).setView(GEO_CENTER, 16);
  tileLayer = L.tileLayer(TILE_URLS.street[0], { attribution: TILE_URLS.street[1] }).addTo(map);

  L.circleMarker(GEO_CENTER, { radius: 6, color: '#10b981', fillColor: '#10b981', fillOpacity: .9 })
    .addTo(map).bindPopup('Home Base (Geofence Center)');

  geofenceCircle = L.circle(GEO_CENTER, { color: '#2563eb', fillColor: '#2563eb', fillOpacity: .08, radius: 200 }).addTo(map);

  vehicleMarker = L.marker(GEO_CENTER).addTo(map).bindPopup('Vehicle');
  trailLine = L.polyline([], { color: '#f59e0b', weight: 3, opacity: .7, dashArray: '5,5' }).addTo(map);

  heatLayer = L.heatLayer([], { radius: 25, blur: 15, maxZoom: 17 }).addTo(map);

  // Tile switcher
  document.querySelectorAll('.btn-map-tile').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.btn-map-tile').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTile = btn.dataset.tile;
      map.removeLayer(tileLayer);
      tileLayer = L.tileLayer(TILE_URLS[currentTile][0], { attribution: TILE_URLS[currentTile][1] }).addTo(map);
    });
  });
}

// ── Fleet Map ─────────────────────────────────────────────
function initFleetMap() {
  fleetMap = L.map('fleet-map').setView(GEO_CENTER, 15);
  L.tileLayer(TILE_URLS.dark[0], { attribution: TILE_URLS.dark[1] }).addTo(fleetMap);
  setInterval(updateFleet, 1500);
}

async function updateFleet() {
  try {
    const res = await fetch('/api/fleet');
    const vehicles = await res.json();
    const container = document.getElementById('fleet-cards');
    container.innerHTML = '';

    vehicles.forEach(v => {
      const pos = [v.latitude, v.longitude];
      const isAlert = v.alert_type !== 'None';
      const color = isAlert ? 'red' : (v.ignition ? 'green' : 'gray');

      // Map marker
      if (fleetMarkers[v.vehicle_id]) {
        fleetMarkers[v.vehicle_id].setLatLng(pos);
      } else {
        const icon = L.divIcon({ className: '', html: `<div style="width:12px;height:12px;background:${color === 'red' ? '#ef4444' : color === 'green' ? '#10b981' : '#6b7a99'};border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(0,0,0,.5)"></div>` });
        fleetMarkers[v.vehicle_id] = L.marker(pos, { icon }).addTo(fleetMap).bindPopup(v.vehicle_name);
      }

      // Card
      const alertClass = isAlert ? 'badge-off' : 'badge-on';
      const alertText  = isAlert ? v.alert_type : 'Secure';
      container.innerHTML += `
        <div class="fleet-card">
          <div class="fleet-card-hdr"><span class="fleet-vid">${v.vehicle_id}</span><i class="fa-solid fa-circle" style="color:${isAlert?'#ef4444':v.ignition?'#10b981':'#6b7a99'};font-size:9px"></i></div>
          <div class="fleet-name">${v.vehicle_name}</div>
          <div class="fleet-stat"><i class="fa-solid fa-gauge-high"></i> ${v.speed} km/h</div>
          <div class="fleet-stat"><i class="fa-solid fa-location-dot"></i> ${v.latitude}, ${v.longitude}</div>
          <div class="fleet-stat"><i class="fa-solid fa-road"></i> Trip: ${v.trip_distance} km</div>
          <span class="badge ${alertClass} fleet-alert-badge">${alertText}</span>
          <div class="fleet-ctrl">
            <button class="btn btn-secondary" onclick="setFleetMode('${v.vehicle_id}','driving')">Drive</button>
            <button class="btn btn-secondary" onclick="setFleetMode('${v.vehicle_id}','parked')">Park</button>
            <button class="btn btn-warn" onclick="setFleetMode('${v.vehicle_id}','stolen')">Stolen</button>
          </div>
        </div>`;
    });
  } catch(e) { /* fleet offline */ }
}

function setFleetMode(vid, mode) {
  fetch('/api/fleet/set_mode', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({vehicle_id: vid, mode}) });
}

// ── Telemetry Poll ────────────────────────────────────────
async function pollTelemetry() {
  try {
    const res = await fetch('/api/telemetry');
    const d = await res.json();
    updateUI(d);
  } catch(e) { /* server restarting */ }
}

function updateUI(d) {
  // Metrics
  setText('val-status', d.status);
  setText('val-speed', d.speed);
  setText('val-ts', `Updated: ${d.timestamp}`);
  setText('val-limit', d.speed_limit);
  setText('val-trip', d.trip_distance);
  setText('val-dscore', Math.round(d.driver_score));
  setText('val-brake', d.harsh_braking_events);
  setText('val-over', d.overspeed_events);
  setText('val-coords', `GPS: ${d.latitude}, ${d.longitude}`);
  setText('val-dist', `${d.distance_from_center}m from Home Base`);

  // Theft risk bar
  const riskPct = d.theft_risk_score;
  document.getElementById('risk-bar').style.width = riskPct + '%';
  setText('val-risk', riskPct + '%');
  setText('val-risk-lbl', riskPct < 30 ? 'Low Risk' : riskPct < 60 ? 'Medium Risk' : '🔴 HIGH RISK');

  // Alert
  const alertEl = document.getElementById('val-alert');
  if (d.alert_type !== 'None') {
    alertEl.textContent = d.alert_type;
    alertEl.className = 'mc-val text-red';
    if (d.alert_type !== lastAlert) {
      addLog(`CRITICAL: ${d.alert_type} @ [${d.latitude}, ${d.longitude}]`, 'alert');
      speakAlert(d.alert_type);
      lastAlert = d.alert_type;
    }
  } else {
    alertEl.textContent = 'Secure';
    alertEl.className = 'mc-val text-green';
    lastAlert = 'None';
  }

  // OBD-II
  setText('obd-fuel', d.fuel_level);
  document.getElementById('obd-fuel-bar').style.width = d.fuel_level + '%';
  setText('obd-batt', d.battery_voltage);
  setText('obd-rpm', d.engine_rpm.toLocaleString());
  setText('obd-temp', d.engine_temp);
  setText('obd-load', d.engine_load);
  setText('obd-head', d.heading + '°');

  // Badges
  setBadge('b-ign',   d.ignition,   'ON',     'OFF',    'badge-on', 'badge-off');
  setBadge('b-vib',   d.vibration,  'TAMPER', 'QUIET',  'badge-off','badge-ok');
  setBadge('b-relay', d.relay_locked,'OPEN',  'CLOSED', 'badge-off','badge-ok');
  setBadge('b-spd',   d.speed_alert,'ALERT',  'SAFE',   'badge-warn','badge-ok');

  // Immobilizer banner
  document.getElementById('imm-banner').classList.toggle('hidden', !d.relay_locked);
  document.getElementById('imm-toggle').checked = d.relay_locked;

  // Map
  const pos = [d.latitude, d.longitude];
  vehicleMarker.setLatLng(pos);
  geofenceCircle.setRadius(d.geofence_radius);

  if (d.status !== 'Parked') {
    map.panTo(pos);
    pathCoords.push(pos);
    if (pathCoords.length > 200) pathCoords.shift();
    trailLine.setLatLngs(pathCoords);
  } else if (pathCoords.length > 0 && d.status === 'Parked') {
    pathCoords = [];
    trailLine.setLatLngs([]);
  }

  // Heatmap
  if (d.alert_history && d.alert_history.length > 0) {
    heatLayer.setLatLngs(d.alert_history.map(p => [p[0], p[1], p[2]]));
  }
}

// ── Controls ──────────────────────────────────────────────
function initControls() {
  document.querySelectorAll('.btn-ctrl').forEach(btn => {
    btn.addEventListener('click', () => {
      fetch(`/api/set_mode?mode=${btn.dataset.mode}`, { method: 'POST' });
      document.querySelectorAll('.btn-ctrl').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      addLog(`Mode changed → ${btn.dataset.mode.toUpperCase()}`, 'info');
    });
  });

  document.getElementById('imm-toggle').addEventListener('change', e => {
    const mode = e.target.checked ? 'immobilize' : 'reset_immobilize';
    fetch(`/api/set_mode?mode=${mode}`, { method: 'POST' });
    addLog(e.target.checked ? 'ENGINE IMMOBILIZED via remote relay.' : 'Engine lock released.', e.target.checked ? 'alert' : 'info');
  });

  document.getElementById('btn-tg').addEventListener('click', async () => {
    const r = await fetch('/api/alert/telegram', { method: 'POST' });
    const d = await r.json();
    addLog(d.status === 'ok' ? 'Telegram alert sent!' : 'Telegram: ' + d.message, d.status === 'ok' ? 'info' : 'alert');
  });

  document.getElementById('btn-dc').addEventListener('click', async () => {
    const r = await fetch('/api/alert/discord', { method: 'POST' });
    const d = await r.json();
    addLog(d.status === 'ok' ? 'Discord alert sent!' : 'Discord: ' + d.message, d.status === 'ok' ? 'info' : 'alert');
  });

  document.getElementById('btn-export-csv').addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = '/api/export_csv';
    a.download = 'location_history.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  });

  document.getElementById('btn-pdf').addEventListener('click', async () => {
    addLog('Generating PDF report…', 'info');
    const r = await fetch('/api/generate_pdf', { method: 'POST' });
    const d = await r.json();
    if (d.status === 'success') {
      addLog('PDF ready! Downloading…', 'info');
      const a = document.createElement('a');
      a.href = d.download_url;
      a.download = 'vehicle_tracking_report.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
    else addLog('PDF error: ' + d.message, 'alert');
  });

  document.getElementById('btn-theme').addEventListener('click', () => {
    const html = document.documentElement;
    html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
  });

  document.getElementById('btn-voice').addEventListener('click', () => {
    voiceEnabled = !voiceEnabled;
    document.getElementById('dot-voice').style.background = voiceEnabled ? 'var(--blue)' : '#6b7a99';
    addLog(`Voice alerts ${voiceEnabled ? 'enabled' : 'disabled'}.`, 'info');
  });
}

// ── Settings ──────────────────────────────────────────────
function initSettings() {
  const sl = document.getElementById('s-speed-limit');
  const gr = document.getElementById('s-geo-radius');
  sl.addEventListener('input', () => setText('s-speed-val', sl.value + ' km/h'));
  gr.addEventListener('input', () => setText('s-geo-val', gr.value + ' m'));

  document.getElementById('btn-save-settings').addEventListener('click', async () => {
    const payload = {
      speed_limit:      parseFloat(sl.value),
      geofence_radius:  parseFloat(gr.value),
      telegram_token:   document.getElementById('s-tg-token').value.trim(),
      telegram_chat_id: document.getElementById('s-tg-chat').value.trim(),
      discord_webhook:  document.getElementById('s-discord').value.trim(),
      voice_alerts:     document.getElementById('s-voice').checked
    };
    voiceEnabled = payload.voice_alerts;
    await fetch('/api/settings', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const fb = document.getElementById('save-feedback');
    fb.classList.remove('hidden');
    setTimeout(() => fb.classList.add('hidden'), 3000);
    addLog('Settings saved and applied to simulator.', 'info');
  });
}

// ── Analytics Charts ──────────────────────────────────────
async function loadAnalytics() {
  const res = await fetch('/api/analytics');
  const d   = await res.json();

  const labels = d.speeds.map(p => p.t.split(' ')[1] || p.t);
  const cfg    = (label, data, color) => ({
    type: 'line', data: { labels, datasets: [{ label, data, borderColor: color, backgroundColor: color+'22', tension: .35, pointRadius: 2, fill: true }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { maxTicksLimit: 8, color: '#6b7a99' }, grid: { color: '#ffffff0a' } }, y: { ticks: { color: '#6b7a99' }, grid: { color: '#ffffff0a' } } } }
  });

  if (chartSpeed)  chartSpeed.destroy();
  if (chartFuel)   chartFuel.destroy();
  if (chartScore)  chartScore.destroy();
  if (chartAlerts) chartAlerts.destroy();

  chartSpeed  = new Chart(document.getElementById('chart-speed'),  cfg('Speed (km/h)', d.speeds.map(p=>p.v), '#2563eb'));
  chartFuel   = new Chart(document.getElementById('chart-fuel'),   cfg('Fuel %',       d.fuel.map(p=>p.v),   '#10b981'));
  chartScore  = new Chart(document.getElementById('chart-score'),  cfg('Driver Score', d.driver_scores.map(p=>p.v), '#a855f7'));

  const alertLabels = Object.keys(d.alert_counts);
  chartAlerts = new Chart(document.getElementById('chart-alerts'), {
    type: 'doughnut',
    data: { labels: alertLabels, datasets: [{ data: Object.values(d.alert_counts), backgroundColor: ['#ef4444','#f59e0b','#3b82f6','#10b981','#a855f7'] }] },
    options: { responsive: true, plugins: { legend: { labels: { color: '#94a3b8' } } } }
  });

  // Heatmap via Leaflet
  if (!heatMapInstance) {
    heatMapInstance = L.map('heat-map').setView(GEO_CENTER, 15);
    L.tileLayer(TILE_URLS.dark[0], { attribution: '' }).addTo(heatMapInstance);
  }

  const res2 = await fetch('/api/telemetry');
  const td   = await res2.json();
  if (td.alert_history && td.alert_history.length > 0) {
    L.heatLayer(td.alert_history.map(p => [p[0],p[1],p[2]]), { radius: 28 }).addTo(heatMapInstance);
  }
  setTimeout(() => heatMapInstance.invalidateSize(), 100);

  document.getElementById('btn-refresh-charts').addEventListener('click', loadAnalytics);
}

// ── Geofence Manager ──────────────────────────────────────
function initGeoMap() {
  if (geoMap) return;
  geoMap = L.map('geo-map').setView(GEO_CENTER, 15);
  L.tileLayer(TILE_URLS.street[0], { attribution: TILE_URLS.street[1] }).addTo(geoMap);
  setTimeout(() => geoMap.invalidateSize(), 150);

  document.getElementById('btn-add-zone').addEventListener('click', async () => {
    const name   = document.getElementById('zone-name').value.trim() || 'Zone';
    const lat    = parseFloat(document.getElementById('zone-lat').value) || GEO_CENTER[0];
    const lon    = parseFloat(document.getElementById('zone-lon').value) || GEO_CENTER[1];
    const radius = parseFloat(document.getElementById('zone-rad').value) || 150;
    await fetch('/api/zones/add', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name, lat, lon, radius}) });
    loadZones();
  });

  document.getElementById('btn-clear-zones').addEventListener('click', async () => {
    await fetch('/api/zones/clear', { method: 'POST' });
    loadZones();
  });
}

async function loadZones() {
  const res = await fetch('/api/zones');
  const zones = await res.json();

  geoZoneCircles.forEach(c => geoMap.removeLayer(c));
  geoZoneCircles = [];

  const list = document.getElementById('zone-list');
  list.innerHTML = '';

  const colors = ['#2563eb','#10b981','#f59e0b','#a855f7','#ef4444'];
  zones.forEach((z, i) => {
    const c = L.circle([z.lat, z.lon], { color: colors[i%5], fillColor: colors[i%5], fillOpacity: .1, radius: z.radius }).addTo(geoMap).bindPopup(z.name);
    L.circleMarker([z.lat, z.lon], { radius: 5, color: colors[i%5], fillColor: colors[i%5], fillOpacity: .9 }).addTo(geoMap);
    geoZoneCircles.push(c);
    list.innerHTML += `<div class="zone-item"><strong>${z.name}</strong><span>${z.lat}, ${z.lon} — ${z.radius}m</span></div>`;
  });
}

// ── Route Playback ────────────────────────────────────────
function initPlaybackModal() {
  document.getElementById('btn-playback').addEventListener('click', async () => {
    document.getElementById('playback-modal').classList.remove('hidden');
    const res = await fetch('/api/playback');
    pbPath = await res.json();
    if (!pbMap) {
      pbMap = L.map('pb-map').setView(GEO_CENTER, 15);
      L.tileLayer(TILE_URLS.street[0], { attribution: '' }).addTo(pbMap);
      pbPolyline = L.polyline([], { color: '#f59e0b', weight: 3 }).addTo(pbMap);
      pbMarker   = L.marker(GEO_CENTER).addTo(pbMap);
    }
    pbStep = 0; pbPolyline.setLatLngs([]);
    setTimeout(() => pbMap.invalidateSize(), 100);
    setText('pb-info', `Step 0 / ${pbPath.length}`);
  });

  document.getElementById('pb-close').addEventListener('click', () => {
    document.getElementById('playback-modal').classList.add('hidden');
    clearInterval(pbInterval);
  });

  document.getElementById('pb-play').addEventListener('click', () => {
    clearInterval(pbInterval);
    pbInterval = setInterval(() => {
      if (pbStep >= pbPath.length) { clearInterval(pbInterval); return; }
      const pt = pbPath[pbStep];
      const pos = [pt.lat, pt.lon];
      pbMarker.setLatLng(pos);
      pbPolyline.addLatLng(pos);
      pbMap.panTo(pos);
      setText('pb-info', `Step ${pbStep+1} / ${pbPath.length} | ${pt.speed} km/h | ${pt.status}`);
      pbStep++;
    }, 300);
  });

  document.getElementById('pb-reset').addEventListener('click', () => {
    clearInterval(pbInterval);
    pbStep = 0; pbPolyline.setLatLngs([]);
    if (pbPath.length) pbMarker.setLatLng([pbPath[0].lat, pbPath[0].lon]);
    setText('pb-info', `Step 0 / ${pbPath.length}`);
  });
}

// ── Interview Flip Cards ───────────────────────────────────
function initInterviewCards() {
  const grid = document.getElementById('flip-grid');
  QA.forEach(([q, a], i) => {
    grid.innerHTML += `
      <div class="flip-card" onclick="this.classList.toggle('flipped')">
        <div class="flip-inner">
          <div class="flip-front">
            <span class="card-no">Q${String(i+1).padStart(2,'0')}</span>
            <h4>${q}</h4>
            <span class="flip-hint"><i class="fa-solid fa-arrows-rotate"></i> Click to reveal</span>
          </div>
          <div class="flip-back">
            <h4>Model Answer</h4>
            <p>${a}</p>
          </div>
        </div>
      </div>`;
  });
}

// ── Voice Alerts (Web Speech API) ─────────────────────────
function speakAlert(text) {
  if (!voiceEnabled || !window.speechSynthesis) return;
  if (text === lastSpoken) return;
  lastSpoken = text;
  const utt = new SpeechSynthesisUtterance('Vehicle alert: ' + text);
  utt.rate = .95; utt.pitch = 1.1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utt);
}

// ── Helpers ───────────────────────────────────────────────
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

function setBadge(id, condition, trueText, falseText, trueClass, falseClass) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = condition ? trueText : falseText;
  el.className = 'badge ' + (condition ? trueClass : falseClass);
}

function addLog(msg, type = 'info') {
  const list = document.getElementById('log-list');
  const t    = new Date().toTimeString().slice(0, 8);
  const item = document.createElement('div');
  item.className = `log-item ${type}`;
  item.innerHTML = `<span class="ltime">${t}</span><span>${msg}</span>`;
  list.insertBefore(item, list.firstChild);
  if (list.children.length > 40) list.removeChild(list.lastChild);
}
