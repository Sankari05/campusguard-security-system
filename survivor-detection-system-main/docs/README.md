# RIDGEWATCH — AI-Based Multi-Sensor Survivor Detection & Rescue Prioritization System

**System Design & Implementation Documentation**

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Project Structure](#3-project-structure)
4. [Running the System](#4-running-the-system)
5. [The Fusion & Triage Algorithm](#5-the-fusion--triage-algorithm)
6. [Rescue Dispatch Simulation](#6-rescue-dispatch-simulation)
7. [Data Persistence](#7-data-persistence)
8. [API Reference](#8-api-reference)
9. [Scenario Configuration](#9-scenario-configuration)
10. [Testing](#10-testing)
11. [Design Rationale & Limitations](#11-design-rationale--limitations)
12. [Rescue Team Wearable Safety Protocol](#12-rescue-team-wearable-safety-protocol)

---

## 1. Overview

RIDGEWATCH is a simulated disaster-response decision-support system. It models a
search-and-rescue (SAR) field deployment in which a network of multi-sensor nodes
scans a debris field (avalanche, collapsed building, or flood zone) for signs of
life, fuses the raw sensor data into a single confidence score per victim,
classifies each victim into a triage class, and produces a prioritized rescue
queue that a simulated rescue team physically works through.

The project is split into three cooperating layers:

- **Backend** (`backend/`) — a Python/FastAPI service that simulates sensors,
  runs the fusion/triage engine, simulates rescue-team dispatch, and persists
  every run to SQLite for later analysis.
- **Frontend** (`frontend/`) — a static, framework-free HTML/CSS/JS dashboard
  ("RIDGEWATCH console") that polls the backend and visualizes victims, the
  triage queue, and rescue team movement in real time.
- **Tests** (`tests/`) — a pytest suite covering the fusion engine, triage
  ordering, REST API, dispatch simulation, and database logging.

This document is written to be dropped directly into a final-year project
report's **System Design** chapter.

---

## 2. System Architecture

### 2.1 High-level component diagram

```
                         ┌───────────────────────────────┐
                         │        Frontend (SPA)          │
                         │  index.html + dashboard.js     │
                         │  (vanilla JS, fetch() polling)  │
                         └───────────────┬─────────────────┘
                                         │ HTTP / JSON (REST, CORS: *)
                                         ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │                        Backend — FastAPI app (api.py)               │
 │                                                                      │
 │   ┌───────────────┐   ┌────────────────┐   ┌──────────────────┐   │
 │   │ scenario_      │──▶│ ScenarioState  │◀──│ sensor_simulator │   │
 │   │ loader.py      │   │ (in-memory)    │   │ .py              │   │
 │   │ (JSON configs) │   └───────┬────────┘   └──────────────────┘   │
 │   └───────────────┘           │                                    │
 │                                ▼                                    │
 │                        ┌────────────────┐                          │
 │                        │ fusion_engine  │                          │
 │                        │ .py            │                          │
 │                        └───────┬────────┘                          │
 │                                ▼                                    │
 │                        ┌────────────────┐   ┌───────────────────┐ │
 │                        │ rescue_dispatch│   │ db.py (SQLite)     │ │
 │                        │ .py            │──▶│ sessions,          │ │
 │                        └────────────────┘   │ sensor_readings,   │ │
 │                                              │ detection_results, │ │
 │                                              │ rescue_status_     │ │
 │                                              │ events             │ │
 │                                              └───────────────────┘ │
 └────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data flow (one polling cycle)

1. The frontend calls `GET /victims` (or `/queue`) on a timer (default: every
   4 s).
2. `api.py` advances the running scenario by one **sensor cycle**
   (`ScenarioState.tick()`), which asks `sensor_simulator.py` to generate one
   new reading per sensor type (thermal, PIR motion, acoustic, CO2,
   heart-rate radar, RGB camera, kit-level IMU tilt, kit-level IMU
   vibration — plus water level/flow when the scenario enables them) for
   every victim in the active scenario.
3. New readings are appended to a short rolling history buffer (3 cycles ×
   sensors per victim, for temporal smoothing).
4. `fusion_engine.py` fuses the buffered readings for each victim into a
   `FusionResult`: a **Confidence %**, a **triage class**, and a
   hazard-adjusted **Survivor Priority Score (SPS)**.
5. Every cycle's raw readings and fused results are persisted to SQLite via
   `db.py` (`log_detection_cycle`), keyed by the current scenario's
   `session_id`.
6. `rank_victims()` sorts all victims into the final priority queue, which is
   what `GET /queue` and the rescue-team logic both consume.
7. `rescue_dispatch.py`'s single-agent simulation walks that queue in order
   (`POST /rescue-team/advance`), and `api.py`'s simple multi-team
   auto-dispatch logic assigns idle ALPHA/BRAVO-style teams to the
   highest-priority unrescued victims (`GET /rescue-team/status`).
8. The dashboard renders victim cards, the priority queue, sensor readings,
   and rescue-team markers from the JSON responses.

### 2.3 Design principle: sensor evidence vs. operational urgency

A deliberate architectural separation runs through the whole system:

- **Medical triage class** (`HIGH` / `MEDIUM` / `LOW` / `NO_VITAL_SIGNS` /
  `SAFE`) is derived **only** from fused sensor evidence (Confidence %) plus
  discrete signal patterns like deliberate tapping. It never looks at
  situational hazard.
- **Operational urgency** (SPS — Survivor Priority Score) additionally
  factors in **hazard context** (burial depth, secondary-collapse/avalanche
  risk, prolonged exposure time). Hazard changes *where within/across
  classes* a victim is queued, but never reclassifies their medical status.

This mirrors real SAR doctrine: a marginal-but-survivable victim in a highly
unstable location is moved up the queue relative to an equally-classified
victim in a safer spot, without pretending the sensor evidence itself
changed.

---

## 3. Project Structure

```
survivor_detection_system/
├── requirements.txt
├── backend/
│   ├── api.py                 # FastAPI app: REST endpoints, scenario state
│   ├── models.py               # Shared dataclasses/enums (SensorReading,
│   │                            #   VictimProfile, DetectionResult, ...)
│   ├── fusion_engine.py        # Sensor fusion + triage classification + SPS
│   ├── sensor_simulator.py     # Synthetic sensor data generator (per victim)
│   ├── rescue_dispatch.py      # Single-agent dispatch walk simulation
│   ├── scenario_loader.py      # Loads backend/scenarios/*.json configs
│   ├── db.py                   # SQLite persistence + CSV export
│   └── scenarios/
│       ├── himalaya_avalanche.json
│       ├── earthquake_building_collapse.json
│       └── flood_urban.json
├── frontend/
│   ├── index.html              # RIDGEWATCH console markup
│   ├── css/style.css
│   ├── js/dashboard.js         # Polls the API, renders the console
│   └── assets/
├── tests/
│   ├── conftest.py             # Shared pytest fixtures
│   ├── test_fusion_engine.py            # Core fusion/triage test matrix
│   ├── test_fusion_engine_edge_cases.py # Boundary/clamping/averaging edge cases
│   ├── test_triage_queue_ordering.py    # Doctrine ordering, randomized + via API
│   ├── test_api.py / test_api_edge_cases.py     # REST endpoint behavior
│   ├── test_rescue_dispatch.py / test_dispatch_edge_cases.py
│   ├── test_db.py / test_db_logging_integrity.py
│   └── demo_sensor_simulator.py
├── data/                        # (runtime) SQLite DB file lives under backend/
└── docs/
    └── README.md                 # This document
```

---

## 4. Running the System

### 4.1 Requirements

- Python 3.10+
- Packages listed in `requirements.txt`:
  `fastapi`, `uvicorn[standard]`, `pydantic`, `httpx`

Install once:

```bash
pip install -r requirements.txt
```

(For running the test suite, also install `pytest`: `pip install pytest`.)

### 4.2 Running the backend

From the project root:

```bash
cd backend
python api.py
```

or equivalently, with auto-reload during development:

```bash
cd backend
uvicorn api:app --reload --port 8000
```

This starts the FastAPI server on `http://localhost:8000`. On first import,
`db.init_db()` creates (or migrates) the SQLite schema at
`backend/survivor_detection.db` automatically — no manual setup step needed.

The interactive OpenAPI docs are available at `http://localhost:8000/docs`
once the server is running (auto-generated by FastAPI from the same route
definitions listed in [Section 8](#8-api-reference)).

**Starting a scenario:** the API serves no victim data until a scenario is
explicitly started:

```bash
curl -X POST http://localhost:8000/scenario/start \
  -H "Content-Type: application/json" \
  -d '{"scenario": "himalaya_avalanche", "seed": 42, "enable_degradation": true}'
```

### 4.3 Running the frontend

The frontend is a static site with no build step. Two options:

**Option A — open directly:**
Open `frontend/index.html` in a browser. Click the **API** button in the top
bar and confirm the backend URL (defaults to `http://localhost:8000`).

**Option B — serve it (recommended, avoids `file://` fetch quirks):**

```bash
cd frontend
python -m http.server 5500
```

Then browse to `http://localhost:5500`. The backend's CORS policy already
allows all origins for local development, so no extra configuration is
needed.

Once both are running: pick a scenario in the dropdown, click **Start
Scenario**, and the console begins polling `/victims`, `/queue`, and
`/rescue-team/status` on a 4-second interval, rendering live sensor readings,
the triage queue, and rescue-team movement.

### 4.4 Exporting a session log

Every scenario run is logged to SQLite. To list sessions and export one as
CSV (readings + fused results + rescue events, chronologically merged):

```bash
curl http://localhost:8000/sessions
curl http://localhost:8000/sessions/<session_id>/export.csv -o session_log.csv
```

This CSV is well suited for the report's evaluation chapter (e.g. plotting
confidence over time, verifying triage-to-SPS relationships, or auditing
rescue arrival order against expected doctrine).

---

## 5. The Fusion & Triage Algorithm

Implemented entirely in `backend/fusion_engine.py`.

### 5.1 Pipeline overview

```
 SensorReading[] (per victim, per cycle)
        │
        ▼
 ① Average same-type readings across the smoothing window
        │
        ▼
 ② Normalize each sensor's raw value to a 0.0–1.0 sub-score
        │
        ▼
 ③ Weighted-sum the sub-scores → raw fused score (0.0–1.0)
        │
        ▼
 ④ Multiply by measurement reliability → Confidence % (0–100)
        │
        ▼
 ⑤ Rule-based classification → Triage Class
        │
        ▼
 ⑥ Confidence % × Hazard Multiplier → Survivor Priority Score (SPS)
        │
        ▼
 ⑦ rank_victims(): sort by (triage doctrine order, −SPS)
```

### 5.2 Step 1–2: per-sensor scoring

Each of the six sensor channels is normalized independently against a
physiologically-motivated reference range (**not** tuned to any specific
victim's known ground truth — a real detector only has sensor data, not the
answer key):

| Sensor | Raw unit | Normalization |
|---|---|---|
| Heart-rate radar | bpm | `0` below a 15 bpm noise floor; linearly scaled to `1.0` over a 60 bpm span above the floor |
| Thermal imaging | °C | `(temp − ambient) / (body_normal − ambient)`, floored to `0` below a small threshold (treated as "no heat above ambient snow/rubble") |
| Acoustic | dB + motion | `max(normalized dB, normalized PIR motion)` — either a clear sound or clear movement counts |
| CO2 | ppm | Linearly scaled above the ~410 ppm ambient baseline |
| RGB camera | 0–1 confidence | Used directly (already normalized) |

All sub-scores are clamped to `[0.0, 1.0]`.

### 5.3 Step 3–4: weighted fusion and reliability

```python
raw_fused = 0.35·radar + 0.25·thermal + 0.25·acoustic + 0.10·co2 + 0.05·camera
reliability = mean(sensor.confidence for each contributing sensor)
confidence_pct = 100 · raw_fused · reliability
```

`reliability` is the average **self-reported signal quality** across the
contributing sensors (fed by battery/degradation modeling in
`sensor_simulator.py`). This means a technically "strong" reading from a
nearly-dead battery is trusted less than the same reading from a fresh unit
— a deliberately realistic touch, since field sensor nodes degrade over a
mission.

### 5.4 Step 5: triage classification

```python
if visually_confirmed_safe:            # camera + motion + near-normal body temp
    → SAFE
elif tapping_detected and confidence_pct >= 15%:
    → HIGH        # deliberate signaling overrides a weak baseline
elif confidence_pct >= 30%:
    → HIGH
elif confidence_pct >= 15%:
    → MEDIUM
elif confidence_pct >= 5%:
    → LOW
else:
    → NO_VITAL_SIGNS
```

`tapping_detected` fires when acoustic level exceeds an audible
tapping/calling threshold **or** PIR motion exceeds a deliberate-movement
threshold — this lets a conscious, signaling victim reach `HIGH` even if
their other vitals (e.g. body temperature under snow) look weak.

`visually_confirmed_safe` (clear camera detection + ambulatory motion +
near-normal body temperature) always wins, even over tapping — a victim who
is clearly seen moving under their own power doesn't need urgent extraction
regardless of how loud they are.

### 5.5 Step 6: hazard-adjusted Survivor Priority Score (SPS)

```python
hazard_multiplier = 1.0
    + up to 0.15  (burial depth, saturating at 3 m)
    + 0.30 flat   (if a secondary hazard is present, e.g. active avalanche path)
    + up to 0.10  (exposure time, saturating at 240 minutes)
    + ...         (water level/rise/flow, rain, soil-saturation/landslide coupling,
                   seismic vibration + aftershock/soil compound, ground tilt)
    + up to 0.20  (cold exposure — ambient temperature at/below 5°C, saturating at -20°C)
    + up to 0.20  (heat + humidity, compound — only when ambient temp ≥ 32°C
                   AND relative humidity ≥ 70% simultaneously; heat alone or
                   humidity alone adds nothing)
    + 0.10 flat   (kit-level IMU disturbance — this victim's own kit
                   registered a fresh tilt shift or vibration spike this cycle)
sps = confidence_pct × hazard_multiplier
```

Cold exposure and heat/humidity are both **site-wide** environmental readings
(one shared thermometer/hygrometer for the whole disaster zone, not a
per-victim sensor — see `GET /environment`), the same category as rain,
soil saturation, seismic vibration, and tilt above. Cold is an uncoupled
bonus like rain: every degree below the threshold raises hypothermia-risk
urgency. Heat is deliberately **not** a bonus on its own — it's heat
*combined with* high humidity (poor evaporative cooling, heat-stroke and
dehydration risk) that raises urgency, so it's gated on both crossing
their thresholds together, mirroring the aftershock/soil compound bonus.
See `fusion_engine.py`'s `HazardContext.multiplier()` for the authoritative,
fully-commented list of every hazard term and its constants.

**Kit-level IMU vs. the site-wide seismic/tilt sensors — don't confuse
these.** `GET /seismic` and `GET /tilt` (and the `vibration_mm_s`/`tilt_deg`
fields on `HazardContext`) come from a single shared inclinometer/vibration
sensor for the *whole site*: "the slope or structure itself is moving."
The kit-level IMU is a completely different reading — a small
accelerometer/inclinometer inside *each victim's own* sensor kit, exposed
per-victim as the `imu_tilt`/`imu_vibration` entries in `GET /victims`'
`sensors` dict (see `SensorSimulator.imu_report()`), and folded into
`HazardContext.kit_disturbed`. A kit_disturbed=True flag on `HazardContext`
means "this one unit just got knocked or shaken" — debris settling, an
animal, a rescuer nearby, or the victim moving it themselves — not "the
whole slope is moving." That's why the kit bonus (`KIT_IMU_RISK_BONUS`,
0.10) is deliberately smaller than `VIBRATION_RISK_MAX_BONUS` (0.20) or
`TILT_RISK_MAX_BONUS` (0.30), and why — unlike the site-wide tilt bonus —
it is **not** gated on `secondary_hazard`: it's a noisier, more localized
signal, not a confirmed slope/structure failure. `kit_disturbed` is also a
one-shot flag, true only on the exact cycle a fresh shift/spike fires
(mirroring how `shift_detected`/`aftershock_active` behave site-wide), not
a sustained state.

Hazard context **never** changes `triage_class` — only `sps`, which
determines ordering *within and across* classes.

### 5.6 Step 7: the priority queue

```python
TRIAGE_DOCTRINE_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2, NO_VITAL_SIGNS: 3, SAFE: 4}

rank_victims(results) = sorted(results, key=lambda r: (doctrine_order[r.triage_class], −r.sps))
```

In words: **urgent survivable cases (HIGH → MEDIUM → LOW) are always
dispatched before confirmed-fatality recovery (`NO_VITAL_SIGNS`), which is
in turn before safe/self-evacuating victims (`SAFE`, always last)**. Within
a tied class, higher hazard-adjusted SPS goes first.

---

## 6. Rescue Dispatch Simulation

Implemented in `backend/rescue_dispatch.py`, exposed via `GET
/rescue-team/status` and `POST /rescue-team/advance`.

A single simulated team (`RescueDispatchAgent`) walks the current priority
queue one victim at a time:

- **Movement model:** constant-speed, straight-line (great-circle) travel
  between the team's current position and its current target, using the
  haversine formula (`haversine_distance_m`). Default speed is `0.6 m/s`,
  deliberately slow to reflect movement over broken snowpack/rubble rather
  than open ground.
- **Stepping:** each call to `POST /rescue-team/advance` moves the simulated
  clock forward by `seconds × steps` (defaults: 60 s × 1 step). If a leg
  completes within that step, the team snaps exactly to the victim's
  coordinates, the victim is marked `reached` with a UTC timestamp, and a
  `DispatchLogEntry` (arrival order + travel time) is returned. Otherwise the
  team's position moves partway along the leg and the call returns no
  arrival.
- **Live re-prioritization:** every call re-loads the agent's target list
  from the *current* `/queue` order before advancing. If priorities shift
  between calls (e.g. a victim's confidence rose or hazard changed), the
  still-pending leg of the walk retargets accordingly — mirroring how a real
  team would re-triage on the move. Already-reached victims are never
  revisited even if they reappear in the reloaded queue.

Independently, `api.py`'s `_auto_dispatch()` assigns idle named teams
(e.g. ALPHA/BRAVO, defined per-scenario) to the highest-priority
**unassigned survivable** victims (`HIGH`/`MEDIUM`/`LOW` only —
`NO_VITAL_SIGNS` and `SAFE` are never auto-dispatched a live-rescue team)
each time `/rescue-team/status` is polled, giving each team an ETA estimate.
This is a simpler, separate mechanism from the single-agent walk simulation
above, representing dispatch *assignment* rather than a physical walk
trace.

---

## 7. Data Persistence

Implemented in `backend/db.py` — a lightweight SQLite layer, one short-lived
connection per call (appropriate for this simulated, low-throughput
workload).

**Schema:**

| Table | Purpose | Key columns |
|---|---|---|
| `sessions` | One row per `POST /scenario/start` | `session_id`, `started_at`, `seed`, `enable_degradation`, `victim_count`, `scenario_id`, `scenario_name` |
| `sensor_readings` | One row per raw sensor reading, every cycle | `session_id`, `cycle`, `victim_id`, `sensor_type`, `value`, `sensor_confidence`, `noisy` |
| `detection_results` | One row per victim per cycle (fused output) | `confidence_pct`, `triage_class`, `sps`, `hazard_multiplier`, `tapping_detected`, `contributing_sensors` |
| `rescue_status_events` | Team-dispatch assignments and dispatch-agent arrivals | `event_type` (`team_dispatched` \| `victim_reached`), `team_id`, `victim_id`, `eta_minutes`, `arrival_order`, `travel_seconds` |

`export_session_csv(session_id)` merges all three tables for a session into
a single chronologically-ordered CSV (`record_type` column disambiguates the
source table), suitable for direct import into spreadsheet or plotting tools
for the report's evaluation chapter.

---

## 8. API Reference

Base URL: `http://localhost:8000` (default). All responses are JSON unless
noted otherwise.

### `GET /health`
Liveness check.
**Response:** `{"status": "ok", "time": "<ISO-8601 UTC>"}`

### `GET /scenarios`
List every available scenario config found under `backend/scenarios/*.json`.
**Response:** `{"scenarios": [{"scenario_id", "name", "description", "site_label", "victim_count"}, ...]}`

### `POST /scenario/start`
Start (or restart) a scenario.
**Body:**
```json
{ "scenario": "himalaya_avalanche", "seed": 42, "enable_degradation": true }
```
All fields optional (defaults: `himalaya_avalanche`, random seed, degradation on).
**Response:** `{"status": "started", ...scenario_meta}`
**Errors:** `404` unknown `scenario`; `422` malformed scenario config file.

### `POST /scenario/reset`
Reset to initial (not-running) state. Does not delete logged history.
**Response:** `{"status": "reset", ...scenario_meta}`

### `GET /victims`
Advances the simulation by one sensor cycle and returns current sensor +
fusion state for every victim.
**Response:**
```json
{
  "scenario": { "running": true, "cycle": 3, "scenario_id": "himalaya_avalanche", ... },
  "victims": [
    {
      "victim_id": "V2",
      "location": { "latitude": 0, "longitude": 0, "altitude_m": 0 },
      "sensors": {
        "heart_rate_radar": { "value": 42.1, "unit": "bpm", "confidence": 0.9, "noisy": false, "timestamp": "..." },
        "imu_tilt": { "value": 0.08, "unit": "deg", "confidence": 0.9, "noisy": false, "timestamp": "..." },
        "imu_vibration": { "value": 0.03, "unit": "g", "confidence": 0.9, "noisy": false, "timestamp": "..." }
      },
      "sensor_node_online": true,
      "kit_disturbed": false,
      "fusion": {
        "confidence_pct": 27.4, "triage_class": "MEDIUM", "sps": 27.4,
        "hazard_multiplier": 1.0, "tapping_detected": false,
        "score_breakdown": { "heart_rate_radar": 0.45 },
        "contributing_sensors": ["heart_rate_radar", "thermal_imaging"],
        "notes": "Probable life signs, moderate confidence."
      }
    }
  ]
}
```
`imu_tilt`/`imu_vibration` are this victim's own kit-level IMU readings
(always present, unlike the conditionally-gated `water_level`/`water_flow`
keys) — see [Section 5.5](#55-step-6-hazard-adjusted-survivor-priority-score-sps)
for how these differ from the site-wide `/seismic`/`/tilt` sensors.
`kit_disturbed` is `true` only on the exact cycle this victim's kit
registers a fresh tilt shift or vibration spike.
**Errors:** `409` if no scenario is running.

### `GET /queue`
Advances the simulation by one cycle and returns the ranked triage priority
queue (see [Section 5.6](#56-step-7-the-priority-queue)).
**Response:**
```json
{
  "scenario": {},
  "queue": [
    { "rank": 1, "victim_id": "V2", "triage_class": "HIGH", "confidence_pct": 34.2,
      "sps": 47.9, "hazard_multiplier": 1.4, "tapping_detected": true,
      "location": {}, "notes": "..." }
  ]
}
```
**Errors:** `409` if no scenario is running.

### `GET /rescue-team/status`
Current multi-team auto-dispatch assignments plus the single-agent dispatch
simulation's state (does **not** advance the sensor simulation).
**Response:** `{"scenario": {}, "teams": [], "dispatch_sim": {}}`
(`dispatch_sim` shape: `team_id`, `sim_time`, `position`, `current_target`,
`eta_seconds_to_target`, `queue_order`, `reached` (arrival log), `victim_status`,
`remaining`, `complete`.)
**Errors:** `409` if no scenario is running.

### `POST /rescue-team/advance`
Step the single-agent dispatch simulation forward.
**Body:** `{ "seconds": 60.0, "steps": 1 }` (both optional; `steps` must be ≥ 1)
**Response:** `{"scenario": {}, "arrivals": [], "dispatch_sim": {}}`
**Errors:** `409` if no scenario running; `400` if `steps < 1`.

### `GET /environment`
Site-wide ambient temperature (°C) and relative humidity (%) from the
running scenario's shared weather station — one reading for the whole
disaster zone (like `/rain`, `/soil`, `/seismic`, and `/tilt`), not a
per-victim sensor. Feeds the hazard multiplier as an exposure-risk signal
(see [Section 5.5](#55-step-6-hazard-adjusted-survivor-priority-score-sps));
never affects a victim's medical triage class.
**Response:** `{"scenario": {}, "ambient_temp_c": -8.4, "humidity_pct": 57.2}`
**Errors:** `409` if no scenario is running.

### `GET /sessions`
List every logged scenario session (past and current) with per-table row
counts.
**Response:** `{"current_session_id": "...", "sessions": [{"session_id", "started_at", "seed", "counts": {}}]}`

### `GET /sessions/{session_id}/export.csv`
Download a session's full unified log as CSV
(`Content-Type: text/csv`, `Content-Disposition: attachment`).
**Errors:** `404` if `session_id` is unknown.

---

## 9. Scenario Configuration

Disaster scenarios are data, not code: each is a single JSON file under
`backend/scenarios/`, loaded by `scenario_loader.py`. Three ship with the
project — `himalaya_avalanche`, `earthquake_building_collapse`, and
`flood_urban` — and adding a new disaster type requires **no code changes**,
only a new JSON file following the documented schema (victim profiles with
per-sensor expected signature ranges, per-victim hazard context, site
origin, site-wide environment settings including ambient temperature/
humidity, and optional rescue-team templates). See the schema docstring at
the top of `backend/scenario_loader.py` for the full field reference.

---

## 10. Testing

The `tests/` directory contains a pytest suite (174 tests across 16 files)
covering:

- **Fusion engine** (`test_fusion_engine.py`, `test_fusion_engine_edge_cases.py`,
  `test_fusion_engine_imu.py`, `test_fusion_engine_water.py`)
  — the core detection matrix (empty rubble, person present, tapping
  override, hazard-adjusted SPS, weak signal) plus boundary/clamping edge
  cases, multi-cycle averaging, zero-reliability handling, kit-IMU hazard
  bonuses, and water-level/flow hazard bonuses.
- **Environmental hazard sensors** (`test_environment_temp_humidity.py`)
  — cold-exposure hazard scaling and cap, the heat+humidity compound bonus
  (and that heat or humidity alone add nothing), sensor-simulator
  temperature/humidity reports staying in sane ranges and responding to
  rainfall, and the `GET /environment` endpoint.
- **Triage queue ordering** (`test_triage_queue_ordering.py`) — doctrine
  ordering under randomized populations and via the live API.
- **REST API** (`test_api.py`, `test_api_edge_cases.py`) — endpoint
  responses, error codes, scenario lifecycle, response schema checks.
- **Rescue dispatch** (`test_rescue_dispatch.py`, `test_dispatch_edge_cases.py`)
  — full end-to-end sequencing plus haversine/edge-case unit tests.
- **Database logging** (`test_db.py`, `test_db_logging_integrity.py`) — row
  count integrity, data-type round-trip fidelity, session isolation, CSV
  export ordering.
- **Testing & Controls** (`test_admin_auth.py`, `test_admin_add_victim.py`,
  `test_admin_create_scenario.py`, `test_testing_console_flow.py`) — direct unauthenticated
  access to victim, scenario, and team creation endpoints.
- **Alert dispatch** (`test_alert_dispatch.py`) — simulated GSM/LoRa
  network-alert triggering and history.

Run the whole suite from the project root:

```bash
pip install -r requirements.txt pytest
python -m pytest tests/ -v
```

---

## 11. Design Rationale & Limitations

- **Simulation, not hardware integration.** All sensor data is synthetic
  (`sensor_simulator.py` uses a bounded mean-reverting random walk per
  victim/sensor, with an optional battery-degradation model). The system is
  designed so a real sensor feed could be substituted behind the same
  `SensorReading` interface without touching the fusion or triage logic.
- **In-memory scenario state.** `ScenarioState` in `api.py` holds the live
  simulation in a single process-global instance — appropriate for a
  single-operator demo/report context, not a multi-tenant production
  deployment.
- **SQLite over a short-lived connection per call.** Simple and safe for
  this workload; would need a pooled/async driver for high write throughput.
- **Deterministic replay.** Passing the same `seed` to `POST /scenario/start`
  reproduces the same sensor readings, which makes scenario runs reproducible
  for report figures and regression testing.
- **Ambient temperature/humidity are exposure-risk signals, not life-sign
  evidence.** Like rain, soil saturation, seismic vibration, and tilt, the
  weather station is a *site-wide* reading (one shared thermometer/hygrometer
  for the whole zone), and it only ever moves the hazard multiplier — it is
  deliberately kept out of the per-victim Confidence % fusion weights, so a
  freezing night can't be mistaken by the algorithm for a victim's declining
  vitals.

---

## 12. Rescue Team Wearable Safety Protocol

Every tracked rescue-team member starts in **HOLD** state - no one moves
toward a victim location without an explicit assignment
(`POST /commander/assign`). This is enforced structurally, not just by
convention: `advance_team_members()` only ever moves members whose status
is already `EN_ROUTE`, and the only code path that sets that status is the
manual assign action. See `tests/test_integration_rescue_chain.py`
for automated proof of this safety gate.

All modules (Dashboard, Testing Console, Commander Console, Watch Preview,
and Hardware View) are directly accessible with zero authentication required.

Wearable devices (`GET /watch/{member_id}`) are unauthenticated and self-scoped,
mirroring a real BLE/LoRa field wearable that reads its own assignment.
