# COMPLETE REPOSITORY AUDIT REPORT: BAROMETRIC PRESSURE SENSOR INTEGRATION

**Repository**: Survivor Detection & Disaster Rescue Prioritization System  
**Audit Date**: August 2026  
**Baseline Test Results**: 268 Tests Passed / 0 Failed (100% Pass Rate)

---

## 1. Existing Architecture Overview

The system is a production-grade Disaster Management and Rescue Operations platform structured into a multi-tiered architecture:

```
[ Frontend: Vanilla HTML5/CSS3/ES6 ] 
       │  (REST API calls over fetch() with Configurable API Base)
       ▼
[ Backend: FastAPI (api.py) ]
       ├── Sensor Simulator (sensor_simulator.py) -> Mean-reverting random walk & degradation
       ├── Fusion Engine (fusion_engine.py) -> Multi-sensor weighted triage & SPS scoring
       ├── Scenario Intelligence (scenario_intelligence.py) -> 19 Master Scenarios, Trends & Anomaly Detection
       ├── Alert & Rescue Dispatch (alert_dispatch.py, rescue_dispatch.py)
       ├── Scenarios Master Registry (scenarios_master.py) -> Data-driven staff eligibility
       └── SQLite Database Persistence (db.py) -> Survivor Detection DB
```

---

## 2. Inventory of Relevant Files

### Backend Core
- [backend/models.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/models.py): Core data models (`SensorType`, `SensorReading`, `SensorHealth`, `SensorTrend`, `SensorEvidence`, `ScenarioInferenceResult`, `DisasterAssessment`, `TeamMember`, `RescueTeamStatus`, `GasSmokeReading`, `GasSmokeSensorInterface`).
- [backend/db.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/db.py): SQLite schema, migrations, time-series tables (`sessions`, `sensor_readings`, `detection_results`, `rescue_status_events`, `network_alerts`, `sensor_health_records`, `sensor_trends`, `scenario_intelligence_ledger`, `active_alerts_ledger`, `gas_smoke_readings`, `personnel`, `admin_scenarios`, `admin_teams`, `commander_jobs`, `job_assignments`).
- [backend/api.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/api.py): FastAPI application serving REST endpoints for victims, queue, sensor telemetry, commander operations, staff jobs, scenario state, and admin registry.
- [backend/fusion_engine.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/fusion_engine.py): Multi-sensor fusion engine, Survivor Probability Score (SPS), triage classification (`HIGH`, `MEDIUM`, `LOW`, `NO_VITAL_SIGNS`, `SAFE`).
- [backend/scenario_intelligence.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/scenario_intelligence.py): Real-time intelligence coordinator (`SensorTrendTracker`, `SensorHealthMonitor`, `SensorEvidenceExtractor`, `DisasterScenarioInferenceEngine`, `MultiHazardCascadeEngine`, `AlertLifecycleManager`).
- [backend/scenarios_master.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/scenarios_master.py): 19 master disaster scenario definitions, keyword normalization, and dynamic `is_staff_eligible_for_scenario` matching engine.
- [backend/sensor_simulator.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/sensor_simulator.py): Physics-based simulation engine with degradation, solar battery management, and environmental channel generation.
- [backend/scenario_loader.py](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/backend/scenario_loader.py): Dynamic JSON scenario loaders and runtime config generator.

