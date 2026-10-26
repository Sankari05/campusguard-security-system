# RIDGEWATCH — Existing System Communication Analysis
**Document Version:** 1.0.0  
**Date:** September 2026  
**Author:** Disaster Communication Systems Engineering & QA Team  
**Status:** Completed Inspection Baseline (Phase 1)

---

## 1. Executive Summary & Context

RidgeWatch is an AI-driven multi-sensor survivor detection, hazard intelligence, and emergency rescue prioritization platform operating in extreme alpine and disaster environments. The existing communication stack encompasses:
1. **Sensor Ingestion & Fusion:** Ingesting 18 sensor modalities (Bioradar, Thermal IR, Acoustic Tapping, PIR, CO2, Barometric Pressure, Landslide Tilt/Moisture, Optical RGB, Rainfall, Water Level, etc.) into `fusion_engine.py` and `scenario_intelligence.py`.
2. **Alert Generation & Prioritization:** Automated generation of survivor detection alerts (`ALT-...`) with Survivor Priority Scores (SPS) and priority classes (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) via `alert_dispatch.py`.
3. **Rescue Dispatch & Work Assignments:** Commander assignment flows in `api.py` (`POST /commander/rescue-command`, `POST /commander/jobs/assign`), triggering missions (`MSN-...`), rescue commands (`CMD-...`), and work assignments (`ASN-...`).
4. **Notification Dispatch:** Live dispatch to mobile rescuers via SMSGate Local Server (`backend/notification_dispatch.py`), SQLite persistence (`backend/db.py`), and Bluetooth Low Energy smartwatch commands (`backend/wearable_gateway.py`).
5. **Rescuer Android Companion & Wearables:** Android Kotlin Companion app (`android-companion`) acting as a bridge between the backend, rescuer GPS, and physical Wave Call Plus BLE smartwatches.

This analysis details the current architecture, alert entry points, notification mechanisms, database schemas, frontend status views, dependencies, risk areas, and strict non-modification boundaries.

---

## 2. Existing Communication Flow & Architecture

```
                                  RIDGEWATCH DISASTER ECOSYSTEM
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
       SURVIVOR SENSOR STREAM                                        COMMANDER INTERFACE
  (Bioradar, Thermal, PIR, CO2,                                  (Incident Commander Dashboard
   Acoustic, Pressure, Tilt, etc.)                                 /frontend/commander.html)
                 │                                                             │
                 ▼                                                             ▼
        [fusion_engine.py]                                            [api.py POST /rescue-command]
        [scenario_intelligence.py]                                    [api.py POST /jobs/assign]
                 │                                                             │
                 ▼                                                             ▼
        [alert_dispatch.py]                                           [notification_dispatch.py]
  (Calculates SPS, Triage Class,                                  (Resolves E.164 Recipient Phone,
   Simulated Network Alerts)                                       Builds Mission Instructions)
                 │                                                             │
                 │                                            ┌────────────────┴────────────────┐
                 │                                            ▼                                 ▼
                 │                                   [SMSGate HTTP POST]              [wearable_gateway.py]
                 │                                   (POST /message to SIM)           (BLE Wave Call Plus)
                 │                                            │                                 │
                 ▼                                            ▼                                 ▼
        [backend/db.py]                             [backend/db.py]                   [Android Bridge]
      (network_alerts table)                     (notification_center &            (GNSS + GATT Packets)
                                                 rescue_commands tables)
```

### 2.1 Alert Generation Entry Points
- **Automated Sensor Detection Alerts:** `alert_dispatch.py:NetworkAlertDispatcher.send_alert()` generates `AlertRecord` entries logged to the `network_alerts` table in `backend/db.py`.
- **Commander Emergency Rescue Missions:** `api.py:assign_commander_rescue_command()` creates `rescue_commands` rows and invokes `notification_dispatch.py:dispatch_rescue_command_notifications()`.
- **Commander Work/Job Assignments:** `api.py:assign_commander_job()` creates `job_assignments` rows and invokes `notification_dispatch.py:dispatch_job_assignment_notifications()`.
- **Hazard Intelligence Ledger Alerts:** `scenario_intelligence.py:ScenarioIntelligenceEngine.evaluate_cycle()` generates `active_alerts_ledger` entries.

