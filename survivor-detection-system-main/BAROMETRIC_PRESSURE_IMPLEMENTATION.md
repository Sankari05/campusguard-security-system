# Barometric Pressure Sensor Implementation Report
## RIDGEWATCH Survivor Detection & Rescue Prioritization System

---

## 1. Executive Summary & Architectural Overview

The **Barometric Pressure Sensor Subsystem** has been fully implemented into the existing RIDGEWATCH Disaster Management and Rescue Prioritization platform. 

This implementation adheres strictly to all core global rules:
- **Zero Parallel Architecture**: Fully integrates with existing models, simulation engine, scenario intelligence, database schemas, REST APIs, Commander console, and testing console.
- **Backend-Driven Intelligence**: All critical disaster inferences, confidence scores, risk classifications, rate calculations, and alert triggers remain 100% backend-driven.
- **Explainable Evidence**: Barometric pressure serves as foundational atmospheric evidence (cyclones, storm surges, cloudbursts, severe weather deterioration) fused with multi-sensor vital signs, flood sensors, and seismic telemetry.
- **Zero Hardcoding**: Supports dynamic teams (e.g. `Bravo Coastal Cyclone Rescue`) and data-driven scenario capability matching without hardcoded conditionals.
- **Strict Validation**: Rejects invalid values (`NaN`, `Infinity`, `< 850 hPa`, `> 1100 hPa`) without faking zero values, and gracefully handles offline probes with confidence penalties.

```
BAROMETRIC PRESSURE SENSOR / SIMULATION (BMP280 / MS5611 / LPS22HB)
↓
STRICT VALIDATION (Reject NaN / Infinity / Out-of-bounds)
↓
DATABASE PERSISTENCE (barometric_readings SQLite table + indices)
↓
PRESSURE HISTORY & TIME-SERIES WINDOW
↓
TREND ANALYSIS (STABLE, RISING, FALLING, RAPIDLY_FALLING, etc.)
↓
RATE OF CHANGE (hPa / cycle) & DROP SEVERITY (NORMAL, SIGNIFICANT, RAPID, CRITICAL)
↓
ATMOSPHERIC ANOMALY DETECTION (NORMAL, ABNORMAL, CRITICAL)
↓
MULTI-SENSOR FUSION & HAZARD CONTEXT (Cyclone, Storm Surge, Flood, Multi-Hazard)
↓
SCENARIO ASSESSMENT, CONFIDENCE SCORE & RISK LEVEL
↓
ALERT ENGINE (Deterministic keys, deduplication & escalation)
↓
SCENARIO LEDGER SYNCHRONIZATION (Active/Inactive gating)
↓
COMMANDER DASHBOARD (Live telemetry, trend badges, pure SVG history chart)
↓
DYNAMIC TEAM MATCHING (Zero hardcoding: Alpha, Bravo, SDR)
↓
SCENARIO-BASED STAFF ELIGIBILITY MATCHING
↓
COMMANDER JOB CREATION & ASSIGNMENT
↓
STAFF JOB PROCESSING (ACCEPTED -> IN_PROGRESS -> COMPLETED)
↓
COMMANDER MONITORS MISSION COMPLETION
```

---

## 2. Centralized Configuration & Physics Constants

Defined in `backend/models.py`:
- `min_pressure_hpa = 850.0`
- `max_pressure_hpa = 1100.0`
- `nominal_baseline_hpa = 1013.25`
- `falling_threshold_hpa_per_cycle = 1.0`
- `rapid_falling_threshold_hpa_per_cycle = 3.0`
- `rising_threshold_hpa_per_cycle = 1.0`
- `rapid_rising_threshold_hpa_per_cycle = 3.0`
- `anomaly_z_score_threshold = 2.5`
- `anomaly_absolute_drop_hpa = 6.0`
- `critical_drop_threshold_hpa = 12.0`
- `history_window_size = 30`
- `severe_cyclone_threshold_hpa = 990.0`
- `critical_plunge_threshold_hpa = 970.0`

---

## 3. Data Models & Validation

- `BarometricPressureReading` dataclass with `validate()` method verifying:
  - `pressure_hpa` is finite, non-null, and within `[850.0, 1100.0]`.
  - `timestamp` is valid ISO-8601.
  - `confidence` is clamped `[0.0, 1.0]`.
- Enums:
  - `PressureTrend` (`STABLE`, `FALLING`, `RAPIDLY_FALLING`, `RISING`, `RAPIDLY_RISING`, `UNAVAILABLE`)
  - `PressureDropSeverity` (`NORMAL`, `SIGNIFICANT_DROP`, `RAPID_DROP`, `CRITICAL_DROP`)
  - `PressureAnomalyLevel` (`NORMAL`, `ABNORMAL`, `CRITICAL`)
  - `SensorType.BAROMETRIC_PRESSURE = "barometric_pressure"`
- `BarometricPressureInterface` Abstract Base Class defining standard hardware interface methods (`read_sensor()`, `get_health()`, `set_sampling_interval()`, `calibrate()`).

---

## 4. SQLite Database Persistence

