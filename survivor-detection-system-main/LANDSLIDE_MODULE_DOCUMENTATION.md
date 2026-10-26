# RIDGEWATCH: Geotechnical Soil Moisture + Tilt / Inclinometer Landslide Detection & Early Warning Module

## Executive Overview

The **Geotechnical Soil Moisture + Tilt / Inclinometer Landslide Detection & Early Warning Module** is a core sub-system of the **RIDGEWATCH AI-Based Multi-Sensor Survivor Detection & Rescue Prioritization System**. 

The module is engineered to detect pre-failure geotechnical slope instability, evaluate compounding environmental triggers (soil moisture saturation, inclinometer shear rate, torrential precipitation, seismic vibration), calculate an explainable **Landslide Risk Score (0–100)**, and deliver mission-critical early warnings and automated alerts to Search & Rescue Commanders.

> **Engineering Principle:** The system provides probabilistic, sensor-based decision support and hazard estimation. It does not claim deterministic foreknowledge of natural slope failures.

---

## 1. System Architecture & Component Interactions

```mermaid
flowchart TD
    subgraph SENSORS["Geotechnical IoT Sensor Layer"]
        S1["Upper Ridge (SLOPE-NODE-01)\nMoisture % + Inclinometer Tilt °"]
        S2["Mid-Slope (SLOPE-NODE-02)\nMoisture % + Inclinometer Tilt °"]
        S3["Base Slope (SLOPE-NODE-03)\nMoisture % + Inclinometer Tilt °"]
    end

    subgraph SIM["Sensor Simulation Engine"]
        AD["LandslideSensorSimulationAdapter\n(9 Deterministic Profiles)"]
        S1 --> AD
        S2 --> AD
        S3 --> AD
    end

    subgraph ENGINE["Landslide Hazard Intelligence & Fusion Engine"]
        LRA["LandslideRiskAnalyzer\n- Multi-Parameter Scoring\n- Rate of Change & Trend Filter\n- Persistence & Debounce (<= 68 max)\n- 6-State Event State Machine"]
        AD --> LRA
        RAIN["Rainfall Telemetry (mm/hr)"] --> LRA
        SEIS["Seismic Vibration (mm/s)"] --> LRA
    end

    subgraph PERSIST["SQLite Operational DB Ledger"]
        DB[("landslide_readings\nactive_alerts")]
        LRA --> DB
    end

    subgraph API["FastAPI REST Endpoints"]
        EP1["/sensors/soil-moisture/*"]
        EP2["/sensors/tilt/*"]
        EP3["/hazards/landslide/*"]
        DB --> API
        LRA --> API
    end

    subgraph UI["RIDGEWATCH Web Applications"]
        HW["Hardware Diagnostics & Slope Nodes"]
        LOGIC["Logic & Score Explainability"]
        CMD["Commander Incident Command Center"]
        TEST["Testing & Manual IoT Ingestion"]
        ANALYTICS["Analytics & Historical Charts"]
        API --> HW
        API --> LOGIC
        API --> CMD
        API --> TEST
        API --> ANALYTICS
    end
```

---

## 2. Sensor Foundations & Data Models

### Soil Moisture Sensor
- **Unit**: `%` Volumetric Water Content / Saturation (`0.0% – 100.0%`).
- **Validation**: Values `< 0.0%` or `> 100.0%` or `NaN`/`Inf` are rejected with HTTP 422.
- **Classification Bands**:
  - `0.0% – 49.9%`: Dry / Nominal Baseline
  - `50.0% – 69.9%`: Wet / Elevated Saturation
  - `70.0% – 79.9%`: Highly Saturated (Pore-pressure accumulation)
  - `80.0% – 100.0%`: Super-Saturated / Critical Liquefaction

### Tilt / Inclinometer Sensor
- **Unit**: Degrees of angular displacement from baseline (`0.0° – 90.0°`).
- **3-Axis Telemetry**: `tilt_x`, `tilt_y`, `tilt_z`, `tilt_angle_deg`, `tilt_rate` (deg/cycle).
- **Validation**: Negative values, values `> 90.0°`, and non-numeric inputs are rejected.
- **Classification Bands**:
  - `0.0° – 1.49°`: Stable Equilibrium
  - `1.5° – 2.99°`: Minor Slope Creep / Elevated
  - `3.0° – 4.49°`: Significant Shear Displacement / High
  - `4.5° – 90.0°`: Structural Failure / Critical Shear

---

## 3. Landslide Risk Scoring & Multi-Parameter Fusion

The **Landslide Risk Score (0–100)** is computed across 5 weighted sub-scores:

