# RIDGEWATCH Flash-Flood Early Warning, Non-Contact Hydrostatic Pressure & Tactical Rescue System

## 1. Executive Summary & Problem Context

During catastrophic mountain flash-flood and debris flow emergencies (such as the 2021 Melamchi and Seti River disaster dynamics in Nepal), submerged river stage sensors and in-stream pressure transducers are rapidly destroyed, silted over, or swept away by high-velocity slurry and boulders. 

To solve this life-safety challenge, **RIDGEWATCH** implements a robust, real-time, **non-contact flash-flood early warning, hydrostatic pressure monitoring, dynamic evacuation, and rescue coordination platform**. 

The system derives true hydrostatic water pressure ($P = \rho \cdot g \cdot h$) and stage depth strictly from airborne distance measurements—using downward-looking FMCW radar (60–80 GHz) and ultrasonic transceivers mounted safely above floodwaters—coupled with soil moisture, slope tilt, acoustic rumble, and multi-bearer communication fallback.

---

## 2. Physical Principles & Mathematical Derivations

```
                     ┌──────────────────────────────┐
                     │ Downward-Facing Non-Contact  │
                     │ Radar / Ultrasonic Sensor    │
                     └──────────────┬───────────────┘
                                    │
                                    │ Measured Surface Distance (d)
                                    ▼
       ~~~~~~~~~~~~~~~~~~~~ Water Surface (Air-Water Interface) ~~~~~~~~~~~~~~~~~~~~
       ▲
       │
       │ Water Depth (h = H_mount - Datum - d)
       │
       ▼
══════════════════════════ Riverbed / Measurement Datum (z = 0) ══════════════════════════
```

### 2.1 Hydrostatic Gauge Pressure

According to classical fluid statics, hydrostatic gauge pressure exerted by a standing or quasi-steady water column at depth $h$ is:

$$P = \rho \cdot g \cdot h$$

Where:
- **$\rho$ (rho)**: Fluid density = $1000.0\text{ kg/m}^3$ (nominal for fresh river water at standard conditions).
- **$g$**: Acceleration due to gravity = $9.80665\text{ m/s}^2$ (standard Earth gravitational acceleration).
- **$h$**: Water column depth in metres ($m$).

The pressure is computed in Pascal ($\text{Pa}$) and converted to Kilopascal ($\text{kPa}$):

$$P_{\text{kPa}} = \frac{P_{\text{Pa}}}{1000.0} = \frac{\rho \cdot g \cdot h}{1000.0}$$

### 2.2 Non-Contact Geometry & Water Depth Calculation

The downward-pointing sensor is fixed at a known vertical height $H_{\text{mount}}$ above the riverbed or bridge datum ($z_{\text{datum}} = 0.0\text{ m}$).

The sensor emits acoustic or electromagnetic wave pulses and measures the round-trip time-of-flight to the air-water interface to determine surface distance $d$:

$$h = \max\left(0.0, (H_{\text{mount}} - z_{\text{datum}}) - d\right)$$

#### Numerical Examples:
1. **Dry / Baseline Riverbed**: $H_{\text{mount}} = 6.0\text{ m}$, $d = 6.0\text{ m}$
   $$h = 6.0 - 6.0 = 0.0\text{ m} \implies P = 0.0\text{ kPa}$$
2. **Moderate Stage Flood**: $H_{\text{mount}} = 6.0\text{ m}$, $d = 4.5\text{ m}$
   $$h = 6.0 - 4.5 = 1.5\text{ m} \implies P = 1000 \cdot 9.80665 \cdot 1.5 = 14,709.975\text{ Pa} \approx 14.71\text{ kPa}$$
3. **Severe Flash-Flood Surge**: $H_{\text{mount}} = 6.0\text{ m}$, $d = 2.0\text{ m}$
   $$h = 6.0 - 2.0 = 4.0\text{ m} \implies P = 1000 \cdot 9.80665 \cdot 4.0 = 39,226.6\text{ Pa} \approx 39.23\text{ kPa}$$

### 2.3 Water-Level Rise Rate & Acceleration

The first and second time derivatives of water depth are computed across consecutive telemetry cycles:

$$\frac{dh}{dt} = \frac{h(t) - h(t - \Delta t)}{\Delta t} \quad [\text{m/s}]$$

$$\text{Rise Rate}_{\text{cm/min}} = \frac{dh}{dt} \cdot 100 \cdot 60$$

$$\frac{d^2h}{dt^2} = \frac{\left.\frac{dh}{dt}\right|_t - \left.\frac{dh}{dt}\right|_{t - \Delta t}}{\Delta t} \quad [\text{m/s}^2]$$

### 2.4 Time to Inundation Projection

When water level is rising toward a critical flood embankment or bridge deck clearance $H_{\text{critical}}$ ($H_{\text{critical}} = 3.5\text{ m}$ by default):

$$T_{\text{inundation}} = \begin{cases} 
\frac{H_{\text{critical}} - h(t)}{\frac{dh}{dt} \cdot 60} & \text{if } \frac{dh}{dt} > 0.001\text{ m/s} \text{ and } h < H_{\text{critical}} \\
0.0\text{ min} & \text{if } h \ge H_{\text{critical}} \\
\infty & \text{if } \frac{dh}{dt} \le 0.001\text{ m/s}
\end{cases}$$

---

## 3. Flash-Flood Intelligence & Risk Classification

The `FloodIntelligenceEngine` fuses multi-sensor hydrological indicators into an explainable 0–100 composite risk score:

$$\text{Risk Score} = w_{\text{depth}} S_{\text{depth}} + w_{\text{rise}} S_{\text{rise}} + w_{\text{rain}} S_{\text{rain}} + w_{\text{vel}} S_{\text{vel}} + w_{\text{geo}} S_{\text{geo}}$$

### Feature Weights & Indicators

| Indicator | Weight ($w_i$) | Physical Parameter | Critical Condition |
| :--- | :--- | :--- | :--- |
| **Water Depth** | $35\%$ | Non-contact derived $h$ | $h \ge 3.0\text{ m}$ |
| **Rise Rate** | $25\%$ | $\frac{dh}{dt}$ surge velocity | $\frac{dh}{dt} \ge 0.05\text{ m/s}$ ($3\text{ m/min}$) |
| **Precipitation** | $20\%$ | Tipping-bucket rain intensity | Rain $\ge 50\text{ mm/hr}$ |
| **Flow Velocity** | $10\%$ | Surface radar doppler speed | $v \ge 2.5\text{ m/s}$ |
| **Geotechnical / Upstream** | $10\%$ | Landslide / Debris flow trigger | Upstream dam break / acoustic rumble |

### Risk Level Tiers

- **NORMAL (0–25)**: River stage within seasonal bounds. Nominal baseline monitoring.
- **WATCH (26–50)**: Stage rising ($> 0.8\text{ m}$) or heavy mountain rainfall. Field teams alerted.
- **WARNING (51–75)**: Rapid inundation ($h > 1.8\text{ m}$ or rise rate $> 1.0\text{ m/min}$). Prepare community evacuation.
- **CRITICAL (76–100)**: Catastrophic surge ($h > 2.8\text{ m}$, debris flow active, or $T_{\text{inundation}} < 15\text{ min}$). Mandatory immediate high-ground evacuation and Swiftwater Rescue protocols active.

---

## 4. Geotechnical Coupling: Landslide & Debris Flow Detection

In Himalayan and steep-terrain river valleys, flash floods are intimately coupled with geotechnical slope failures and temporary landslide dams.

### 4.1 Landslide Detector (`LandslideDetector`)
- **Sensors**: FDR Soil Moisture Probes + MPU-6050 Slope Inclinometers + Cumulative Rainfall.
- **Physics**: Slope stability decreases as volumetric soil moisture exceeds saturation thresholds ($> 70\%$) combined with slope tilt angle displacement ($\theta > 12^\circ$).
- **Output**: Factor of Safety ($FS$) proxy and early landslide alarm before catastrophic mass displacement.