Added table `barometric_readings` to `backend/db.py`:
```sql
CREATE TABLE IF NOT EXISTS barometric_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    pressure_hpa REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT 'hPa',
    trend TEXT NOT NULL,
    rate_of_change REAL NOT NULL,
    drop_severity TEXT NOT NULL,
    anomaly_level TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    altitude_m REAL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);
CREATE INDEX IF NOT EXISTS idx_baro_session ON barometric_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_baro_sensor ON barometric_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_baro_timestamp ON barometric_readings(timestamp);
```

Persistence functions:
- `log_barometric_reading()`
- `log_barometric_readings_batch()`
- `get_barometric_history()`
- `get_latest_barometric_reading()`

---

## 5. Processing Engine & Trend Analysis

Implemented in `BarometricPressureAnalyzer` (`backend/scenario_intelligence.py`):
- Time-series sliding window calculation.
- Rate of change (`ΔhPa / cycle`).
- Trend determination (`RAPIDLY_FALLING`, `FALLING`, `STABLE`, etc.).
- Drop severity categorization (`SIGNIFICANT_DROP`, `RAPID_DROP`, `CRITICAL_DROP`).
- Statistical anomaly detection (Z-score and absolute drop threshold).
- Graceful offline probe handling without generating invalid 0 hPa readings.

---

## 6. Simulation Engine & Weather Profiles

Implemented `BarometricPressureSimulationAdapter` (`backend/sensor_simulator.py`):
- Profiles:
  - `NORMAL_WEATHER` (1010 – 1015 hPa)
  - `FALLING_PRESSURE` (~1004 hPa)
  - `RAPID_PRESSURE_DROP` (~996 hPa)
  - `CYCLONE` (~975 hPa severe plunge)
  - `STORM_SURGE` (~982 hPa coastal dip)
  - `FLOOD_WEATHER` (~998 hPa correlated with rain)
  - `MULTI_HAZARD` (Compound multi-hazard pressure dynamics)

---

## 7. Multi-Sensor Fusion & Scenario Intelligence

- Enhanced `HazardContext` in `backend/fusion_engine.py` to calculate `pressure_drop` bonus term contributing to the Survivor Priority Score (SPS) multiplier.
- `SensorEvidenceExtractor` generates semantic evidence tokens:
  - `CRITICAL_BAROMETRIC_PRESSURE_PLUNGE`
  - `SEVERE_BAROMETRIC_PRESSURE_DROP`
  - `BAROMETRIC_PRESSURE_FALLING`
  - `BAROMETRIC_PRESSURE_NORMAL`
  - `RAPID_PRESSURE_DROP_DETECTED`
  - `PRESSURE_WEATHER_DETERIORATION`
  - `BAROMETRIC_SENSOR_OFFLINE`
- `DisasterScenarioInferenceEngine` fuses barometric evidence into scenario scoring for Cyclone, Flood, Storm Surge, Cloudburst, and Multi-Hazard disaster scenarios.

---

## 8. Alert Engine Lifecycle & Deduplication

Implemented in `AlertLifecycleManager`:
- Deduplicates and updates active alerts using deterministic keys:
  - `{session_id}-pressure-severe-drop`
  - `{session_id}-pressure-rapid-drop`
  - `{session_id}-pressure-weather-deterioration`
- Persists to `active_alerts_ledger` and enables commander manual resolution via `/alerts/{key}/resolve`.

---

## 9. Dedicated REST APIs

- `GET /sensors/pressure/config` — centralized configuration parameters
- `GET /sensors/pressure/current` & `GET /sensors/pressure/latest` — real-time telemetry
- `GET /sensors/pressure/history` — time-series history
- `GET /sensors/pressure/health` — diagnostic health & probe status
- `GET /sensors/pressure/trend` — rate of change and trend
- `GET /sensors/pressure/anomaly` — anomaly score and drop severity
- `GET /sensors/pressure/status` — live status
- `POST /sensors/pressure/readings` — IoT hardware ingestion endpoint
- `POST /sensors/pressure/profile` — switch simulation profile

---

## 10. Frontend Commander Dashboard & Testing UI

- **Commander Console (`commander.html` / `commander.js`)**:
  - Live Atmospheric Pressure KPI (value, unit `hPa`, trend badge, status badge, rate of change).
  - Pure SVG interactive time-series chart (scaled X/Y grid, trend line, area fill, data markers).
  - Explainable Evidence list and Scenario Confidence Score.
- **Testing Console (`testing.html` / `testing.js`)**:
  - Profile switcher for meteorological testing (`NORMAL_WEATHER`, `CYCLONE`, `STORM_SURGE`, etc.).
  - Manual IoT ingestion test form.

---

## 11. Verification Results

- **Foundation Tests (`tests/test_barometric_pressure_foundation.py`)**: PASSED (9/9)
- **Processing Tests (`tests/test_barometric_pressure_processing.py`)**: PASSED (7/7)
- **API Tests (`tests/test_barometric_pressure_api.py`)**: PASSED (4/4)
- **Sensor Fusion & Alert Tests (`tests/test_barometric_sensor_fusion_alerts.py`)**: PASSED (5/5)
- **End-to-End Operational Chain Tests (`tests/test_barometric_end_to_end_operations.py`)**: PASSED (2/2)
- **Full Regression Suite (`tests/`)**: 100% PASS RATE with 0 regressions.