| Component | Max Points | Description |
| :--- | :---: | :--- |
| **Moisture Subscore** | **25 pts** | Base soil moisture level (Nominal: 0–8 pts, Elevated: 8–18 pts, Critical: 18–25 pts) |
| **Moisture Trend Bonus** | **15 pts** | Rate of moisture change per cycle (Rising: +8 pts, Rapidly Rising: +15 pts, Falling: -3 to -6 pts) |
| **Tilt Subscore** | **25 pts** | Angular deviation from baseline (Nominal: 0–6 pts, Elevated: 6–17 pts, Critical: 17–25 pts) |
| **Tilt Trend Bonus** | **25 pts** | Rate of tilt change per cycle (Rising: +14 pts, Rapidly Rising: +25 pts, Falling: -5 to -10 pts) |
| **Persistence & Compound Triggers** | **10 pts** | Compounding factors: Torrential Rain (>=25 mm/hr: +3 pts), Ground Vibration (>=4 mm/s: +3 pts), Multi-cycle persistence (+4 pts) |

### Persistence Filter & Single Spike Debouncing
To prevent false alarms in noisy field telemetry:
- A single isolated spike on Cycle 1 is debounced and clamped to **$\le 68.0$ (High)**, never triggering an immediate False Alarm Critical alert.
- Escalation to **CRITICAL ($\ge 75.0$)** requires sustained elevation across $\ge 2$ consecutive cycles.

### Event State Machine
```
[NORMAL] ──(moist/tilt elevation)──> [WATCH] ──(further shift)──> [ELEVATED] 
   ▲                                                                    │
   │                                                             (accelerating)
   │                                                                    ▼
[RECOVERY] <──(multi-cycle stabilization)── [CRITICAL] <─── [HIGH_RISK]
```

---

## 4. Multi-Node Deployment Topology

The system models a 3-tier slope telemetry array:

1. **Upper Ridge Node (`SLOPE-NODE-01`)**: Crest slope monitor (Lat: 11.5312, Lon: 76.1245).
2. **Mid-Slope Node (`SLOPE-NODE-02`)**: Primary shear plane monitor (Lat: 11.5305, Lon: 76.1250).
3. **Base Slope Node (`SLOPE-NODE-03`)**: Debris flow & runout zone monitor (Lat: 11.5298, Lon: 76.1258).

---

## 5. Simulation Profiles

The module includes 9 deterministic simulation profiles:

1. `NORMAL`: Nominal moisture (35–45%) and stable tilt (0.5–1.5°).
2. `WET_SOIL`: Elevated moisture (55–65%) with stable tilt.
3. `INCREASING_MOISTURE`: Rising moisture (65–85%) tracking saturation.
4. `TILT_ANOMALY`: Rapid inclinometer shift (3–6°) without heavy moisture.
5. `EARLY_LANDSLIDE`: Compounding 70–80% moisture + 2.5–4.5° tilt.
6. `CRITICAL_LANDSLIDE`: 85–95% saturation + 5–9° critical shear rate.
7. `SENSOR_FAILURE`: Probe offline / communication disruption.
8. `NOISY_SENSOR`: Telemetry with random spikes (filtered by debouncer).
9. `RECOVERY`: Gradual stabilization back to nominal baseline.

---

## 6. REST API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/sensors/soil-moisture/current` | `GET` | Current soil moisture reading and probe health |
| `/sensors/soil-moisture/history` | `GET` | Historical soil moisture readings (time-series) |
| `/sensors/tilt/current` | `GET` | Current 3-axis tilt reading and inclinometer health |
| `/sensors/tilt/history` | `GET` | Historical tilt readings (time-series) |
| `/hazards/landslide/current` | `GET` | Aggregate current landslide hazard assessment |
| `/hazards/landslide/nodes` | `GET` | Multi-node geotechnical slope telemetry status |
| `/hazards/landslide/risk` | `GET` | Explainable 5-factor risk score breakdown |
| `/hazards/landslide/history` | `GET` | Historical landslide risk score timeline |
| `/hazards/landslide/profile` | `POST` | Switch active simulation profile (9 profiles) |
| `/sensors/soil-moisture/readings` | `POST` | Ingest external IoT soil moisture reading |
| `/sensors/tilt/readings` | `POST` | Ingest external IoT tilt/inclinometer reading |
| `/alerts/{alert_key}/resolve` | `POST` | Manually resolve active geotechnical alert |

---

## 7. Frontend Integration Matrix

- **Hardware Diagnostics (`hardware.html`)**: Live Geotechnical Slope Telemetry Nodes panel with moisture %, rate of change, tilt angle, shear rate, and probe health status for each node.
- **Logic & AI Explainability (`logic.html`)**: Step 5 Landslide Hazard Risk Engine panel showing subscore bars, total score, state machine badges, and actionable recommendations.
- **Commander Incident Command Center (`commander.html`)**: Landslide Hazard & Slope Stability Intelligence card with live risk gauge, persistence cycles, slope nodes list, and active hazard factor warnings.
- **Testing & Simulation Control (`testing.html`)**: Landslide & Geotechnical Simulation Profiles switcher and manual IoT telemetry injection form.
- **Analytics & History (`analytics.html`)**: Geotechnical & Landslide Risk Timeline SVG chart plotting Soil Moisture %, Inclinometer Tilt °, and Risk Score.