### 4.2 Debris Flow & Dam Breach Detector (`DebrisFlowDetector`)
- **Sensors**: Surface Flow Radar Doppler + Infrasound / Geophone Acoustic Rumble Sensors.
- **Physics**: High water flow velocity ($> 2.0\text{ m/s}$) combined with elevated low-frequency ground vibration ($> 65\text{ dB}$ rumble at $10\text{--}50\text{ Hz}$) indicates boulder and mud transport typical of glacial lake outburst floods (GLOF) or landslide dam breach surges.

---

## 5. Evacuation Planning & Tactical Road Network

The `EvacuationEngine` continuously evaluates 4 designated vulnerable population zones against live inundation risk:

### Vulnerable Inundation Danger Zones

| Zone ID | Zone Name | Elevation | Critical Threshold | Default Safe Assembly Point |
| :--- | :--- | :--- | :--- | :--- |
| `ZONE-RIVER-LOW` | Riverside Lowland Settlement | $+1.2\text{ m}$ | $1.2\text{ m}$ | `AP-HILL-TEMPLE` (+38m) |
| `ZONE-MELAMCHI-BAZ` | Melamchi Bazaar Commercial Hub | $+2.5\text{ m}$ | $2.2\text{ m}$ | `AP-HIGH-SCHOOL` (+24m) |
| `ZONE-FLOODPLAIN-C` | Floodplain Sector C Agricultural Area | $+1.8\text{ m}$ | $1.8\text{ m}$ | `AP-COMMUNITY-CTR` (+18m) |
| `ZONE-BRIDGE-APPR` | Lower Bridge Approach & Transit Point | $+1.5\text{ m}$ | $1.5\text{ m}$ | `AP-STADIUM-HIGH` (+30m) |

### Tactical Evacuation Routing & Safety Margin

1. **A\* Detour Routing**: Evaluates graph connectivity using `TacticalRoadNetwork`, automatically pruning flooded or blocked road segments.
2. **Safety Margin Calculation**:
   $$\text{Safety Margin} = T_{\text{inundation}} - T_{\text{transit}}$$
   - **POSITIVE**: Evacuation window is open with safe buffer.
   - **ZERO / NEGATIVE**: Route compromised; urgent vertical shelter-in-place instructions issued immediately.

---

## 6. Multi-Bearer Communication Architecture

In mountainous disaster zones, cellular base stations frequently lose power or fiber backhaul. RIDGEWATCH implements an automated 4-tier communication fallback hierarchy:

```
┌────────────────────────────────────────────────────────┐
│  Tier 1: High-Speed Internet REST API / WebSockets     │
└──────────────────────────┬─────────────────────────────┘
                           │ (Failover on HTTP timeout)
                           ▼
┌────────────────────────────────────────────────────────┐
│  Tier 2: GSM SMS Gateway (SMSGate Local SIM Service)   │
└──────────────────────────┬─────────────────────────────┘
                           │ (Failover on Carrier Outage)
                           ▼
┌────────────────────────────────────────────────────────┐
│  Tier 3: LoRa 868/915 MHz Long-Range Tactical Mesh    │
└──────────────────────────┬─────────────────────────────┘
                           │ (Failover when Mesh Out of Range)
                           ▼
┌────────────────────────────────────────────────────────┐
│  Tier 4: Offline App Local Queue & Bluetooth Peering  │
└────────────────────────────────────────────────────────┘
```

- **Idempotency Deduplication**: Each emergency alert payload is hashed with an idempotency key (`idempotency_key`) to prevent duplicate message dispatch across bearers.
- **Priority Queuing**: Messages are prioritized (`CRITICAL`, `WARNING`, `ADVISORY`, `ROUTINE`).

---

## 7. Sensor Fleet Health & Diagnostics

The `SensorHealthMonitor` continuously audits all deployed hardware nodes:
- **Heartbeat Freshness**: Detects dead or disconnected nodes ($> 30\text{s}$ timeout flags `STALE` / `OFFLINE`).
- **Battery Health**: Low-voltage detection ($< 3.4\text{V}$ or $< 20\%$ capacity flags `CRITICAL_BATTERY`).
- **Wireless Signal Quality**: RF link budget monitoring (RSSI $< -85\text{ dBm}$ flags `SIGNAL_POOR`).
- **Frozen Sensor Anomaly Detection**: Flags broken transducers reporting invariant values during active storms.
- **Fleet Health Index**: Composite fleet integrity score ($0\text{--}100\%$) displayed on commander and hardware dashboards.