### 2.2 Existing Notification Dispatching Mechanism
`backend/notification_dispatch.py` provides the current multi-channel notification entry point:
- **Phone Number Resolution:** `resolve_recipient_mobile()` looks up personnel records from `personnel` / `admin_team_members` tables in `backend/db.py`.
- **E.164 Normalization:** `normalize_phone_number_e164()` cleans and validates international and national Indian mobile numbers (e.g. `8098897666` -> `+918098897666`).
- **SMSGate Gateway Dispatch:** `dispatch_smsgate_sms()` sends HTTP POST requests to the local Android SMSGate server (`POST {SMSGATE_LOCAL_URL}/message`) using Basic Auth (`SMSGATE_USERNAME`, `SMSGATE_PASSWORD`).
- **Two-Way SMS Inbound Polling:** `poll_smsgate_inbound_messages()` polls `GET {SMSGATE_LOCAL_URL}/inbox`, parses `ACCEPT <CMD_ID>` commands with `parse_sms_acceptance_command()`, and invokes `api.py:accept_rescue_assignment()`.
- **Deduplication:** Uses SQLite table `processed_inbound_sms` to prevent duplicate processing of inbound SMS messages across polling cycles.

### 2.3 Existing SMS Gateway Integration Details
- **Protocol:** HTTP REST with JSON payloads over local LAN/Wi-Fi or cellular tether.
- **Endpoint:** `POST /message` with payload:
  ```json
  {
    "textMessage": {
      "text": "<Alert content with ACCEPT instructions>"
    },
    "phoneNumbers": ["+918098897666"],
    "simNumber": 1
  }
  ```
- **Health Check:** `GET /health` with Basic Auth.
- **Inbox Polling:** `GET /inbox` returns JSON array of SMS messages.
- **Safety Flags:** `SMSGATE_ENABLED=false` disables live dispatch; `ALLOW_REAL_SMSGATE_IN_TESTS=false` forces test mock responses without hitting physical devices.

### 2.4 Existing LoRa Capabilities & Code State
- In `backend/alert_dispatch.py`, `CHANNEL_LORA` is simulated with baseline latency (1200 ms) and battery-dependent packet loss.
- In `backend/communication_fallback.py`, an early prototype `CommunicationManager` contains an in-memory enum `BearerType.LORA_MESH_ADAPTER` with simulated packet dispatch.
- **Hardware Integration Status:** No direct physical UART/SPI LoRa hardware driver (e.g. SX1262, SX1276, or Serial AT-command modem) is currently wired in production. A structured hardware adapter with safe simulation/mocking and packet formatting is required.

---

## 3. Database Schema Mapping (Alerts & Notifications)

| Table Name | File Location | Key Fields | Purpose |
|---|---|---|---|
| `notification_center` | `backend/db.py` (L268, L2099) | `id`, `alert_id`, `type`, `title`, `message`, `priority`, `status`, `watch_delivery_status`, `watch_ack_status`, `team_id`, `member_id`, `victim_id`, `phone_number`, `sms_status`, `sms_error`, `timestamp` | Historical ledger of all multi-channel alert notifications displayed in UI. |
| `rescue_commands` | `backend/db.py` (L4672, L4976) | `command_id`, `mission_id`, `team_id`, `member_id`, `victim_id`, `priority`, `status`, `watch_delivery_status`, `phone_number`, `sms_status`, `sms_error`, `created_at`, `delivered_at`, `acknowledged_at` | Authoritative single source of truth for rescue missions and assignments. |
| `job_assignments` | `backend/db.py` (L1650) | `assignment_id`, `job_id`, `team_id`, `person_id`, `status`, `notes`, `created_at`, `accepted_at` | Task and work assignments issued by Commander to field staff. |
| `processed_inbound_sms` | `backend/db.py` (L4735, L5374) | `message_id`, `sender`, `content`, `parsed_command_id`, `processed_at`, `status` | Deduplication table preventing re-processing of SMS acceptance messages. |
| `network_alerts` | `backend/db.py` (L189, L1760) | `alert_id`, `session_id`, `victim_id`, `channel`, `triage_class`, `sps`, `status`, `attempts`, `latency_ms`, `timestamp` | Sensor node network transmission logs (GSM/LoRa). |
| `communication_queue` | `backend/db.py` (L680) | `message_id`, `recipient`, `payload`, `priority`, `active_bearer`, `status`, `retry_count`, `idempotency_key` | Legacy schema for queue fallback prototype. |

---

## 4. Frontend Status Views & Dashboards

1. **Notification Center (`frontend/notification.html`, `frontend/js/notification.js`):**
   - Displays real-time KPI cards: Total Notifications, Active Alerts, SMS Delivered, SMS Queued/Failed, Watch Confirmed.
   - Shows detailed notification table with Alert ID, Mission ID, Target Victim, Priority badge, SMS Delivery badge (`SENT`, `FAILED`, `QUEUED`), and Watch Delivery badge.
2. **Commander Operations Console (`frontend/commander.html`, `frontend/js/commander.js`):**
   - Displays active rescue missions, rescuer assignment dropdowns, live dispatch buttons, and dispatch status toasts.