### Frontend Core
- [frontend/index.html](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/index.html) & [frontend/js/dashboard.js](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/js/dashboard.js): Main operations dashboard, victim cards, map, live environmental gauges.
- [frontend/commander.html](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/commander.html) & [frontend/js/commander.js](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/js/commander.js): Incident Commander console, interactive SVG tactical map, roster tracking, victim nearest suggestions, job assignment interface.
- [frontend/hardware.html](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/hardware.html) & [frontend/js/hardware.js](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/js/hardware.js): Sensor hardware telemetry, edge pipeline visualization.
- [frontend/testing.html](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/testing.html) & [frontend/js/testing.js](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/js/testing.js): Scenario and sensor simulation testing control room.
- [frontend/analytics.html](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/analytics.html) & [frontend/js/analytics.js](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/js/analytics.js): Interactive SVG charts, rescue performance analytics.
- [frontend/alerts.html](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/alerts.html) & [frontend/js/alerts.js](file:///c:/Users/MADHAVAN/Downloads/asdf/survivor-detection-system-main/frontend/js/alerts.js): Real-time alert feed, active alerts ledger.

---

## 3. Existing Sensor Pipeline

The platform handles 15 sensor types defined in `SensorType`:
1. `THERMAL_IMAGING` (degC)
2. `PIR_MOTION` (motion index 0-1)
3. `ACOUSTIC` (dB)
4. `CO2` (ppm)
5. `HEART_RATE_RADAR` (bpm)
6. `RGB_CAMERA` (confidence 0-1)
7. `WATER_LEVEL` (cm)
8. `WATER_FLOW` (m/s)
9. `IMU_TILT` (deg)
10. `IMU_VIBRATION` (g)
11. `GAS_CONCENTRATION` (ppm)
12. `SMOKE_DENSITY` (%)
13. `BAROMETRIC_PRESSURE` (hPa) - *Enum present; foundation, DB persistence, API, and full pipeline integration being implemented*
14. `RAINFALL_INTENSITY` (mm/hr)
15. `SOIL_MOISTURE` (%)

---

## 4. Existing Simulation & Environmental Engine

- In `sensor_simulator.py`, the `SensorSimulator` generates victim vitals using an Ornstein-Uhlenbeck mean-reverting random walk with jitter.
- Environmental readings are generated per cycle via `generate_environmental_readings()` and `environmental_full_report()`.
- Degradation model simulates battery drain, cold weather snaps, solar charging, and signal degradation.

---

## 5. Existing Database Architecture

SQLite database `survivor_detection.db` with short-lived connections and WAL mode:
- **`sessions`**: Session runs with seed, degradation, scenario ID.
- **`sensor_readings`**: Raw victim-level readings per cycle.
- **`detection_results`**: Fused victim detection outputs.
- **`rescue_status_events`**: Chronological event logs.
- **`network_alerts`**: GSM/LoRa simulated network alerts.
- **`sensor_health_records`**: Per-sensor health and battery status.
- **`sensor_trends`**: Rolling time-series trends and anomaly scores.
- **`scenario_intelligence_ledger`**: Scenario assessment records with JSON evidence.
- **`active_alerts_ledger`**: Deduplicated active alerts with status (`ACTIVE`, `RESOLVED`).
- **`gas_smoke_readings`**: Dedicated telemetry table for gas/smoke sensor.
- **`personnel` & `personnel_scenarios`**: Staff registry with trained disaster capabilities.
- **`admin_scenarios`**: Scenarios ledger with Active/Inactive status.
- **`admin_teams` & `admin_team_members`**: Dynamic team registries.
- **`commander_jobs` & `job_assignments`**: Scenario-based jobs and staff assignment workflows.

---

## 6. Existing Scenario & Alert Engines

- **Scenario Engine (`scenarios_master.py`)**: 19 master disaster scenarios with canonical IDs, display names, categories, icons, and keyword aliases.
- **Intelligence Engine (`scenario_intelligence.py`)**:
  - `SensorTrendTracker`: Rate of change, trend direction, statistical spike detection.
  - `SensorHealthMonitor`: Fault detection, offline/degraded flagging.
  - `SensorEvidenceExtractor`: Semantic token extraction (e.g. `SEVERE_BAROMETRIC_PRESSURE_DROP`).
  - `DisasterScenarioInferenceEngine`: Multi-hazard evaluation, confidence scoring, risk classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  - `AlertLifecycleManager`: Upserts deduplicated alerts into `active_alerts_ledger`.

---

## 7. Existing Commander & Staff/Job Workflow

1. Scenario becomes **ACTIVE** in Scenarios Ledger.
2. Incident Commander views active scenario, live environmental telemetry, and active alerts on Commander Dashboard.
3. Commander queries eligible teams and qualified staff via `/commander/eligible-staff`.
4. Eligibility is strictly verified on backend via `is_staff_eligible_for_scenario` in `scenarios_master.py`.
5. Commander creates a scenario job via `/commander/jobs/create`.
6. Commander assigns eligible staff via `/commander/jobs/assign`.
7. Staff receives assignment via `/staff/{member_id}/jobs`, updates status (`ACCEPTED` → `IN_PROGRESS` → `COMPLETED`) via `/staff/jobs/{id}/status`.
8. Commander monitors real-time progress and mission completion.

---

## 8. Existing Tests & Verification

The existing test suite comprises **42 test files** in `tests/`:
- Test command: `python -m pytest tests/`
- Result: **268 passed, 0 failed, 1 warning** (119s execution time).

---

## 9. Recommended Integration Points for Barometric Pressure

1. **Configuration**: Create centralized `PRESSURE_CONFIG` in `backend/models.py`.
2. **Dedicated Models**: Create `BarometricPressureReading` dataclass and `BarometricPressureInterface` ABC in `backend/models.py`.
3. **Database Table**: Add `barometric_readings` table and query functions in `backend/db.py`.
4. **Processing & Simulation Adapter**: Implement `BarometricPressureAnalyzer` and `SimulationPressureAdapter` in `backend/sensor_simulator.py`.
5. **Sensor Fusion & Intelligence**: Enhance `SensorEvidenceExtractor` and `DisasterScenarioInferenceEngine` in `backend/scenario_intelligence.py`.
6. **Alert Engine**: Add pressure alert definitions, deduplication, and escalation in `backend/scenario_intelligence.py`.
7. **APIs**: Expose REST endpoints in `backend/api.py` for ingest, history, latest, status, trend, anomaly, and config.
8. **Commander Dashboard & UI**: Integrate live hPa readings, trend badges, rate of change, history charts, and simulation controls.

---

## 10. Potential Conflicts & Mitigations

| Potential Issue | Root Cause | Mitigation Strategy |
| :--- | :--- | :--- |
| False cyclone alarms | Isolated pressure fluctuation | Pressure is strictly supporting evidence; requires multi-sensor correlation (wind, rain, surge) |
| Duplicate alerts on prolonged pressure drop | New alert fired every cycle | Alert deduplication updates existing active alert in-place in `active_alerts_ledger` |
| Offline sensor reporting 0 hPa | Defaulting missing value to zero | Reject 0/null conversions; explicitly set status to `OFFLINE` and pressure to `UNAVAILABLE` |
| Hardcoded team names | Checking `if team == "Alpha"` | Use dynamic DB queries and capability-based matching via `scenarios_master.py` |
| Breaking existing tests | Schema or API signature mismatch | Strict backwards compatibility; additive DB migrations and non-breaking API extensions |