---

## 8. REST API Reference

### 8.1 Non-Contact Hydrostatic Pressure
- **Endpoint**: `GET /hydrostatic-pressure/estimate`
- **Query Params**:
  - `measured_distance_m`: `float` (e.g. `4.5`)
  - `sensor_mount_height_m`: `float` (default `6.0`)
  - `fluid_density_kg_m3`: `float` (default `1000.0`)
- **Response**:
```json
{
  "success": true,
  "sensor_type": "ultrasonic",
  "measured_surface_distance_m": 4.5,
  "sensor_mount_height_m": 6.0,
  "pressure_datum_m": 0.0,
  "water_depth_m": 1.5,
  "water_level_rise_rate_mps": 0.025,
  "water_level_rise_rate_cm_min": 150.0,
  "estimated_pressure_pa": 14709.975,
  "estimated_pressure_kpa": 14.71,
  "reading_timestamp": "2026-09-13T16:00:00Z",
  "reading_quality": "VALID",
  "is_valid": true,
  "status_message": "Nominal hydrostatic pressure estimation",
  "pressure_source": "non_contact_sensor_estimation"
}
```

### 8.2 Current Flood Intelligence
- **Endpoint**: `GET /flood-intelligence/current`
- **Response**: Comprehensive fused risk report, breakdown scores, time-to-inundation, and active alarms.

### 8.3 Proactive Early-Warning Summary
- **Endpoint**: `GET /flood-intelligence/early-warning`
- **Response**: High-level alert status (`CRITICAL_WARNING`, `FLOOD_WARNING`, `FLOOD_WATCH`, `NORMAL`), warning title, advisory body, and evacuation flag.

### 8.4 Custom Evaluation Ingestion
- **Endpoint**: `POST /flood-intelligence/evaluate`
- **Body**:
```json
{
  "measured_surface_distance_m": 2.2,
  "rainfall_rate_mmh": 65.0,
  "flow_velocity_mps": 3.1,
  "upstream_surge_active": true,
  "soil_moisture_pct": 85.0,
  "slope_tilt_deg": 14.5,
  "acoustic_rumble_db": 78.0
}
```

### 8.5 Dynamic Evacuation Recommendations
- **Endpoint**: `GET /evacuation/recommendations`
- **Response**: List of zone recommendations, high-ground assembly coordinates, route transit times, and safety margins.

### 8.6 Sensor Fleet Health Summary
- **Endpoint**: `GET /sensors/health/summary`
- **Response**: Fleet health index percentage, battery statuses, RSSI levels, and diagnostics.

### 8.7 Multi-Bearer Communication Status & Send
- **Endpoint**: `GET /communication/status`
- **Endpoint**: `POST /communication/send`
- **Body**:
```json
{
  "recipient": "BROADCAST",
  "payload": "🚨 CRITICAL FLASH-FLOOD SURGE ALERT: Evacuate Melamchi Bazaar to High School Assembly Point immediately!",
  "priority": "CRITICAL"
}
```

---

## 9. Verification & Automated Test Coverage

The flash-flood early warning and non-contact pressure estimation subsystem is verified by an extensive automated test suite (`tests/test_flash_flood_intelligence_suite.py` and `tests/test_non_contact_pressure.py`):

1. **Exact Hydrostatic Physics ($P = \rho g h$)**: Validated for zero depth, fractional depths, and multi-metre surges.
2. **Sensor Rejection & Out-of-Bounds**: Negative distances, distances exceeding max range, and impossible displacement rate jumps ($> 3\text{ m/s}$) are correctly identified and quarantined.
3. **Geotechnical Detector Integration**: Landslide and debris flow detection verified against geotechnical thresholds.
4. **Evacuation Routing & Safety Margins**: Verified route calculations and safe assembly point selection.
5. **Multi-Bearer Failover & Deduplication**: Verified failover from API to SMS and LoRa, with duplicate payload rejection.
6. **API Endpoints**: 100% verified across all HTTP methods and URL rewrites.