3. **Bridge & Hardware Diagnostics (`frontend/bridge.html`, `frontend/hardware.html`, `frontend/watch.html`):**
   - Displays Android Companion Bridge heartbeat, GPS fix quality, Wave Call Plus Bluetooth connection state, and GATT packet delivery telemetry.

---

## 5. Dependency & Environment Map

### 5.1 Runtime Dependencies
- **Python 3.10+ / 3.14:** `fastapi`, `uvicorn`, `httpx`, `pydantic`, `python-dotenv`, `pytest`, standard library (`sqlite3`, `hashlib`, `asyncio`, `logging`, `dataclasses`).
- **Android Companion:** Android SDK 34, Kotlin 1.9.0, Jetpack Compose, OkHttp, Coroutines, Gradle 8.2.

### 5.2 Existing Environment Variables (`backend/.env`)
```bash
SMSGATE_ENABLED=true
SMSGATE_LOCAL_URL=http://192.168.1.50:8080
SMSGATE_USERNAME=admin
SMSGATE_PASSWORD=secret
SMSGATE_SIM_NUMBER=1
SMSGATE_TIMEOUT=10.0
SMSGATE_INBOUND_ENABLED=true
ALLOW_REAL_SMSGATE_IN_TESTS=false
SMS_PROVIDER=SMSGATE
```

---

## 6. Files That Must NOT Be Modified Unnecessarily

To preserve existing system integrity and avoid regression in core capabilities:

1. `backend/fusion_engine.py` — Core 18-modality sensor fusion and triage logic.
2. `backend/wearable_gateway.py` — Wave Call Plus Bluetooth Low Energy hardware abstraction and GATT packet protocol.
3. `backend/rescue_dispatch.py` — Physical vehicle/team dispatch simulation algorithms.
4. `backend/sensor_simulator.py` — Physics-based alpine sensor simulation.
5. `backend/debris_flow_detector.py` & `backend/landslide_detector.py` — Alpine geohazard detection pipelines.
6. `backend/subsurface_dsp.py` — Subsurface bioradar signal processing engine.
7. `backend/road_network.py` & `backend/evacuation_engine.py` — Graph routing and Dijkstra evacuation route generator.
8. `android-companion/app/src/main/java/org/ridgewatch/rescuer/bridge/WearableBleBridge.kt` — Wearable BLE driver.

---

## 7. Potential Integration Points for Multi-Channel Failover

1. **Additive Adapter Injection in `notification_dispatch.py`:**
   - In `dispatch_rescue_command_notifications()` and `dispatch_job_assignment_notifications()`, check feature flag `COMMUNICATION_FAILOVER_ENABLED`.
   - When enabled, delegate multi-bearer dispatch to `backend/communication/communication_router.py`.
   - When disabled (`COMMUNICATION_FAILOVER_ENABLED=false`), preserve 100% of existing behavior calling `dispatch_sms_channel()`.
2. **Dedicated Delivery Ledger Table:**
   - Add `communication_delivery` table in `backend/db.py` to record multi-channel routing decisions, provider message IDs, retries, and acknowledgements.
3. **Dedicated Communication Status Endpoints in `backend/api.py`:**
   - Expose `/api/v1/communication/status`, `/api/v1/communication/messages`, and `/api/v1/communication/retry` as additive endpoints.

---

## 8. Risk Analysis & Mitigation Strategies

| Risk Area | Severity | Impact | Mitigation Strategy |
|---|---|---|---|
| Modifying core notification dispatch breaks existing test suite (972 tests) | HIGH | System regression | Encapsulate new logic behind `COMMUNICATION_FAILOVER_ENABLED=false` default flag; wrap existing functions via adapters. |
| LoRa hardware dependency blocks backend startup | HIGH | Startup failure | Provide robust `MockLoRaAdapter` / `SimulatedLoRaAdapter` with realistic packet formatting and RSSI/SNR metrics. |
| Database locking during concurrent 90-recipient queue dispatch | MEDIUM | Latency spikes | Use short-lived SQLite connections with WAL mode and asynchronous background worker queues. |
| Credential leakage in communication logs | HIGH | Security vulnerability | Implement strict phone number masking (E.164 masked) and redact passwords/tokens in all loggers. |
| Duplicate message storm across multiple bearers | HIGH | Rescuer confusion | Implement deterministic idempotency keys (`RW-YYYYMMDD-HASH`) and cross-bearer deduplication checks before transmission. |

---

## 9. Conclusion

The RidgeWatch existing communication stack is modular, well-tested, and clean. Implementing the Resilient Multi-Channel Emergency Communication Layer as an additive package in `backend/communication/` will provide enterprise-grade disaster resilience (Internet -> Cellular SMS -> LoRa RF -> Local Store-and-Forward) with zero disruption to the existing system.
