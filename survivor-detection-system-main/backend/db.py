



"""
db.py
-----
SQLite persistence layer for the AI-Based Multi-Sensor Survivor Detection &
Rescue Prioritization System.

Purpose
-------
Every simulated scenario run ("session") is logged to disk so that a full
run can be replayed, audited, or exported for the report's testing /
evaluation chapter, independent of the in-memory ScenarioState used by
api.py for live serving.

Tables
------
sessions
    One row per POST /scenario/start call: session_id, start time, and the
    scenario parameters (seed, degradation flag) used for that run.

sensor_readings
    One row per raw sensor reading emitted by sensor_simulator.py during a
    detection cycle (six per victim per cycle: thermal, PIR motion,
    acoustic, CO2, heart-rate radar, RGB camera).

detection_results
    One row per victim per detection cycle, capturing the fused output of
    fusion_engine.py: confidence %, triage class, hazard-adjusted SPS, and
    which sensors contributed.

rescue_status_events
    One row per rescue-team status change: multi-team auto-dispatch
    assignments (ALPHA/BRAVO) *and* single-agent dispatch-simulation
    arrivals ("victim reached"), each tagged by `event_type`.

network_alerts
    One row per simulated GSM/LoRa network-alert attempt fired for a
    HIGH-priority victim (see alert_dispatch.py) - latency, packet loss,
    retry count, and the sensor node's battery level at send time, so a
    reader can distinguish "alert badge shown in-app" from "alert actually
    made it out over the (simulated) network".

Everything is written through a short-lived sqlite3 connection per call
(simple and safe for this simulated, low-throughput workload - no
long-lived connection/locking concerns).

Query / export
---------------
export_session_csv(session_id)      -> CSV text, full unified session log
export_session_csv_file(session_id, path) -> writes CSV to `path`, returns path
list_sessions()                      -> summary of all logged sessions
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sqlite3
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Optional, Any, List, Dict, Tuple
from pathlib import Path
from dotenv import load_dotenv

for _env_path in [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / "backend" / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path("backend/.env"),
    Path(".env"),
]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break


# --------------------------------------------------------------------------- #
# Connection management
# --------------------------------------------------------------------------- #

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "survivor_detection.db")


@contextmanager
def _connect(db_path: Optional[str] = None):
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id          TEXT PRIMARY KEY,
    started_at           TEXT NOT NULL,
    seed                  INTEGER,
    enable_degradation    INTEGER NOT NULL,
    victim_count          INTEGER NOT NULL,
    scenario_id            TEXT,
    scenario_name           TEXT
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id         TEXT NOT NULL REFERENCES sessions(session_id),
    cycle               INTEGER NOT NULL,
    victim_id           TEXT NOT NULL,
    sensor_type         TEXT NOT NULL,
    value                REAL NOT NULL,
    unit                 TEXT,
    sensor_confidence    REAL,
    noisy                 INTEGER NOT NULL DEFAULT 0,
    timestamp            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_session
    ON sensor_readings(session_id);

CREATE TABLE IF NOT EXISTS detection_results (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id             TEXT NOT NULL REFERENCES sessions(session_id),
    cycle                   INTEGER NOT NULL,
    victim_id               TEXT NOT NULL,
    timestamp                TEXT NOT NULL,
    confidence_pct           REAL NOT NULL,
    triage_class             TEXT NOT NULL,
    sps                       REAL NOT NULL,
    hazard_multiplier         REAL NOT NULL,
    tapping_detected          INTEGER NOT NULL DEFAULT 0,
    contributing_sensors      TEXT
);
CREATE INDEX IF NOT EXISTS idx_detection_results_session
    ON detection_results(session_id);

CREATE TABLE IF NOT EXISTS rescue_status_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id         TEXT NOT NULL REFERENCES sessions(session_id),
    timestamp           TEXT NOT NULL,
    event_type          TEXT NOT NULL,      -- 'team_dispatched' | 'victim_reached' | ...
    team_id              TEXT,
    victim_id            TEXT,
    availability          TEXT,
    eta_minutes           REAL,
    arrival_order         INTEGER,
    travel_seconds         REAL,
    notes                  TEXT
);
CREATE INDEX IF NOT EXISTS idx_rescue_status_events_session
    ON rescue_status_events(session_id);

CREATE TABLE IF NOT EXISTS network_alerts (
    alert_id             TEXT PRIMARY KEY,
    session_id            TEXT NOT NULL REFERENCES sessions(session_id),
    victim_id              TEXT,
    channel                 TEXT,
    triage_class             TEXT,
    sps                       REAL,
    status                    TEXT,
    attempts                  INTEGER,
    latency_ms                 REAL,
    battery_pct_at_send          REAL,
    reason                        TEXT,
    timestamp                     TEXT
);
CREATE INDEX IF NOT EXISTS idx_network_alerts_session
    ON network_alerts(session_id);

CREATE TABLE IF NOT EXISTS sensor_health_records (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id            TEXT NOT NULL REFERENCES sessions(session_id),
    cycle                  INTEGER NOT NULL,
    sensor_id              TEXT NOT NULL,
    sensor_type            TEXT NOT NULL,
    status                 TEXT NOT NULL,
    battery_pct            REAL,
    signal_quality         REAL,
    error_message          TEXT,
    timestamp              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_health_session
    ON sensor_health_records(session_id);

CREATE TABLE IF NOT EXISTS sensor_trends (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id              TEXT NOT NULL REFERENCES sessions(session_id),
    cycle                    INTEGER NOT NULL,
    sensor_type              TEXT NOT NULL,
    current_value            REAL NOT NULL,
    rate_of_change           REAL NOT NULL,
    trend_direction          TEXT NOT NULL,
    is_spike                 INTEGER NOT NULL DEFAULT 0,
    is_sustained_abnormal    INTEGER NOT NULL DEFAULT 0,
    anomaly_score            REAL NOT NULL DEFAULT 0.0,
    timestamp                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_trends_session
    ON sensor_trends(session_id);

CREATE TABLE IF NOT EXISTS scenario_intelligence_ledger (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id                TEXT NOT NULL REFERENCES sessions(session_id),
    cycle                      INTEGER NOT NULL,
    primary_scenario_id        TEXT NOT NULL,
    primary_scenario_name      TEXT NOT NULL,
    confidence_pct             REAL NOT NULL,
    risk_level                 TEXT NOT NULL,
    survivor_status            TEXT NOT NULL,
    evidence_json              TEXT,
    secondary_scenarios_json   TEXT,
    recommended_action         TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scenario_intel_session
    ON scenario_intelligence_ledger(session_id);

CREATE TABLE IF NOT EXISTS active_alerts_ledger (
    alert_key                  TEXT PRIMARY KEY,
    session_id                 TEXT NOT NULL,
    hazard_type                TEXT NOT NULL,
    alert_title                TEXT NOT NULL,
    severity                   TEXT NOT NULL,
    confidence_pct             REAL,
    evidence_summary           TEXT,
    status                     TEXT NOT NULL DEFAULT 'ACTIVE',
    first_detected_at          TEXT NOT NULL,
    last_updated_at            TEXT NOT NULL,
    resolved_at                TEXT
);

CREATE TABLE IF NOT EXISTS notification_center (
    id                         TEXT PRIMARY KEY,
    alert_id                   TEXT NOT NULL,
    type                       TEXT NOT NULL,
    title                      TEXT NOT NULL,
    message                    TEXT NOT NULL,
    distance_m                 REAL,
    distance_label             TEXT,
    priority                   TEXT NOT NULL,
    status                     TEXT NOT NULL,
    watch_delivery_status      TEXT NOT NULL,
    watch_ack_status           TEXT NOT NULL,
    team_id                    TEXT,
    member_id                  TEXT,
    victim_id                  TEXT,
    timestamp                  TEXT NOT NULL,
    last_updated_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notification_center_timestamp
    ON notification_center(timestamp);
CREATE INDEX IF NOT EXISTS idx_notification_center_alert
    ON notification_center(alert_id);

CREATE TABLE IF NOT EXISTS gas_smoke_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    sensor_id                  TEXT NOT NULL,
    device_id                  TEXT NOT NULL,
    gas_type                   TEXT NOT NULL,
    gas_concentration          REAL NOT NULL,
    gas_unit                   TEXT NOT NULL,
    gas_level                  TEXT NOT NULL,
    smoke_density_pct          REAL NOT NULL,
    smoke_level                TEXT NOT NULL,
    rate_of_change_gas         REAL NOT NULL,
    rate_of_change_smoke       REAL NOT NULL,
    latitude                   REAL,
    longitude                  REAL,
    status                     TEXT NOT NULL,
    confidence                 REAL NOT NULL,
    quality                    REAL NOT NULL,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gas_smoke_session
    ON gas_smoke_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_gas_smoke_timestamp
    ON gas_smoke_readings(timestamp);

CREATE TABLE IF NOT EXISTS barometric_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    sensor_id                  TEXT NOT NULL,
    device_id                  TEXT NOT NULL,
    pressure_hpa               REAL NOT NULL,
    unit                       TEXT NOT NULL DEFAULT 'hPa',
    rate_of_change             REAL NOT NULL DEFAULT 0.0,
    trend                      TEXT NOT NULL DEFAULT 'STABLE',
    drop_severity              TEXT NOT NULL DEFAULT 'NORMAL',
    anomaly_level              TEXT NOT NULL DEFAULT 'NORMAL',
    latitude                   REAL,
    longitude                  REAL,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    confidence                 REAL NOT NULL DEFAULT 0.95,
    quality                    REAL NOT NULL DEFAULT 0.95,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_baro_session
    ON barometric_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_baro_sensor_id
    ON barometric_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_baro_timestamp
    ON barometric_readings(timestamp);

CREATE TABLE IF NOT EXISTS landslide_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    node_id                    TEXT NOT NULL,
    soil_moisture_pct          REAL NOT NULL,
    moisture_trend             TEXT NOT NULL DEFAULT 'STABLE',
    moisture_rate              REAL NOT NULL DEFAULT 0.0,
    tilt_x                     REAL,
    tilt_y                     REAL,
    tilt_z                     REAL,
    tilt_angle_deg             REAL NOT NULL,
    tilt_rate                  REAL NOT NULL DEFAULT 0.0,
    tilt_trend                 TEXT NOT NULL DEFAULT 'STABLE',
    risk_score                 REAL NOT NULL,
    risk_level                 TEXT NOT NULL,
    confidence                 REAL NOT NULL DEFAULT 0.95,
    event_state                TEXT NOT NULL DEFAULT 'NORMAL',
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    quality                    REAL NOT NULL DEFAULT 0.95,
    latitude                   REAL,
    longitude                  REAL,
    contributing_factors_json  TEXT,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_landslide_session
    ON landslide_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_landslide_node
    ON landslide_readings(node_id);
CREATE INDEX IF NOT EXISTS idx_landslide_timestamp
    ON landslide_readings(timestamp);

CREATE TABLE IF NOT EXISTS camera_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    camera_id                  TEXT NOT NULL,
    device_id                  TEXT NOT NULL,
    victim_id                  TEXT,
    detection_state            TEXT NOT NULL DEFAULT 'NO_DETECTION',
    detection_type             TEXT NOT NULL DEFAULT 'none',
    classification             TEXT NOT NULL DEFAULT 'UNKNOWN',
    classification_confidence  REAL NOT NULL DEFAULT 0.0,
    person_count               INTEGER NOT NULL DEFAULT 0,
    confidence                 REAL NOT NULL DEFAULT 0.0,
    visibility                 REAL NOT NULL DEFAULT 1.0,
    occlusion                  REAL NOT NULL DEFAULT 0.0,
    image_quality              REAL NOT NULL DEFAULT 1.0,
    motion_detected            INTEGER NOT NULL DEFAULT 0,
    smoke_present              INTEGER NOT NULL DEFAULT 0,
    fire_visible               INTEGER NOT NULL DEFAULT 0,
    debris_present             INTEGER NOT NULL DEFAULT 0,
    orientation                TEXT NOT NULL DEFAULT '0° NADIR',
    field_of_view_deg          REAL NOT NULL DEFAULT 85.0,
    range_m                    REAL NOT NULL DEFAULT 30.0,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    health_score               REAL NOT NULL DEFAULT 100.0,
    latitude                   REAL,
    longitude                  REAL,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_camera_session
    ON camera_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_camera_id
    ON camera_readings(camera_id);
CREATE INDEX IF NOT EXISTS idx_camera_victim
    ON camera_readings(victim_id);
CREATE INDEX IF NOT EXISTS idx_camera_timestamp
    ON camera_readings(timestamp);

CREATE TABLE IF NOT EXISTS thermal_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    camera_id                  TEXT NOT NULL,
    device_id                  TEXT NOT NULL,
    victim_id                  TEXT,
    detection_type             TEXT NOT NULL DEFAULT 'NO_HEAT',
    classification             TEXT NOT NULL DEFAULT 'NO_SIGNATURE',
    classification_confidence  REAL NOT NULL DEFAULT 0.0,
    heat_signature_detected    INTEGER NOT NULL DEFAULT 0,
    human_signature            INTEGER NOT NULL DEFAULT 0,
    heat_signature_count       INTEGER NOT NULL DEFAULT 0,
    thermal_confidence         REAL NOT NULL DEFAULT 0.0,
    estimated_temperature      REAL NOT NULL DEFAULT 20.0,
    background_temperature     REAL NOT NULL DEFAULT 18.0,
    temperature_delta          REAL NOT NULL DEFAULT 2.0,
    thermal_visibility         REAL NOT NULL DEFAULT 1.0,
    thermal_contrast           REAL NOT NULL DEFAULT 1.0,
    occlusion                  REAL NOT NULL DEFAULT 0.0,
    fire_hotspot               INTEGER NOT NULL DEFAULT 0,
    hot_debris                 INTEGER NOT NULL DEFAULT 0,
    orientation                TEXT NOT NULL DEFAULT '0° NADIR',
    field_of_view_deg          REAL NOT NULL DEFAULT 60.0,
    range_m                    REAL NOT NULL DEFAULT 40.0,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    health_score               REAL NOT NULL DEFAULT 100.0,
    latitude                   REAL,
    longitude                  REAL,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_thermal_session
    ON thermal_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_thermal_id
    ON thermal_readings(camera_id);
CREATE INDEX IF NOT EXISTS idx_thermal_victim
    ON thermal_readings(victim_id);
CREATE INDEX IF NOT EXISTS idx_thermal_timestamp
    ON thermal_readings(timestamp);

CREATE TABLE IF NOT EXISTS rainfall_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    cycle                      INTEGER NOT NULL DEFAULT 0,
    sensor_id                  TEXT NOT NULL DEFAULT 'ENV-RAIN-01',
    device_id                  TEXT NOT NULL DEFAULT 'DEV-RAIN-01',
    rainfall_rate_mm_h         REAL NOT NULL DEFAULT 0.0,
    cumulative_rainfall_mm     REAL NOT NULL DEFAULT 0.0,
    unit                       TEXT NOT NULL DEFAULT 'mm/h',
    rate_of_change             REAL NOT NULL DEFAULT 0.0,
    trend                      TEXT NOT NULL DEFAULT 'STABLE',
    classification             TEXT NOT NULL DEFAULT 'NO_RAIN',
    severity                   TEXT NOT NULL DEFAULT 'LOW',
    latitude                   REAL,
    longitude                  REAL,
    altitude_m                 REAL,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    confidence                 REAL NOT NULL DEFAULT 0.98,
    quality                    REAL NOT NULL DEFAULT 0.98,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rainfall_session
    ON rainfall_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_rainfall_sensor_id
    ON rainfall_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_rainfall_timestamp
    ON rainfall_readings(timestamp);

CREATE TABLE IF NOT EXISTS temperature_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    cycle                      INTEGER NOT NULL DEFAULT 0,
    sensor_id                  TEXT NOT NULL DEFAULT 'ENV-TEMP-01',
    device_id                  TEXT NOT NULL DEFAULT 'DEV-TEMP-01',
    temperature_c              REAL NOT NULL DEFAULT 15.0,
    ambient_temp_c             REAL NOT NULL DEFAULT 15.0,
    unit                       TEXT NOT NULL DEFAULT '°C',
    rate_of_change             REAL NOT NULL DEFAULT 0.0,
    trend                      TEXT NOT NULL DEFAULT 'STABLE',
    latitude                   REAL,
    longitude                  REAL,
    altitude_m                 REAL,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    confidence                 REAL NOT NULL DEFAULT 0.98,
    quality                    REAL NOT NULL DEFAULT 0.98,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_temp_session
    ON temperature_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_temp_sensor_id
    ON temperature_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_temp_timestamp
    ON temperature_readings(timestamp);

CREATE TABLE IF NOT EXISTS humidity_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    cycle                      INTEGER NOT NULL DEFAULT 0,
    sensor_id                  TEXT NOT NULL DEFAULT 'ENV-HUMID-01',
    device_id                  TEXT NOT NULL DEFAULT 'DEV-HUMID-01',
    humidity_pct               REAL NOT NULL DEFAULT 50.0,
    unit                       TEXT NOT NULL DEFAULT '%',
    rate_of_change             REAL NOT NULL DEFAULT 0.0,
    trend                      TEXT NOT NULL DEFAULT 'STABLE',
    latitude                   REAL,
    longitude                  REAL,
    altitude_m                 REAL,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    confidence                 REAL NOT NULL DEFAULT 0.98,
    quality                    REAL NOT NULL DEFAULT 0.98,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_humidity_session
    ON humidity_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_humidity_sensor_id
    ON humidity_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_humidity_timestamp
    ON humidity_readings(timestamp);

CREATE TABLE IF NOT EXISTS water_level_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    cycle                      INTEGER NOT NULL DEFAULT 0,
    sensor_id                  TEXT NOT NULL DEFAULT 'ENV-WATER-01',
    device_id                  TEXT NOT NULL DEFAULT 'DEV-WATER-01',
    water_level_cm             REAL NOT NULL DEFAULT 0.0,
    water_flow_mps             REAL NOT NULL DEFAULT 0.0,
    unit                       TEXT NOT NULL DEFAULT 'cm',
    rate_of_change             REAL NOT NULL DEFAULT 0.0,
    trend                      TEXT NOT NULL DEFAULT 'STABLE',
    classification             TEXT NOT NULL DEFAULT 'NORMAL',
    severity                   TEXT NOT NULL DEFAULT 'LOW',
    latitude                   REAL,
    longitude                  REAL,
    altitude_m                 REAL,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    confidence                 REAL NOT NULL DEFAULT 0.98,
    quality                    REAL NOT NULL DEFAULT 0.98,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_water_level_session
    ON water_level_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_water_level_sensor_id
    ON water_level_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_water_level_timestamp
    ON water_level_readings(timestamp);

CREATE TABLE IF NOT EXISTS gps_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id                 TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    cycle                      INTEGER NOT NULL DEFAULT 0,
    sensor_id                  TEXT NOT NULL DEFAULT 'DEV-GPS-01',
    device_id                  TEXT NOT NULL DEFAULT 'RESCUE-KIT-01',
    sensor_type                TEXT NOT NULL DEFAULT 'gps',
    latitude                   REAL NOT NULL DEFAULT 32.3739,
    longitude                  REAL NOT NULL DEFAULT 77.2491,
    altitude_m                 REAL NOT NULL DEFAULT 3950.0,
    accuracy_m                 REAL NOT NULL DEFAULT 2.5,
    speed_mps                  REAL NOT NULL DEFAULT 0.0,
    heading_deg                REAL NOT NULL DEFAULT 0.0,
    satellites                 INTEGER NOT NULL DEFAULT 12,
    movement_state             TEXT NOT NULL DEFAULT 'STATIONARY',
    is_valid_fix               INTEGER NOT NULL DEFAULT 1,
    status                     TEXT NOT NULL DEFAULT 'ONLINE',
    confidence                 REAL NOT NULL DEFAULT 0.98,
    quality                    REAL NOT NULL DEFAULT 0.98,
    scenario_id                TEXT,
    entity_type                TEXT NOT NULL DEFAULT 'DEVICE',
    entity_id                  TEXT,
    raw_data_json              TEXT,
    metadata_json              TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gps_session
    ON gps_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_gps_cycle
    ON gps_readings(cycle);
CREATE INDEX IF NOT EXISTS idx_gps_sensor_id
    ON gps_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_gps_timestamp
    ON gps_readings(timestamp);

CREATE TABLE IF NOT EXISTS rejected_sensor_readings (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    rejection_id               TEXT UNIQUE NOT NULL,
    session_id                 TEXT NOT NULL,
    cycle                      INTEGER NOT NULL DEFAULT 0,
    sensor_type                TEXT NOT NULL,
    sensor_id                  TEXT,
    device_id                  TEXT,
    victim_id                  TEXT,
    attempted_value            REAL,
    unit                       TEXT,
    rejection_reason           TEXT NOT NULL,
    raw_payload_json           TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rejected_session
    ON rejected_sensor_readings(session_id);
CREATE INDEX IF NOT EXISTS idx_rejected_sensor_type
    ON rejected_sensor_readings(sensor_type);
CREATE INDEX IF NOT EXISTS idx_rejected_timestamp
    ON rejected_sensor_readings(timestamp);

CREATE TABLE IF NOT EXISTS flood_risk_assessments (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id                 TEXT NOT NULL,
    assessment_id              TEXT UNIQUE NOT NULL,
    water_depth_m              REAL NOT NULL,
    measured_distance_m        REAL NOT NULL,
    rise_rate_mps              REAL NOT NULL,
    estimated_pressure_kpa     REAL NOT NULL,
    rainfall_intensity_mmh     REAL NOT NULL,
    risk_score                 REAL NOT NULL,
    risk_level                 TEXT NOT NULL,
    warning_issued             INTEGER NOT NULL DEFAULT 0,
    evacuation_recommended     INTEGER NOT NULL DEFAULT 0,
    time_to_inundation_minutes REAL,
    reading_quality            TEXT NOT NULL DEFAULT 'VALID',
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flood_assess_session
    ON flood_risk_assessments(session_id);
CREATE INDEX IF NOT EXISTS idx_flood_assess_timestamp
    ON flood_risk_assessments(timestamp);

CREATE TABLE IF NOT EXISTS evacuation_recommendations (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id          TEXT UNIQUE NOT NULL,
    zone_id                    TEXT NOT NULL,
    zone_name                  TEXT NOT NULL,
    assembly_point_id          TEXT NOT NULL,
    assembly_point_name        TEXT NOT NULL,
    urgency                    TEXT NOT NULL,
    route_confidence           TEXT NOT NULL,
    transit_minutes            REAL NOT NULL,
    safety_margin_minutes      REAL,
    avoided_hazards_json       TEXT,
    instructions_json          TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evac_rec_timestamp
    ON evacuation_recommendations(timestamp);

CREATE TABLE IF NOT EXISTS communication_queue (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id                 TEXT UNIQUE NOT NULL,
    recipient                  TEXT NOT NULL,
    payload                    TEXT NOT NULL,
    priority                   TEXT NOT NULL,
    active_bearer              TEXT,
    status                     TEXT NOT NULL,
    retry_count                INTEGER NOT NULL DEFAULT 0,
    idempotency_key            TEXT,
    created_at                 TEXT NOT NULL,
    delivered_at               TEXT
);
CREATE INDEX IF NOT EXISTS idx_comm_queue_status
    ON communication_queue(status);

CREATE TABLE IF NOT EXISTS communication_delivery (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id                 TEXT UNIQUE NOT NULL,
    alert_id                   TEXT,
    rescue_command_id          TEXT,
    mission_id                 TEXT,
    channel                    TEXT NOT NULL,
    recipient                  TEXT NOT NULL,
    recipient_masked           TEXT NOT NULL,
    priority                   TEXT NOT NULL DEFAULT 'HIGH',
    status                     TEXT NOT NULL DEFAULT 'QUEUED',
    retry_count                INTEGER NOT NULL DEFAULT 0,
    max_retries                INTEGER NOT NULL DEFAULT 3,
    provider_message_id        TEXT,
    idempotency_key            TEXT NOT NULL,
    error                      TEXT,
    payload                    TEXT NOT NULL,
    compact_payload            TEXT,
    created_at                 TEXT NOT NULL,
    updated_at                 TEXT NOT NULL,
    dispatched_at              TEXT,
    delivered_at               TEXT,
    acknowledged_at            TEXT,
    expires_at                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_comm_delivery_msg_id
    ON communication_delivery(message_id);
CREATE INDEX IF NOT EXISTS idx_comm_delivery_status
    ON communication_delivery(status);
CREATE INDEX IF NOT EXISTS idx_comm_delivery_alert
    ON communication_delivery(alert_id);
CREATE INDEX IF NOT EXISTS idx_comm_delivery_idem
    ON communication_delivery(idempotency_key);

CREATE TABLE IF NOT EXISTS sensor_health_audit_log (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id                  TEXT NOT NULL,
    sensor_type                TEXT NOT NULL,
    battery_volts              REAL,
    battery_pct                INTEGER,
    rssi_dbm                   INTEGER,
    health_status              TEXT NOT NULL,
    diagnostics_json           TEXT,
    timestamp                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_health_audit_dev
    ON sensor_health_audit_log(device_id);
"""


def init_db(db_path: Optional[str] = None) -> None:
    """Create all tables (idempotent) if they don't already exist."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        _ensure_admin_registry_tables(conn)   # Step 29: Personnel/Scenario-history/Teams registry
        _ensure_wearable_tables(conn)         # Real Wearable IoT & Bridge persistence
        # Migration for DB files created before scenario_id/scenario_name
        # were added to `sessions` (Step 8: scenario config system) -
        # ALTER TABLE ADD COLUMN is a no-op-safe way to upgrade in place.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
        for col in ("scenario_id", "scenario_name"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} TEXT")


# --------------------------------------------------------------------------- #
# Writes - sessions
# --------------------------------------------------------------------------- #

def create_session(
    session_id: str,
    seed: Optional[int],
    enable_degradation: bool,
    victim_count: int,
    started_at: Optional[str] = None,
    scenario_id: Optional[str] = None,
    scenario_name: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
                (session_id, started_at, seed, enable_degradation, victim_count,
                 scenario_id, scenario_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, started_at or _now(), seed, int(enable_degradation),
                victim_count, scenario_id, scenario_name,
            ),
        )


def update_session_victim_count(
    session_id: str,
    victim_count: int,
    db_path: Optional[str] = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE sessions SET victim_count = ? WHERE session_id = ?",
            (victim_count, session_id),
        )


# --------------------------------------------------------------------------- #
# Writes - detection cycle (sensor readings + fused results)
# --------------------------------------------------------------------------- #

def log_detection_cycle(
    session_id: str,
    cycle: int,
    readings: Iterable,
    fusion_results_by_victim: dict,
    db_path: Optional[str] = None,
) -> None:
    """
    Log one detection cycle in a single transaction:
      * every raw SensorReading emitted this cycle (`readings`)
      * the current fused DetectionResult / FusionResult per victim
        (`fusion_results_by_victim`, victim_id -> FusionResult)

    Safe to call every simulator tick - each call is its own transaction.
    """
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO sensor_readings
                (session_id, cycle, victim_id, sensor_type, value, unit,
                 sensor_confidence, noisy, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    session_id,
                    cycle,
                    r.victim_id or "SITE",
                    r.sensor_type.value if hasattr(r.sensor_type, "value") else r.sensor_type,
                    r.value,
                    r.unit,
                    r.confidence,
                    int(bool(r.noisy)),
                    r.timestamp,
                )
                for r in readings
            ],
        )

        conn.executemany(
            """
            INSERT INTO detection_results
                (session_id, cycle, victim_id, timestamp, confidence_pct,
                 triage_class, sps, hazard_multiplier, tapping_detected,
                 contributing_sensors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    session_id,
                    cycle,
                    victim_id,
                    result.timestamp,
                    result.confidence_pct,
                    result.triage_class.value if hasattr(result.triage_class, "value") else result.triage_class,
                    result.sps,
                    result.hazard_multiplier,
                    int(bool(result.tapping_detected)),
                    ",".join(result.contributing_sensors) if result.contributing_sensors else "",
                )
                for victim_id, result in fusion_results_by_victim.items()
            ],
        )


# --------------------------------------------------------------------------- #
# Writes - rescue team status events
# --------------------------------------------------------------------------- #

def log_rescue_status_event(
    session_id: str,
    event_type: str,
    team_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    availability: Optional[str] = None,
    eta_minutes: Optional[float] = None,
    arrival_order: Optional[int] = None,
    travel_seconds: Optional[float] = None,
    notes: str = "",
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """
    Log a single rescue-team status change, e.g.:
      * event_type="team_dispatched" - a multi-team auto-dispatch assignment
        (ALPHA/BRAVO en route to a victim, with ETA)
      * event_type="victim_reached"  - the single-agent dispatch simulation
        physically arriving at a victim (with arrival order + travel time)
    """
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO sessions (session_id, started_at, enable_degradation, victim_count)
            VALUES (?, ?, 0, 0)
            """,
            (session_id, timestamp or _now()),
        )
        conn.execute(
            """
            INSERT INTO rescue_status_events
                (session_id, timestamp, event_type, team_id, victim_id,
                 availability, eta_minutes, arrival_order, travel_seconds, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                timestamp or _now(),
                event_type,
                team_id,
                victim_id,
                availability,
                eta_minutes,
                arrival_order,
                travel_seconds,
                notes,
            ),
        )


# --------------------------------------------------------------------------- #
# Admin registry - Personnel / Scenario history / Teams (Step 29)
# --------------------------------------------------------------------------- #
# These are deliberately separate from the sensor-fusion tables above: they
# persist across scenario reset/restart (a rescuer's staff record shouldn't
# vanish just because the demo scenario was reset), and Personnel is
# explicitly NOT the same entity as a victim/needy-person (V1-V4, lat/lng) -
# conflating the two would be a safety-critical mistake (assigning a
# disaster victim as if they were rescue-team staff).

def _ensure_admin_registry_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS personnel (
            person_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            dob TEXT, gender TEXT, phone TEXT, email TEXT, address TEXT,
            role TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Active',
            badge_id TEXT,
            scenarios TEXT,
            created_at TEXT NOT NULL
        )
    """)
    # Migration: Ensure scenarios column exists for pre-existing personnel tables
    cols = [r[1] for r in conn.execute("PRAGMA table_info(personnel)").fetchall()]
    if "scenarios" not in cols:
        conn.execute("ALTER TABLE personnel ADD COLUMN scenarios TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS personnel_scenarios (
            person_id TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            PRIMARY KEY (person_id, scenario_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_scenarios (
            scenario_ref_id TEXT PRIMARY KEY,
            scenario_name TEXT NOT NULL, hazard_type TEXT NOT NULL,
            victim_count INTEGER NOT NULL, latitude REAL, longitude REAL,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    # Ensure updated_at column exists for pre-existing tables
    cols = [r[1] for r in conn.execute("PRAGMA table_info(admin_scenarios)").fetchall()]
    if "updated_at" not in cols:
        conn.execute("ALTER TABLE admin_scenarios ADD COLUMN updated_at TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_teams (
            team_ref_id TEXT PRIMARY KEY,
            team_name TEXT UNIQUE NOT NULL, team_type TEXT, description TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_team_members (
            team_ref_id TEXT NOT NULL, person_id TEXT NOT NULL,
            role_on_team TEXT, added_at TEXT NOT NULL,
            PRIMARY KEY (team_ref_id, person_id),
            FOREIGN KEY(team_ref_id) REFERENCES admin_teams(team_ref_id)
        )
    """)

    # Self-healing index & deduplication for existing DB files created before UNIQUE constraints
    try:
        conn.execute("""
            DELETE FROM admin_team_members WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM admin_team_members GROUP BY team_ref_id, person_id
            )
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_team_members_unique ON admin_team_members(team_ref_id, person_id)")
    except Exception:
        pass

    try:
        conn.execute("""
            DELETE FROM admin_teams WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM admin_teams GROUP BY team_name
            )
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_teams_name ON admin_teams(team_name)")
    except Exception:
        pass

    try:
        conn.execute("UPDATE personnel SET phone = '+91-80988-97666' WHERE person_id = 'P-ALPHA-01' OR full_name = 'Alpha Member 1'")
    except Exception:
        pass

    # Scenario-Based Commander Jobs & Assignments
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commander_jobs (
            job_id TEXT PRIMARY KEY,
            job_name TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            scenario_name TEXT NOT NULL,
            location TEXT,
            latitude REAL,
            longitude REAL,
            priority TEXT NOT NULL DEFAULT 'HIGH',
            description TEXT,
            status TEXT NOT NULL DEFAULT 'OPEN',
            victim_id TEXT,
            created_by TEXT NOT NULL DEFAULT 'Commander',
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_assignments (
            assignment_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            personnel_id TEXT,
            team_id TEXT,
            scenario_id TEXT NOT NULL,
            assigned_by TEXT NOT NULL DEFAULT 'Commander',
            status TEXT NOT NULL DEFAULT 'ASSIGNED',
            progress_pct INTEGER NOT NULL DEFAULT 0,
            result_notes TEXT,
            acceptance_source TEXT,
            accepted_at TEXT,
            assigned_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY(job_id) REFERENCES commander_jobs(job_id)
        )
    """)

    # Migration for existing job_assignments tables
    existing_job_assign_cols = {row["name"] for row in conn.execute("PRAGMA table_info(job_assignments)")}
    for col, ctype in [
        ("acceptance_source", "TEXT"),
        ("accepted_at", "TEXT"),
    ]:
        if col not in existing_job_assign_cols:
            conn.execute(f"ALTER TABLE job_assignments ADD COLUMN {col} {ctype}")


def seed_builtin_scenarios(db_path=None) -> None:
    """Ensure standard disaster templates exist in the scenarios ledger with default Active status."""
    builtin = [
        ("earthquake_building_collapse", "Urban Earthquake Collapse", "earthquake", 5, 28.6139, 77.2090),
        ("flood_urban", "Flash Flood Surge", "flood", 4, 19.0760, 72.8777),
        ("wildfire_forest", "Wildfire Forest Fire", "wildfire", 4, 30.3165, 78.0322),
        ("chemical_gas_leak", "Chemical Toxic Gas Hazard", "chemical_leak", 4, 22.3072, 73.1812),
        ("himalaya_avalanche", "Himalaya Avalanche", "avalanche", 4, 32.3739, 77.2491),
    ]
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        now_ts = _now()
        for ref_id, name, hazard, victims, lat, lon in builtin:
            conn.execute(
                """
                INSERT OR IGNORE INTO admin_scenarios
                    (scenario_ref_id, scenario_name, hazard_type, victim_count, latitude, longitude, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'Active', ?)
                """,
                (ref_id, name, hazard, victims, lat, lon, now_ts),
            )


def seed_builtin_teams(db_path=None) -> None:
    """Ensure exactly 2 standard active rescue teams with 2 personnel each exist in the admin registry."""
    builtin_teams = [
        (
            "ALPHA", "Rescue Team Alpha", "USAR / Structural Collapse",
            "Specialized in structural collapse, void search, and confined-space extraction.",
            [
                ("P-ALPHA-01", "Alpha Member 1", "Team Leader", "+91-80988-97666", [
                    "earthquake", "building_collapse", "avalanche", "landslide", "flood", "wildfire",
                    "chemical_leak", "tsunami", "cyclone", "urban_fire", "industrial_accident",
                    "dam_failure", "drought", "heatwave", "cloudburst", "stampede",
                    "transport_accident", "infrastructure_entrapment", "multi_hazard"
                ]),
                ("P-ALPHA-02", "Alpha Member 2", "Search Specialist", "+91-98765-01002", [
                    "earthquake", "building_collapse", "avalanche", "landslide", "flood", "wildfire",
                    "chemical_leak", "tsunami", "cyclone", "urban_fire", "industrial_accident",
                    "dam_failure", "drought", "heatwave", "cloudburst", "stampede",
                    "transport_accident", "infrastructure_entrapment", "multi_hazard"
                ]),
            ]
        ),
        (
            "BRAVO", "Rescue Team Bravo", "Medical / Emergency Care",
            "Advanced trauma life support, field triage, hypothermia treatment, and medical stabilization.",
            [
                ("P-BRAVO-01", "Bravo Member 1", "Medical Lead", "+91-98765-02001", [
                    "earthquake", "avalanche", "flood", "wildfire", "chemical_leak", "tsunami",
                    "cyclone", "landslide", "building_collapse", "urban_fire", "industrial_accident",
                    "dam_failure", "drought", "heatwave", "cloudburst", "stampede",
                    "transport_accident", "infrastructure_entrapment", "multi_hazard"
                ]),
                ("P-BRAVO-02", "Bravo Member 2", "Triage Paramedic", "+91-98765-02002", [
                    "earthquake", "avalanche", "flood", "wildfire", "chemical_leak", "tsunami",
                    "cyclone", "landslide", "building_collapse", "urban_fire", "industrial_accident",
                    "dam_failure", "drought", "heatwave", "cloudburst", "stampede",
                    "transport_accident", "infrastructure_entrapment", "multi_hazard"
                ]),
            ]
        ),
    ]
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        now_ts = _now()
        for team_ref_id, name, t_type, desc, members in builtin_teams:
            conn.execute(
                """
                INSERT INTO admin_teams (team_ref_id, team_name, team_type, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(team_ref_id) DO UPDATE SET
                    team_name = excluded.team_name,
                    team_type = excluded.team_type,
                    description = excluded.description
                """,
                (team_ref_id, name, t_type, desc, now_ts),
            )
            for p_id, p_name, role, phone, sc_list in members:
                sc_json, _ = _format_scenarios_input(sc_list)
                conn.execute(
                    """
                    INSERT INTO personnel (person_id, full_name, role, phone, status, scenarios, created_at)
                    VALUES (?, ?, ?, ?, 'Active', ?, ?)
                    ON CONFLICT(person_id) DO UPDATE SET
                        full_name = excluded.full_name,
                        role = excluded.role,
                        phone = excluded.phone,
                        status = 'Active',
                        scenarios = excluded.scenarios
                    """,
                    (p_id, p_name, role, phone, sc_json, now_ts),
                )
                for sc in sc_list:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO personnel_scenarios (person_id, scenario_id)
                        VALUES (?, ?)
                        """,
                        (p_id, sc),
                    )
                conn.execute(
                    """
                    INSERT INTO admin_team_members (team_ref_id, person_id, role_on_team, added_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(team_ref_id, person_id) DO UPDATE SET
                        role_on_team = excluded.role_on_team
                    """,
                    (team_ref_id, p_id, role, now_ts),
                )


def reset_team_demo_data(db_path=None) -> None:
    """
    Safely reset the teams and personnel database tables to the clean authoritative
    baseline of exactly 2 teams (Rescue Team Alpha, Rescue Team Bravo) and 4 members
    (2 members per team), removing old/demo/testing teams and duplicate records.
    Preserves all sensor logs, sessions, alerts, and other non-registry data.
    """
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        conn.execute("DELETE FROM admin_team_members")
        conn.execute("DELETE FROM admin_teams")
        conn.execute("DELETE FROM personnel_scenarios")
        conn.execute("DELETE FROM personnel")
    seed_builtin_scenarios(db_path)
    seed_builtin_teams(db_path)


def _format_scenarios_input(scenarios) -> tuple[str, list[str]]:
    """Format and normalize scenarios to JSON string and list of strings."""
    import json
    if not scenarios:
        return json.dumps([]), []
    if isinstance(scenarios, str):
        try:
            parsed = json.loads(scenarios)
            if isinstance(parsed, list):
                clean_list = [str(s).strip() for s in parsed if str(s).strip()]
                return json.dumps(clean_list), clean_list
        except Exception:
            clean_list = [s.strip() for s in scenarios.split(",") if s.strip()]
            return json.dumps(clean_list), clean_list
        clean_list = [scenarios.strip()]
        return json.dumps(clean_list), clean_list
    clean_list = [str(s).strip() for s in scenarios if str(s).strip()]
    return json.dumps(clean_list), clean_list


def _parse_scenarios_json(scenarios_str: Optional[str]) -> list[str]:
    import json
    if not scenarios_str:
        return []
    try:
        parsed = json.loads(scenarios_str)
        if isinstance(parsed, list):
            return [str(s) for s in parsed]
        return [str(parsed)]
    except Exception:
        return [s.strip() for s in scenarios_str.split(",") if s.strip()]


def add_personnel(person_id, full_name, role, dob=None, gender=None, phone=None,
                   email=None, address=None, status="Active", badge_id=None,
                   scenarios=None, created_at=None, db_path=None) -> None:
    if scenarios is None:
        scenarios = ["earthquake", "avalanche", "flood", "building_collapse", "landslide"]
    scenarios_json, scenarios_list = _format_scenarios_input(scenarios)
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        conn.execute(
            "INSERT INTO personnel (person_id, full_name, dob, gender, phone, email, address, role, status, badge_id, scenarios, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (person_id, full_name, dob, gender, phone, email, address, role, status, badge_id, scenarios_json,
             created_at or _now()),
        )
        for s in scenarios_list:
            conn.execute(
                "INSERT OR IGNORE INTO personnel_scenarios (person_id, scenario_id) VALUES (?, ?)",
                (person_id, s),
            )


def update_personnel_scenarios(person_id: str, scenarios, db_path=None) -> bool:
    scenarios_json, scenarios_list = _format_scenarios_input(scenarios)
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        cur = conn.execute(
            "UPDATE personnel SET scenarios = ? WHERE person_id = ?",
            (scenarios_json, person_id),
        )
        conn.execute("DELETE FROM personnel_scenarios WHERE person_id = ?", (person_id,))
        for s in scenarios_list:
            conn.execute(
                "INSERT OR IGNORE INTO personnel_scenarios (person_id, scenario_id) VALUES (?, ?)",
                (person_id, s),
            )
        return cur.rowcount > 0


def get_personnel(person_id: str, db_path=None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        row = conn.execute("SELECT * FROM personnel WHERE person_id = ?", (person_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["scenarios"] = _parse_scenarios_json(d.get("scenarios"))
        return d


def list_personnel(db_path=None) -> list:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        rows = conn.execute("SELECT * FROM personnel ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["scenarios"] = _parse_scenarios_json(d.get("scenarios"))
            result.append(d)
        return result


def log_admin_scenario(scenario_ref_id, scenario_name, hazard_type, victim_count,
                        latitude=None, longitude=None, status="Active", created_at=None,
                        updated_at=None, db_path=None) -> None:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        status_val = (status or "Active").strip().capitalize()
        if status_val not in ("Active", "Inactive"):
            status_val = "Active"
        now_ts = _now()
        conn.execute(
            "INSERT OR REPLACE INTO admin_scenarios (scenario_ref_id, scenario_name, hazard_type, victim_count, latitude, longitude, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (scenario_ref_id, scenario_name, hazard_type, victim_count, latitude, longitude,
             status_val, created_at or now_ts, updated_at),
        )


def list_admin_scenarios(db_path=None) -> list:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        rows = conn.execute("SELECT * FROM admin_scenarios ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def set_admin_scenario_status(scenario_ref_id, status, db_path=None) -> bool:
    """Flip a scenario's ledger status between Active / Inactive.

    Returns True if a row was updated, False if scenario_ref_id doesn't exist.
    """
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        status_val = (status or "Active").strip().capitalize()
        if status_val not in ("Active", "Inactive"):
            status_val = "Active"
        now_ts = _now()
        cur = conn.execute(
            "UPDATE admin_scenarios SET status = ?, updated_at = ? WHERE scenario_ref_id = ?",
            (status_val, now_ts, scenario_ref_id),
        )
        return cur.rowcount > 0


def get_admin_scenario(scenario_ref_id, db_path=None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        row = conn.execute(
            "SELECT * FROM admin_scenarios WHERE scenario_ref_id = ?", (scenario_ref_id,)
        ).fetchone()
        return dict(row) if row else None


def create_admin_team(team_ref_id, team_name, team_type=None, description=None,
                       created_at=None, db_path=None) -> None:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        conn.execute(
            "INSERT INTO admin_teams (team_ref_id, team_name, team_type, description, created_at) VALUES (?,?,?,?,?)",
            (team_ref_id, team_name, team_type, description, created_at or _now()),
        )


def add_team_member(team_ref_id, person_id, role_on_team=None, added_at=None, db_path=None) -> None:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        conn.execute(
            """
            INSERT INTO admin_team_members (team_ref_id, person_id, role_on_team, added_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(team_ref_id, person_id) DO UPDATE SET
                role_on_team = excluded.role_on_team
            """,
            (team_ref_id, person_id, role_on_team, added_at or _now()),
        )


def list_admin_teams(db_path=None) -> list:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        teams = [dict(r) for r in conn.execute("SELECT * FROM admin_teams ORDER BY created_at DESC").fetchall()]
        for t in teams:
            members = conn.execute(
                "SELECT m.person_id, p.full_name, m.role_on_team, m.added_at, p.phone, p.scenarios "
                "FROM admin_team_members m JOIN personnel p ON p.person_id = m.person_id "
                "WHERE m.team_ref_id = ?", (t["team_ref_id"],),
            ).fetchall()
            member_dicts = []
            for m in members:
                md = dict(m)
                md["scenarios"] = _parse_scenarios_json(md.get("scenarios"))
                member_dicts.append(md)
            t["members"] = member_dicts
            t["member_count"] = len(t["members"])
        return teams


def get_admin_team(team_ref_id, db_path=None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        row = conn.execute(
            "SELECT * FROM admin_teams WHERE team_ref_id = ?", (team_ref_id,)
        ).fetchone()
        if not row:
            return None
        team = dict(row)
        members = conn.execute(
            "SELECT m.person_id, p.full_name, m.role_on_team, m.added_at, p.phone, p.scenarios "
            "FROM admin_team_members m JOIN personnel p ON p.person_id = m.person_id "
            "WHERE m.team_ref_id = ?", (team_ref_id,),
        ).fetchall()
        member_dicts = []
        for m in members:
            md = dict(m)
            md["scenarios"] = _parse_scenarios_json(md.get("scenarios"))
            member_dicts.append(md)
        team["members"] = member_dicts
        team["member_count"] = len(team["members"])
        return team


def list_team_roster_members(team_ref_id: str, db_path=None) -> list:
    """Return all roster members belonging to a team ref ID from admin_team_members joined with personnel."""
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        members = conn.execute(
            "SELECT m.person_id, p.full_name, m.role_on_team, m.added_at, p.phone, p.scenarios "
            "FROM admin_team_members m JOIN personnel p ON p.person_id = m.person_id "
            "WHERE m.team_ref_id = ? "
            "ORDER BY m.added_at ASC",
            (team_ref_id,),
        ).fetchall()
        member_dicts = []
        for m in members:
            md = dict(m)
            md["scenarios"] = _parse_scenarios_json(md.get("scenarios"))
            member_dicts.append(md)
        return member_dicts


def get_rescue_member(member_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    """Return rescue member details and latest location by member_id or personnel_id."""
    if not member_id:
        return None
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        _ensure_wearable_tables(conn)

        # 1. Look up live bridge session by member_id
        bridge_row = conn.execute(
            "SELECT * FROM bridge_sessions WHERE member_id = ? ORDER BY last_heartbeat DESC LIMIT 1",
            (member_id,),
        ).fetchone()

        # 2. Look up personnel / roster record
        person_row = conn.execute(
            """
            SELECT m.team_ref_id, m.person_id, p.full_name, m.role_on_team, p.phone, p.scenarios
            FROM admin_team_members m
            JOIN personnel p ON p.person_id = m.person_id
            WHERE m.person_id = ? OR p.person_id = ?
            LIMIT 1
            """,
            (member_id, member_id),
        ).fetchone()

        # Check job assignments if member_id might map to a personnel_id
        assigned_personnel_id = None
        if not person_row:
            job_row = conn.execute(
                "SELECT personnel_id, team_id FROM job_assignments WHERE member_id = ? ORDER BY assigned_at DESC LIMIT 1",
                (member_id,),
            ).fetchone()
            if job_row and job_row["personnel_id"]:
                assigned_personnel_id = job_row["personnel_id"]
                person_row = conn.execute(
                    """
                    SELECT m.team_ref_id, m.person_id, p.full_name, m.role_on_team, p.phone, p.scenarios
                    FROM admin_team_members m
                    JOIN personnel p ON p.person_id = m.person_id
                    WHERE m.person_id = ? OR p.person_id = ?
                    LIMIT 1
                    """,
                    (assigned_personnel_id, assigned_personnel_id),
                ).fetchone()

        # 3. Check wearable telemetry
        telemetry_row = conn.execute(
            "SELECT * FROM wearable_telemetry WHERE team_id = ? OR device_id = ? ORDER BY id DESC LIMIT 1",
            (member_id, member_id),
        ).fetchone()

        if not bridge_row and not person_row and not telemetry_row:
            return None

        team_id = None
        if bridge_row and bridge_row["team_id"]:
            team_id = bridge_row["team_id"]
        elif person_row and person_row["team_ref_id"]:
            team_id = person_row["team_ref_id"]

        lat = None
        lon = None
        alt = None
        if bridge_row and bridge_row["latitude"] is not None and bridge_row["longitude"] is not None:
            lat = float(bridge_row["latitude"])
            lon = float(bridge_row["longitude"])
            alt = float(bridge_row["altitude_m"]) if bridge_row["altitude_m"] is not None else None
        elif telemetry_row and telemetry_row["latitude"] is not None and telemetry_row["longitude"] is not None:
            lat = float(telemetry_row["latitude"])
            lon = float(telemetry_row["longitude"])
            alt = float(telemetry_row["altitude_m"]) if telemetry_row["altitude_m"] is not None else None

        rec = {
            "member_id": member_id,
            "personnel_id": person_row["person_id"] if person_row else assigned_personnel_id,
            "team_id": team_id,
            "full_name": person_row["full_name"] if person_row else "",
            "role": person_row["role_on_team"] if person_row else "",
            "phone": person_row["phone"] if person_row else None,
            "scenarios": _parse_scenarios_json(person_row["scenarios"]) if person_row else [],
        }
        if lat is not None and lon is not None:
            rec["location"] = {
                "latitude": lat,
                "longitude": lon,
                "altitude_m": alt,
            }
        return rec



# --------------------------------------------------------------------------- #
# Commander Jobs & Mission Assignments
# --------------------------------------------------------------------------- #

def create_commander_job(
    job_id: str,
    job_name: str,
    scenario_id: str,
    scenario_name: str,
    location: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    priority: str = "HIGH",
    description: Optional[str] = None,
    victim_id: Optional[str] = None,
    created_by: str = "Commander",
    created_at: Optional[str] = None,
    status: str = "OPEN",
    db_path: Optional[str] = None,
) -> dict:
    now_ts = created_at or _now()
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        conn.execute(
            """
            INSERT INTO commander_jobs
                (job_id, job_name, scenario_id, scenario_name, location,
                 latitude, longitude, priority, description, status,
                 victim_id, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, job_name, scenario_id, scenario_name, location,
                latitude, longitude, priority, description, status,
                victim_id, created_by, now_ts, now_ts,
            ),
        )
    return {
        "job_id": job_id,
        "job_name": job_name,
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "priority": priority,
        "description": description,
        "status": status,
        "victim_id": victim_id,
        "created_by": created_by,
        "created_at": now_ts,
        "updated_at": now_ts,
    }


def get_commander_job(job_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        row = conn.execute("SELECT * FROM commander_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        job = dict(row)
        assignments = conn.execute(
            "SELECT * FROM job_assignments WHERE job_id = ? ORDER BY assigned_at DESC",
            (job_id,),
        ).fetchall()
        job["assignments"] = [dict(a) for a in assignments]
        return job


def list_commander_jobs(
    scenario_id: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        query = "SELECT * FROM commander_jobs WHERE 1=1"
        params = []
        if scenario_id:
            query += " AND scenario_id = ?"
            params.append(scenario_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        jobs = []
        for r in rows:
            j = dict(r)
            assignments = conn.execute(
                "SELECT * FROM job_assignments WHERE job_id = ? ORDER BY assigned_at DESC",
                (j["job_id"],),
            ).fetchall()
            j["assignments"] = [dict(a) for a in assignments]
            j["assignment_count"] = len(j["assignments"])
            jobs.append(j)
        return jobs


def update_commander_job_status(
    job_id: str,
    status: str,
    db_path: Optional[str] = None,
) -> bool:
    now_ts = _now()
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        cur = conn.execute(
            "UPDATE commander_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
            (status, now_ts, job_id),
        )
        return cur.rowcount > 0


def create_job_assignment(
    assignment_id: str,
    job_id: str,
    member_id: str,
    personnel_id: Optional[str] = None,
    team_id: Optional[str] = None,
    scenario_id: str = "",
    assigned_by: str = "Commander",
    status: str = "ASSIGNED",
    progress_pct: int = 0,
    result_notes: Optional[str] = None,
    assigned_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    now_ts = assigned_at or _now()
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        conn.execute(
            """
            INSERT INTO job_assignments
                (assignment_id, job_id, member_id, personnel_id, team_id,
                 scenario_id, assigned_by, status, progress_pct, result_notes,
                 assigned_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assignment_id, job_id, member_id, personnel_id, team_id,
                scenario_id, assigned_by, status, progress_pct, result_notes,
                now_ts, now_ts,
            ),
        )
        # Update job status to ASSIGNED if currently OPEN
        conn.execute(
            "UPDATE commander_jobs SET status = 'ASSIGNED', updated_at = ? WHERE job_id = ? AND status = 'OPEN'",
            (now_ts, job_id),
        )
    return {
        "assignment_id": assignment_id,
        "job_id": job_id,
        "member_id": member_id,
        "personnel_id": personnel_id,
        "team_id": team_id,
        "scenario_id": scenario_id,
        "assigned_by": assigned_by,
        "status": status,
        "progress_pct": progress_pct,
        "result_notes": result_notes,
        "assigned_at": now_ts,
        "updated_at": now_ts,
    }


def get_job_assignment(assignment_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        row = conn.execute(
            "SELECT * FROM job_assignments WHERE assignment_id = ?", (assignment_id,)
        ).fetchone()
        return dict(row) if row else None


def list_job_assignments(
    job_id: Optional[str] = None,
    member_id: Optional[str] = None,
    personnel_id: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        query = "SELECT a.*, j.job_name, j.priority as job_priority, j.location as job_location, j.description as job_description FROM job_assignments a LEFT JOIN commander_jobs j ON j.job_id = a.job_id WHERE 1=1"
        params = []
        if job_id:
            query += " AND a.job_id = ?"
            params.append(job_id)
        if member_id:
            query += " AND (a.member_id = ? OR a.personnel_id = ?)"
            params.extend([member_id, member_id])
        elif personnel_id:
            query += " AND a.personnel_id = ?"
            params.append(personnel_id)
        if status:
            query += " AND a.status = ?"
            params.append(status)
        query += " ORDER BY a.assigned_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_active_job_assignment_for_member(member_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    """Retrieves the most recent active (non-terminal) work assignment for a specific team member."""
    assignments = list_job_assignments(member_id=member_id, db_path=db_path)
    for a in assignments:
        if a.get("status") not in ("COMPLETED", "FAILED", "CANCELLED"):
            return a
    return None


def update_job_assignment_status(
    assignment_id: str,
    status: str,
    progress_pct: Optional[int] = None,
    result_notes: Optional[str] = None,
    acceptance_source: Optional[str] = None,
    accepted_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    now_ts = _now()
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        updates = ["status = ?", "updated_at = ?"]
        params: list[Any] = [status, now_ts]
        if progress_pct is not None:
            updates.append("progress_pct = ?")
            params.append(progress_pct)
        if result_notes is not None:
            updates.append("result_notes = ?")
            params.append(result_notes)
        if acceptance_source is not None:
            updates.append("acceptance_source = ?")
            params.append(acceptance_source)
        if accepted_at is not None:
            updates.append("accepted_at = ?")
            params.append(accepted_at)
        elif status in ("ACCEPTED", "IN_PROGRESS"):
            updates.append("accepted_at = COALESCE(accepted_at, ?)")
            params.append(now_ts)
        params.append(assignment_id)

        cur = conn.execute(
            f"UPDATE job_assignments SET {', '.join(updates)} WHERE assignment_id = ?",
            params,
        )
        if cur.rowcount > 0:
            # Sync parent job status if completed or failed
            row = conn.execute("SELECT job_id FROM job_assignments WHERE assignment_id = ?", (assignment_id,)).fetchone()
            if row and row["job_id"]:
                job_id = row["job_id"]
                if status == "COMPLETED":
                    conn.execute("UPDATE commander_jobs SET status = 'COMPLETED', updated_at = ? WHERE job_id = ?", (now_ts, job_id))
                elif status == "IN_PROGRESS":
                    conn.execute("UPDATE commander_jobs SET status = 'IN_PROGRESS', updated_at = ? WHERE job_id = ? AND status != 'COMPLETED'", (now_ts, job_id))
            return True
        return False




def log_network_alert(
    session_id: str,
    alert_record: dict,
    db_path: Optional[str] = None,
) -> None:
    """Log one simulated GSM/LoRa alert attempt (see alert_dispatch.py).

    `alert_record` is the dict produced by AlertRecord.to_dict().
    """
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO network_alerts
                (alert_id, session_id, victim_id, channel, triage_class,
                 sps, status, attempts, latency_ms, battery_pct_at_send,
                 reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_record["alert_id"],
                session_id,
                alert_record["victim_id"],
                alert_record["channel"],
                alert_record["triage_class"],
                alert_record["sps"],
                alert_record["status"],
                alert_record["attempts"],
                alert_record["latency_ms"],
                alert_record["battery_pct_at_send"],
                alert_record["reason"],
                alert_record["timestamp"],
            ),
        )


def log_sensor_health_batch(
    session_id: str,
    cycle: int,
    health_list: list,
    db_path: Optional[str] = None,
) -> None:
    """Log a batch of SensorHealth records for the current cycle."""
    if not health_list:
        return
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO sensor_health_records
                (session_id, cycle, sensor_id, sensor_type, status,
                 battery_pct, signal_quality, error_message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    session_id,
                    cycle,
                    h.sensor_id if hasattr(h, "sensor_id") else h.get("sensor_id", ""),
                    h.sensor_type.value if hasattr(h, "sensor_type") and hasattr(h.sensor_type, "value") else str(h.get("sensor_type", "")),
                    h.status.value if hasattr(h, "status") and hasattr(h.status, "value") else str(h.get("status", "ONLINE")),
                    getattr(h, "battery_pct", h.get("battery_pct", 100.0) if isinstance(h, dict) else 100.0),
                    getattr(h, "signal_quality", h.get("signal_quality", 1.0) if isinstance(h, dict) else 1.0),
                    getattr(h, "error_message", h.get("error_message") if isinstance(h, dict) else None),
                    getattr(h, "last_heartbeat", h.get("timestamp", _now()) if isinstance(h, dict) else _now()),
                )
                for h in health_list
            ],
        )


def log_sensor_trends_batch(
    session_id: str,
    cycle: int,
    trend_list: list,
    db_path: Optional[str] = None,
) -> None:
    """Log a batch of SensorTrend records for the current cycle."""
    if not trend_list:
        return
    now_ts = _now()
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO sensor_trends
                (session_id, cycle, sensor_type, current_value, rate_of_change,
                 trend_direction, is_spike, is_sustained_abnormal, anomaly_score, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    session_id,
                    cycle,
                    t.sensor_type.value if hasattr(t, "sensor_type") and hasattr(t.sensor_type, "value") else str(t.get("sensor_type", "")),
                    getattr(t, "current_value", t.get("current_value", 0.0) if isinstance(t, dict) else 0.0),
                    getattr(t, "rate_of_change_per_cycle", t.get("rate_of_change", 0.0) if isinstance(t, dict) else 0.0),
                    getattr(t, "trend_direction", t.get("trend_direction", "STABLE") if isinstance(t, dict) else "STABLE"),
                    int(bool(getattr(t, "is_spike", t.get("is_spike", False) if isinstance(t, dict) else False))),
                    int(bool(getattr(t, "is_sustained_abnormal", t.get("is_sustained_abnormal", False) if isinstance(t, dict) else False))),
                    getattr(t, "anomaly_score", t.get("anomaly_score", 0.0) if isinstance(t, dict) else 0.0),
                    now_ts,
                )
                for t in trend_list
            ],
        )


def log_scenario_intelligence(
    session_id: str,
    cycle: int,
    assessment_dict: dict,
    db_path: Optional[str] = None,
) -> None:
    """Log the fused disaster assessment from the Scenario Intelligence Engine."""
    import json
    now_ts = _now()
    primary = assessment_dict.get("primary_scenario") or {}
    sec_list = assessment_dict.get("secondary_scenarios") or []
    evidence = assessment_dict.get("active_evidence") or []
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO scenario_intelligence_ledger
                (session_id, cycle, primary_scenario_id, primary_scenario_name,
                 confidence_pct, risk_level, survivor_status, evidence_json,
                 secondary_scenarios_json, recommended_action, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                cycle,
                primary.get("scenario_id", "unknown"),
                primary.get("scenario_name", "Unknown Scenario"),
                assessment_dict.get("confidence_pct", primary.get("confidence_pct", 0.0)),
                assessment_dict.get("overall_risk", primary.get("risk_level", "MEDIUM")),
                assessment_dict.get("survivor_status", "SEARCHING"),
                json.dumps(evidence),
                json.dumps(sec_list),
                primary.get("recommended_action", "Monitor and deploy response teams."),
                now_ts,
            ),
        )


def get_latest_scenario_intelligence(session_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    import json
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM scenario_intelligence_ledger WHERE session_id = ? ORDER BY cycle DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["evidence"] = json.loads(d.get("evidence_json") or "[]")
        except Exception:
            d["evidence"] = []
        try:
            d["secondary_scenarios"] = json.loads(d.get("secondary_scenarios_json") or "[]")
        except Exception:
            d["secondary_scenarios"] = []
        return d


def upsert_active_alert(
    alert_key: str,
    session_id: str,
    hazard_type: str,
    alert_title: str,
    severity: str,
    confidence_pct: float,
    evidence_summary: str,
    db_path: Optional[str] = None,
) -> None:
    now_ts = _now()
    with _connect(db_path) as conn:
        existing = conn.execute("SELECT first_detected_at FROM active_alerts_ledger WHERE alert_key = ?", (alert_key,)).fetchone()
        first_detected = existing["first_detected_at"] if existing else now_ts
        conn.execute(
            """
            INSERT OR REPLACE INTO active_alerts_ledger
                (alert_key, session_id, hazard_type, alert_title, severity,
                 confidence_pct, evidence_summary, status, first_detected_at,
                 last_updated_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, NULL)
            """,
            (
                alert_key, session_id, hazard_type, alert_title, severity,
                confidence_pct, evidence_summary, first_detected, now_ts,
            ),
        )


def list_active_alerts(session_id: Optional[str] = None, status: str = "ACTIVE", db_path: Optional[str] = None) -> list[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM active_alerts_ledger WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY last_updated_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def resolve_active_alert(alert_key: str, db_path: Optional[str] = None) -> bool:
    now_ts = _now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE active_alerts_ledger SET status = 'RESOLVED', resolved_at = ? WHERE alert_key = ?",
            (now_ts, alert_key),
        )
        return cur.rowcount > 0


def normalize_phone_number(phone_raw: Optional[str]) -> str:
    """Normalizes phone number to international E.164-like standard (+918098897666)."""
    if not phone_raw:
        return ""
    digits = re.sub(r"\D", "", phone_raw)
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    elif len(digits) == 10:
        return f"+91{digits}"
    elif digits:
        return f"+{digits}" if not phone_raw.startswith("+") else phone_raw
    return phone_raw


def mask_phone_number(normalized: str) -> str:
    """Masks phone number (e.g. +91 80988****66) so full number is never unnecessarily exposed in UI."""
    if not normalized:
        return "Unknown"
    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 12 and digits.startswith("91"):
        country = "+91"
        national = digits[2:]
        return f"{country} {national[:5]}****{national[-2:]}"
    elif len(digits) == 10:
        return f"+91 {digits[:5]}****{digits[-2:]}"
    elif len(normalized) > 7:
        return f"{normalized[:5]}****{normalized[-2:]}"
    return normalized


def resolve_member_contact_info(member_id: str, team_id: Optional[str] = None, db_path: Optional[str] = None) -> dict:
    """
    Resolves personnel phone number and details from persistent database registry.
    When Commander selects Alpha Team -> Alpha Member 1, resolves Mobile: 8098897666,
    Normalized: +918098897666, Masked: +91 80988****66.
    """
    with _connect(db_path) as conn:
        _ensure_admin_registry_tables(conn)
        row = conn.execute("SELECT * FROM personnel WHERE person_id = ? LIMIT 1", (member_id,)).fetchone()
        
        if not row and team_id:
            tm_row = conn.execute(
                "SELECT person_id FROM admin_team_members WHERE team_ref_id = ? AND person_id = ? LIMIT 1",
                (team_id, member_id),
            ).fetchone()
            if tm_row:
                row = conn.execute("SELECT * FROM personnel WHERE person_id = ? LIMIT 1", (tm_row["person_id"],)).fetchone()

        if not row:
            clean_m = (member_id or "").upper().replace("-", "").replace("_", "").replace(" ", "")
            if "ALPHA" in clean_m and ("1" in clean_m or "M001" in clean_m or "LEADER" in clean_m):
                row = conn.execute(
                    "SELECT * FROM personnel WHERE person_id = 'P-ALPHA-01' OR full_name LIKE '%Alpha Member 1%' LIMIT 1"
                ).fetchone()
            elif "ALPHA" in clean_m and ("2" in clean_m or "M002" in clean_m):
                row = conn.execute(
                    "SELECT * FROM personnel WHERE person_id = 'P-ALPHA-02' OR full_name LIKE '%Alpha Member 2%' LIMIT 1"
                ).fetchone()
            elif "BRAVO" in clean_m and ("1" in clean_m or "M001" in clean_m):
                row = conn.execute(
                    "SELECT * FROM personnel WHERE person_id = 'P-BRAVO-01' OR full_name LIKE '%Bravo Member 1%' LIMIT 1"
                ).fetchone()
            elif "BRAVO" in clean_m and ("2" in clean_m or "M002" in clean_m):
                row = conn.execute(
                    "SELECT * FROM personnel WHERE person_id = 'P-BRAVO-02' OR full_name LIKE '%Bravo Member 2%' LIMIT 1"
                ).fetchone()

        if not row:
            row = conn.execute(
                "SELECT * FROM personnel WHERE full_name LIKE ? OR person_id LIKE ? LIMIT 1",
                (f"%{member_id}%", f"%{member_id}%")
            ).fetchone()

        raw_phone = row["phone"] if (row and row["phone"]) else ("+91-80988-97666" if "ALPHA" in (member_id or "").upper() else "+91-98765-01001")
        normalized = normalize_phone_number(raw_phone)
        masked = mask_phone_number(normalized)
        member_name = row["full_name"] if (row and row["full_name"]) else ("Alpha Member 1" if "ALPHA" in (member_id or "").upper() else member_id)

        return {
            "member_id": member_id,
            "personnel_id": row["person_id"] if row else None,
            "full_name": member_name,
            "role": row["role"] if row else "Rescuer",
            "phone_raw": raw_phone,
            "phone_normalized": normalized,
            "phone_masked": masked,
        }


def upsert_notification(
    notif: dict,
    db_path: Optional[str] = None,
) -> dict:
    """Upserts an alert into the notification_center history table with multi-channel attributes."""
    now_ts = _now()
    notif_id = notif.get("id") or f"NOTIF-{uuid.uuid4().hex[:6].upper()}"
    alert_id = notif.get("alert_id") or notif_id
    rescue_command_id = notif.get("rescue_command_id") or notif.get("command_id") or alert_id.replace("ALT-", "")
    mission_id = notif.get("mission_id") or f"MSN-{rescue_command_id}"
    notif_type = notif.get("type", "EMERGENCY")
    title = notif.get("title", "Emergency Alert")
    message = notif.get("message", "Survivor detected")
    distance_m = notif.get("distance_m")
    distance_label = notif.get("distance_label") or (f"{int(distance_m)} m" if distance_m is not None else "Distance unavailable")
    priority = notif.get("priority", "HIGH")
    status = notif.get("status", "ACTIVE")
    watch_delivery_status = notif.get("watch_delivery_status", "PENDING")
    watch_ack_status = notif.get("watch_ack_status", "PENDING")
    team_id = notif.get("team_id", "ALPHA")
    member_id = notif.get("member_id", "ALPHA-M001")
    victim_id = notif.get("victim_id", "Survivor")
    created_ts = notif.get("timestamp") or now_ts

    phone_number = notif.get("phone_number")
    phone_number_masked = notif.get("phone_number_masked")
    if not phone_number:
        contact = resolve_member_contact_info(member_id, team_id=team_id, db_path=db_path)
        phone_number = contact["phone_normalized"]
        phone_number_masked = contact["phone_masked"]
    elif not phone_number_masked:
        phone_number_masked = mask_phone_number(normalize_phone_number(phone_number))

    sms_status = notif.get("sms_status", "QUEUED")
    sms_error = notif.get("sms_error")
    sps = float(notif.get("sps") or 0.0)
    latitude = float(notif.get("latitude") or 0.0)
    longitude = float(notif.get("longitude") or 0.0)
    required_action = notif.get("required_action") or notif.get("command_text") or message

    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO notification_center
                (id, alert_id, type, title, message, distance_m, distance_label,
                 priority, status, watch_delivery_status, watch_ack_status,
                 team_id, member_id, victim_id, timestamp, last_updated_at,
                 rescue_command_id, mission_id, phone_number, phone_number_masked,
                 sms_status, sms_error,
                 sps, latitude, longitude, required_action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notif_id, alert_id, notif_type, title, message, distance_m, distance_label,
                priority, status, watch_delivery_status, watch_ack_status,
                team_id, member_id, victim_id, created_ts, now_ts,
                rescue_command_id, mission_id, phone_number, phone_number_masked,
                sms_status, sms_error,
                sps, latitude, longitude, required_action,
            ),
        )
    return {
        "id": notif_id,
        "alert_id": alert_id,
        "rescue_command_id": rescue_command_id,
        "mission_id": mission_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "distance_m": distance_m,
        "distance_label": distance_label,
        "priority": priority,
        "status": status,
        "watch_delivery_status": watch_delivery_status,
        "watch_ack_status": watch_ack_status,
        "team_id": team_id,
        "member_id": member_id,
        "victim_id": victim_id,
        "phone_number": phone_number,
        "phone_number_masked": phone_number_masked,
        "sms_status": sms_status,
        "sms_error": sms_error,
        "sps": sps,
        "latitude": latitude,
        "longitude": longitude,
        "required_action": required_action,
        "timestamp": created_ts,
        "last_updated_at": now_ts,
    }


def list_notifications(
    team_id: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> list[dict]:
    """
    Retrieves notifications derived directly from the authoritative rescue_commands table
    (the exact same single source of truth that feeds the Bridge page), supplemented by
    any additional emergency/sensor alerts, ordered by newest first.
    """
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        results = []
        seen_cmd_ids = set()

        # 1. Primary Source: Authoritative rescue_commands (Same flow as Commander & Bridge)
        cmd_query = "SELECT * FROM rescue_commands WHERE 1=1"
        cmd_params: list[Any] = []
        if team_id:
            cmd_query += " AND (team_id = ? OR team_id IS NULL OR team_id = '')"
            cmd_params.append(team_id)
        cmd_query += " ORDER BY created_at DESC LIMIT ?"
        cmd_params.append(limit)
        cmd_rows = conn.execute(cmd_query, cmd_params).fetchall()

        for r in cmd_rows:
            d = dict(r)
            cmd_id = d["command_id"]
            seen_cmd_ids.add(cmd_id)
            seen_cmd_ids.add(f"CMD-{cmd_id}")
            seen_cmd_ids.add(f"ALT-{cmd_id}")
            seen_cmd_ids.add(f"NOTIF-{cmd_id}")
            seen_cmd_ids.add(f"NOTIF-ALT-{cmd_id}")

            raw_p = d.get("phone_number")
            masked_p = d.get("phone_number_masked")
            if not masked_p:
                if not raw_p:
                    c = resolve_member_contact_info(d.get("member_id", "ALPHA-M001"), team_id=d.get("team_id"), db_path=db_path)
                    raw_p = c["phone_normalized"]
                    masked_p = c["phone_masked"]
                else:
                    masked_p = mask_phone_number(normalize_phone_number(raw_p))

            sms_st = d.get("sms_status") or "SENT"
            watch_st = d.get("watch_delivery_status") or d.get("status") or "PENDING"
            watch_ack = "ACCEPTED" if d.get("acknowledged_at") else "PENDING"

            notif_item = {
                "id": f"NOTIF-{cmd_id}",
                "alert_id": f"ALT-{cmd_id}",
                "rescue_command_id": cmd_id,
                "mission_id": d.get("mission_id") or f"MSN-{cmd_id}",
                "type": "RESCUE_COMMAND",
                "title": f"🚨 RESCUE MISSION: {d.get('destination_label') or d.get('victim_id') or 'Survivor'}",
                "message": d.get("command_text") or f"Proceed to rescue {d.get('destination_label') or d.get('victim_id')}",
                "distance_m": 62.0,
                "distance_label": "62 m",
                "priority": d.get("priority", "HIGH"),
                "status": d.get("status", "ASSIGNED"),
                "watch_delivery_status": watch_st,
                "watch_ack_status": watch_ack,
                "team_id": d.get("team_id", "ALPHA"),
                "member_id": d.get("member_id", "ALPHA-M001"),
                "victim_id": d.get("victim_id", "Survivor"),
                "phone_number": raw_p,
                "phone_number_masked": masked_p,
                "sms_status": sms_st,
                "sms_error": d.get("sms_error"),
                "sms_provider": d.get("sms_provider") or os.getenv("SMS_PROVIDER", "SMSGATE").upper().strip(),
                "sps": 88.5,
                "latitude": d.get("destination_latitude") or d.get("latitude") or 0.0,
                "longitude": d.get("destination_longitude") or d.get("longitude") or 0.0,
                "required_action": d.get("command_text") or f"Proceed to rescue {d.get('destination_label') or d.get('victim_id')}",
                "timestamp": d.get("created_at") or _now(),
                "last_updated_at": d.get("created_at") or _now(),
            }
            results.append(notif_item)

        # 2. Secondary Source: Any distinct notification_center alerts (sensor/incident alerts)
        nc_query = "SELECT * FROM notification_center WHERE 1=1"
        nc_params: list[Any] = []
        if team_id:
            nc_query += " AND (team_id = ? OR team_id IS NULL OR team_id = '')"
            nc_params.append(team_id)
        nc_query += " ORDER BY timestamp DESC LIMIT ?"
        nc_params.append(limit)
        nc_rows = conn.execute(nc_query, nc_params).fetchall()

        for r in nc_rows:
            d = dict(r)
            rc_id = d.get("rescue_command_id") or ""
            alt_id = d.get("alert_id") or ""
            nid = d.get("id") or ""
            if rc_id in seen_cmd_ids or alt_id in seen_cmd_ids or nid in seen_cmd_ids:
                continue

            if not d.get("phone_number_masked"):
                raw_p = d.get("phone_number")
                if not raw_p:
                    c = resolve_member_contact_info(d.get("member_id", "ALPHA-M001"), team_id=d.get("team_id"), db_path=db_path)
                    d["phone_number_masked"] = c["phone_masked"]
                    d["phone_number"] = c["phone_normalized"]
                else:
                    d["phone_number_masked"] = mask_phone_number(normalize_phone_number(raw_p))
            if not d.get("sms_status"):
                d["sms_status"] = "QUEUED"
            d["sms_provider"] = d.get("sms_provider") or os.getenv("SMS_PROVIDER", "SMSGATE").upper().strip()
            results.append(d)

        results.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return results[:limit]


def get_notification(
    notif_id_or_alert_id: str,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Finds a notification by ID, alert_id, or rescue_command_id from rescue_commands or notification_center."""
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        clean_cmd_id = notif_id_or_alert_id.replace("NOTIF-ALT-", "").replace("NOTIF-", "").replace("ALT-", "")

        # Check rescue_commands first (authoritative source)
        row = conn.execute(
            "SELECT * FROM rescue_commands WHERE command_id = ? OR command_id = ? LIMIT 1",
            (notif_id_or_alert_id, clean_cmd_id),
        ).fetchone()
        if row:
            d = dict(row)
            cmd_id = d["command_id"]
            raw_p = d.get("phone_number")
            masked_p = d.get("phone_number_masked")
            if not masked_p:
                if not raw_p:
                    c = resolve_member_contact_info(d.get("member_id", "ALPHA-M001"), team_id=d.get("team_id"), db_path=db_path)
                    raw_p = c["phone_normalized"]
                    masked_p = c["phone_masked"]
                else:
                    masked_p = mask_phone_number(normalize_phone_number(raw_p))
            return {
                "id": f"NOTIF-{cmd_id}",
                "alert_id": f"ALT-{cmd_id}",
                "rescue_command_id": cmd_id,
                "mission_id": d.get("mission_id") or f"MSN-{cmd_id}",
                "type": "RESCUE_COMMAND",
                "title": f"🚨 RESCUE MISSION: {d.get('destination_label') or d.get('victim_id') or 'Survivor'}",
                "message": d.get("command_text") or f"Proceed to rescue {d.get('destination_label') or d.get('victim_id')}",
                "distance_m": 62.0,
                "distance_label": "62 m",
                "priority": d.get("priority", "HIGH"),
                "status": d.get("status", "ASSIGNED"),
                "watch_delivery_status": d.get("watch_delivery_status") or d.get("status") or "PENDING",
                "watch_ack_status": "ACCEPTED" if d.get("acknowledged_at") else "PENDING",
                "team_id": d.get("team_id", "ALPHA"),
                "member_id": d.get("member_id", "ALPHA-M001"),
                "victim_id": d.get("victim_id", "Survivor"),
                "phone_number": raw_p,
                "phone_number_masked": masked_p,
                "sms_status": d.get("sms_status") or "SENT",
                "sms_error": d.get("sms_error"),
                "sms_provider": d.get("sms_provider") or os.getenv("SMS_PROVIDER", "SMSGATE").upper().strip(),
                "sps": 88.5,
                "latitude": d.get("destination_latitude") or d.get("latitude") or 0.0,
                "longitude": d.get("destination_longitude") or d.get("longitude") or 0.0,
                "required_action": d.get("command_text") or f"Proceed to rescue {d.get('destination_label') or d.get('victim_id')}",
                "timestamp": d.get("created_at") or _now(),
                "last_updated_at": d.get("created_at") or _now(),
            }

        # Fallback to notification_center table
        row = conn.execute(
            "SELECT * FROM notification_center WHERE id = ? OR alert_id = ? OR rescue_command_id = ? LIMIT 1",
            (notif_id_or_alert_id, notif_id_or_alert_id, notif_id_or_alert_id),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if not d.get("phone_number_masked"):
            c = resolve_member_contact_info(d.get("member_id", "ALPHA-M001"), team_id=d.get("team_id"), db_path=db_path)
            d["phone_number_masked"] = c["phone_masked"]
            d["phone_number"] = c["phone_normalized"]
        d["sms_provider"] = d.get("sms_provider") or os.getenv("SMS_PROVIDER", "SMSGATE").upper().strip()
        return d


def update_notification_status(
    notif_id_or_alert_id: str,
    watch_delivery_status: Optional[str] = None,
    watch_ack_status: Optional[str] = None,
    status: Optional[str] = None,
    sms_status: Optional[str] = None,
    sms_error: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """Updates channel, delivery, and ACK status for an existing notification."""
    now_ts = _now()
    updates = ["last_updated_at = ?"]
    params: list[Any] = [now_ts]
    if watch_delivery_status:
        updates.append("watch_delivery_status = ?")
        params.append(watch_delivery_status)
    if watch_ack_status:
        updates.append("watch_ack_status = ?")
        params.append(watch_ack_status)
    if status:
        updates.append("status = ?")
        params.append(status)
    if sms_status:
        updates.append("sms_status = ?")
        params.append(sms_status)
    if sms_error is not None:
        updates.append("sms_error = ?")
        params.append(sms_error)
    params.extend([notif_id_or_alert_id, notif_id_or_alert_id, notif_id_or_alert_id])

    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        cur = conn.execute(
            f"UPDATE notification_center SET {', '.join(updates)} WHERE id = ? OR alert_id = ? OR rescue_command_id = ?",
            params,
        )
        return cur.rowcount > 0



def get_sensor_history(session_id: str, victim_id: Optional[str] = None, sensor_type: Optional[str] = None, limit: int = 100, db_path: Optional[str] = None) -> list[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM sensor_readings WHERE session_id = ?"
        params: list[Any] = [session_id]
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        if sensor_type:
            query += " AND sensor_type = ?"
            params.append(sensor_type)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def log_gas_smoke_reading(
    reading: Any,
    session_id: str,
    db_path: Optional[str] = None,
) -> None:
    """Log a validated GasSmokeReading object or dict to gas_smoke_readings."""
    if hasattr(reading, "to_dict"):
        d = reading.to_dict()
    elif isinstance(reading, dict):
        d = reading
    else:
        return

    lat = d.get("location", {}).get("latitude") if isinstance(d.get("location"), dict) else None
    lon = d.get("location", {}).get("longitude") if isinstance(d.get("location"), dict) else None
    now_ts = d.get("timestamp") or _now()

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO gas_smoke_readings
                (reading_id, session_id, sensor_id, device_id, gas_type,
                 gas_concentration, gas_unit, gas_level, smoke_density_pct,
                 smoke_level, rate_of_change_gas, rate_of_change_smoke,
                 latitude, longitude, status, confidence, quality,
                 raw_data_json, metadata_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.get("reading_id") or f"GSR-{uuid.uuid4().hex[:8]}",
                session_id,
                d.get("sensor_id", "GAS-SMOKE-SITE"),
                d.get("device_id", "DEV-GAS-01"),
                d.get("gas_type", "GENERIC_SMOKE"),
                _safe_float(d.get("gas_concentration"), 0.0),
                d.get("gas_unit", "ppm"),
                d.get("gas_level", "NORMAL"),
                _safe_float(d.get("smoke_density_pct"), 0.0),
                d.get("smoke_level", "NO_SMOKE"),
                _safe_float(d.get("rate_of_change_gas"), 0.0),
                _safe_float(d.get("rate_of_change_smoke"), 0.0),
                lat,
                lon,
                d.get("status", "ONLINE"),
                _safe_float(d.get("confidence"), 0.95),
                _safe_float(d.get("quality"), 0.95),
                json.dumps(d.get("raw_data", {})),
                json.dumps(d.get("metadata", {})),
                now_ts,
            ),
        )


def log_gas_smoke_readings_batch(
    readings: Iterable[Any],
    session_id: str,
    db_path: Optional[str] = None,
) -> None:
    """Log a batch of GasSmokeReading objects or dicts."""
    rows = []
    for reading in readings:
        if hasattr(reading, "to_dict"):
            d = reading.to_dict()
        elif isinstance(reading, dict):
            d = reading
        else:
            continue
        lat = d.get("location", {}).get("latitude") if isinstance(d.get("location"), dict) else None
        lon = d.get("location", {}).get("longitude") if isinstance(d.get("location"), dict) else None
        rows.append((
            d.get("reading_id") or f"GSR-{uuid.uuid4().hex[:8]}",
            session_id,
            d.get("sensor_id", "GAS-SMOKE-SITE"),
            d.get("device_id", "DEV-GAS-01"),
            d.get("gas_type", "GENERIC_SMOKE"),
            _safe_float(d.get("gas_concentration"), 0.0),
            d.get("gas_unit", "ppm"),
            d.get("gas_level", "NORMAL"),
            _safe_float(d.get("smoke_density_pct"), 0.0),
            d.get("smoke_level", "NO_SMOKE"),
            _safe_float(d.get("rate_of_change_gas"), 0.0),
            _safe_float(d.get("rate_of_change_smoke"), 0.0),
            lat,
            lon,
            d.get("status", "ONLINE"),
            _safe_float(d.get("confidence"), 0.95),
            _safe_float(d.get("quality"), 0.95),
            json.dumps(d.get("raw_data", {})),
            json.dumps(d.get("metadata", {})),
            d.get("timestamp") or _now(),
        ))
    if not rows:
        return
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO gas_smoke_readings
                (reading_id, session_id, sensor_id, device_id, gas_type,
                 gas_concentration, gas_unit, gas_level, smoke_density_pct,
                 smoke_level, rate_of_change_gas, rate_of_change_smoke,
                 latitude, longitude, status, confidence, quality,
                 raw_data_json, metadata_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def get_gas_smoke_history(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Fetch historical gas/smoke time series ordered chronologically."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM gas_smoke_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        result = [dict(r) for r in rows]
        # Return in ascending chronological order for charts
        result.reverse()
        return result


def get_latest_gas_smoke_reading(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Fetch the latest gas/smoke reading."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM gas_smoke_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY id DESC LIMIT 1"
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


# --------------------------------------------------------------------------- #
# Writes & Reads - Barometric Pressure Telemetry
# --------------------------------------------------------------------------- #

def log_barometric_reading(
    reading: Any,
    session_id: str,
    db_path: Optional[str] = None,
) -> None:
    """Log a validated BarometricPressureReading object or dict to barometric_readings."""
    if hasattr(reading, "to_dict"):
        d = reading.to_dict()
    elif isinstance(reading, dict):
        d = reading
    else:
        return

    loc = d.get("location")
    lat, lon = None, None
    if isinstance(loc, dict):
        lat = loc.get("latitude")
        lon = loc.get("longitude")
    elif isinstance(loc, (tuple, list)) and len(loc) >= 2:
        lat, lon = loc[0], loc[1]

    now_ts = d.get("timestamp") or _now()

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO barometric_readings
                (reading_id, session_id, sensor_id, device_id, pressure_hpa,
                 unit, rate_of_change, trend, drop_severity, anomaly_level,
                 latitude, longitude, status, confidence, quality,
                 raw_data_json, metadata_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.get("reading_id") or f"BPR-{uuid.uuid4().hex[:8]}",
                session_id,
                d.get("sensor_id", "ENV-BARO-01"),
                d.get("device_id", "DEV-BARO-01"),
                _safe_float(d.get("pressure_hpa"), 1013.25),
                d.get("unit", "hPa"),
                _safe_float(d.get("rate_of_change"), 0.0),
                d.get("trend", "STABLE"),
                d.get("drop_severity", "NORMAL"),
                d.get("anomaly_level", "NORMAL"),
                lat,
                lon,
                d.get("status", "ONLINE"),
                _safe_float(d.get("confidence"), 0.95),
                _safe_float(d.get("quality"), 0.95),
                json.dumps(d.get("raw_data", {})),
                json.dumps(d.get("metadata", {})),
                now_ts,
            ),
        )


def log_barometric_readings_batch(
    readings: Iterable[Any],
    session_id: str,
    db_path: Optional[str] = None,
) -> None:
    """Log a batch of BarometricPressureReading objects or dicts."""
    rows = []
    for reading in readings:
        if hasattr(reading, "to_dict"):
            d = reading.to_dict()
        elif isinstance(reading, dict):
            d = reading
        else:
            continue

        loc = d.get("location")
        lat, lon = None, None
        if isinstance(loc, dict):
            lat = loc.get("latitude")
            lon = loc.get("longitude")
        elif isinstance(loc, (tuple, list)) and len(loc) >= 2:
            lat, lon = loc[0], loc[1]

        rows.append((
            d.get("reading_id") or f"BPR-{uuid.uuid4().hex[:8]}",
            session_id,
            d.get("sensor_id", "ENV-BARO-01"),
            d.get("device_id", "DEV-BARO-01"),
            _safe_float(d.get("pressure_hpa"), 1013.25),
            d.get("unit", "hPa"),
            _safe_float(d.get("rate_of_change"), 0.0),
            d.get("trend", "STABLE"),
            d.get("drop_severity", "NORMAL"),
            d.get("anomaly_level", "NORMAL"),
            lat,
            lon,
            d.get("status", "ONLINE"),
            _safe_float(d.get("confidence"), 0.95),
            _safe_float(d.get("quality"), 0.95),
            json.dumps(d.get("raw_data", {})),
            json.dumps(d.get("metadata", {})),
            d.get("timestamp") or _now(),
        ))
    if not rows:
        return
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO barometric_readings
                (reading_id, session_id, sensor_id, device_id, pressure_hpa,
                 unit, rate_of_change, trend, drop_severity, anomaly_level,
                 latitude, longitude, status, confidence, quality,
                 raw_data_json, metadata_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def get_barometric_history(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Fetch historical barometric pressure time series ordered chronologically."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM barometric_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        result = [dict(r) for r in rows]
        # Return in ascending chronological order for charts
        result.reverse()
        return result


def get_latest_barometric_reading(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Fetch the latest barometric pressure reading."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM barometric_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT 1"
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #

def list_sessions(db_path: Optional[str] = None) -> list:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def session_counts(session_id: str, db_path: Optional[str] = None) -> dict:
    """Row counts per table for a session - handy for a quick sanity check."""
    with _connect(db_path) as conn:
        counts = {}
        for table in ("sensor_readings", "detection_results", "rescue_status_events", "network_alerts"):
            n = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE session_id = ?", (session_id,)
            ).fetchone()["n"]
            counts[table] = n
        return counts


def count_rescued_events(session_id: str, db_path: Optional[str] = None) -> int:
    """Rescue completions logged for a session - either subsystem (Step 33 analytics)."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM rescue_status_events "
            "WHERE session_id = ? AND event_type IN ('member_arrived', 'victim_reached')",
            (session_id,),
        ).fetchone()
        return row["n"]


def list_rescue_status_events(session_id: str, db_path: Optional[str] = None) -> list:
    """List all rescue status events for a session, ordered chronologically."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM rescue_status_events WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# CSV column order for the unified export. `record_type` disambiguates
# which table a row came from; irrelevant columns for that record type are
# left blank.
_EXPORT_FIELDS = [
    "record_type", "timestamp", "session_id", "cycle", "victim_id",
    # sensor_readings columns
    "sensor_type", "value", "unit", "sensor_confidence", "noisy",
    # detection_results columns
    "confidence_pct", "triage_class", "sps", "hazard_multiplier",
    "tapping_detected", "contributing_sensors",
    # rescue_status_events columns
    "event_type", "team_id", "availability", "eta_minutes",
    "arrival_order", "travel_seconds", "notes",
    # network_alerts columns
    "alert_id", "channel", "status", "attempts",
    "latency_ms", "battery_pct_at_send", "reason",
]


def _fetch_unified_rows(conn: sqlite3.Connection, session_id: str) -> list:
    rows = []

    for r in conn.execute(
        "SELECT * FROM sensor_readings WHERE session_id = ? ORDER BY id", (session_id,)
    ):
        rows.append({
            "record_type": "sensor_reading",
            "timestamp": r["timestamp"],
            "session_id": r["session_id"],
            "cycle": r["cycle"],
            "victim_id": r["victim_id"],
            "sensor_type": r["sensor_type"],
            "value": r["value"],
            "unit": r["unit"],
            "sensor_confidence": r["sensor_confidence"],
            "noisy": r["noisy"],
        })

    for r in conn.execute(
        "SELECT * FROM detection_results WHERE session_id = ? ORDER BY id", (session_id,)
    ):
        rows.append({
            "record_type": "detection_result",
            "timestamp": r["timestamp"],
            "session_id": r["session_id"],
            "cycle": r["cycle"],
            "victim_id": r["victim_id"],
            "confidence_pct": r["confidence_pct"],
            "triage_class": r["triage_class"],
            "sps": r["sps"],
            "hazard_multiplier": r["hazard_multiplier"],
            "tapping_detected": r["tapping_detected"],
            "contributing_sensors": r["contributing_sensors"],
        })

    for r in conn.execute(
        "SELECT * FROM rescue_status_events WHERE session_id = ? ORDER BY id", (session_id,)
    ):
        rows.append({
            "record_type": "rescue_status_event",
            "timestamp": r["timestamp"],
            "session_id": r["session_id"],
            "victim_id": r["victim_id"],
            "event_type": r["event_type"],
            "team_id": r["team_id"],
            "availability": r["availability"],
            "eta_minutes": r["eta_minutes"],
            "arrival_order": r["arrival_order"],
            "travel_seconds": r["travel_seconds"],
            "notes": r["notes"],
        })

    for r in conn.execute(
        "SELECT * FROM network_alerts WHERE session_id = ? ORDER BY rowid", (session_id,)
    ):
        rows.append({
            "record_type": "network_alert",
            "timestamp": r["timestamp"],
            "session_id": r["session_id"],
            "victim_id": r["victim_id"],
            "alert_id": r["alert_id"],
            "channel": r["channel"],
            "triage_class": r["triage_class"],
            "sps": r["sps"],
            "status": r["status"],
            "attempts": r["attempts"],
            "latency_ms": r["latency_ms"],
            "battery_pct_at_send": r["battery_pct_at_send"],
            "reason": r["reason"],
        })

    # Chronological order across all record types makes for a readable,
    # analysis-ready timeline (e.g. for a testing/evaluation chapter).
    rows.sort(key=lambda d: (d.get("timestamp") or "", d.get("record_type") or ""))
    return rows


# --------------------------------------------------------------------------- #
# Landslide Hazard & Soil Moisture / Tilt Persistence
# --------------------------------------------------------------------------- #

def log_landslide_reading(
    reading: Any,
    session_id: str = "default",
    db_path: Optional[str] = None,
) -> int:
    """Insert a single Landslide / Soil Moisture / Tilt reading."""
    import json
    import uuid
    from datetime import datetime, timezone
    with _connect(db_path) as conn:
        r_dict = reading.to_dict() if hasattr(reading, "to_dict") else dict(reading)
        rid = r_dict.get("reading_id") or f"LSR-{uuid.uuid4().hex[:8]}"
        nid = r_dict.get("node_id") or "SLOPE-NODE-01"
        sm_val = r_dict.get("soil_moisture_pct")
        sm = float(sm_val if sm_val is not None else 38.0)
        m_trend = str(r_dict.get("moisture_trend", "STABLE"))
        m_rate_val = r_dict.get("moisture_rate")
        if m_rate_val is None:
            m_rate_val = r_dict.get("rate_of_change")
        m_rate = float(m_rate_val if m_rate_val is not None else 0.0)
        tx = r_dict.get("tilt_x")
        ty = r_dict.get("tilt_y")
        tz = r_dict.get("tilt_z")
        t_ang_val = r_dict.get("tilt_angle_deg")
        t_ang = float(t_ang_val if t_ang_val is not None else 0.5)
        t_rate_val = r_dict.get("tilt_rate")
        t_rate = float(t_rate_val if t_rate_val is not None else 0.0)
        t_trend = str(r_dict.get("tilt_trend", "STABLE"))
        r_score_val = r_dict.get("landslide_risk_score")
        if r_score_val is None:
            r_score_val = r_dict.get("risk_score")
        r_score = float(r_score_val if r_score_val is not None else 10.0)
        r_level = str(r_dict.get("risk_level", "LOW"))
        conf_val = r_dict.get("confidence")
        conf = float(conf_val if conf_val is not None else 0.95)
        ev_state = str(r_dict.get("event_state", "NORMAL"))
        stat = str(r_dict.get("status", "ONLINE"))
        qual_val = r_dict.get("quality")
        qual = float(qual_val if qual_val is not None else 0.95)
        loc = r_dict.get("location")
        lat = loc[0] if isinstance(loc, (list, tuple)) and len(loc) >= 2 else (loc.get("latitude") if isinstance(loc, dict) else None)
        lng = loc[1] if isinstance(loc, (list, tuple)) and len(loc) >= 2 else (loc.get("longitude") if isinstance(loc, dict) else None)
        factors = json.dumps(r_dict.get("contributing_factors", []))
        raw_json = json.dumps(r_dict.get("raw_data", {}))
        meta_json = json.dumps(r_dict.get("metadata", {}))
        ts = r_dict.get("timestamp") or datetime.now(timezone.utc).isoformat()

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO landslide_readings (
                reading_id, session_id, node_id, soil_moisture_pct, moisture_trend,
                moisture_rate, tilt_x, tilt_y, tilt_z, tilt_angle_deg, tilt_rate,
                tilt_trend, risk_score, risk_level, confidence, event_state,
                status, quality, latitude, longitude, contributing_factors_json,
                raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, nid, sm, m_trend,
                m_rate, tx, ty, tz, t_ang, t_rate,
                t_trend, r_score, r_level, conf, ev_state,
                stat, qual, lat, lng, factors,
                raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def log_landslide_readings_batch(
    readings: List[Any],
    session_id: str = "default",
    db_path: Optional[str] = None,
) -> int:
    count = 0
    for r in readings:
        log_landslide_reading(r, session_id=session_id, db_path=db_path)
        count += 1
    return count


def get_latest_landslide_reading(
    session_id: Optional[str] = None,
    node_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    import json
    with _connect(db_path) as conn:
        query = "SELECT * FROM landslide_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("contributing_factors_json"):
            try:
                d["contributing_factors"] = json.loads(d["contributing_factors_json"])
            except Exception:
                d["contributing_factors"] = []
        return d


def get_landslide_history(
    session_id: Optional[str] = None,
    node_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    import json
    with _connect(db_path) as conn:
        query = "SELECT * FROM landslide_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        results = []
        for row in reversed(rows):
            d = dict(row)
            if d.get("contributing_factors_json"):
                try:
                    d["contributing_factors"] = json.loads(d["contributing_factors_json"])
                except Exception:
                    d["contributing_factors"] = []
            results.append(d)
        return results


def log_camera_reading(
    reading: Any,
    session_id: str = "default",
    db_path: Optional[str] = None,
) -> int:
    """Persist a single CameraReading to the camera_readings audit table."""
    import json
    if hasattr(reading, "to_dict"):
        d = reading.to_dict()
    elif isinstance(reading, dict):
        d = reading
    else:
        d = vars(reading)

    rid = d.get("reading_id") or f"CAMR-{uuid.uuid4().hex[:8]}"
    cid = d.get("camera_id", "CAM-001")
    dev_id = d.get("device_id", "DEV-CAM-01")
    vid = d.get("victim_id")
    det_state = d.get("detection_state", "NO_DETECTION")
    det_type = d.get("detection_type", "none")
    cls_type = d.get("classification", "UNKNOWN")
    cls_conf = float(d.get("classification_confidence", 0.0))
    p_cnt = int(d.get("person_count", 0))
    conf = float(d.get("confidence", 0.0))
    vis = float(d.get("visibility", 1.0))
    occ = float(d.get("occlusion", 0.0))
    img_q = float(d.get("image_quality", 1.0))
    mot = 1 if d.get("motion_detected") else 0
    smk = 1 if d.get("smoke_present") else 0
    fir = 1 if d.get("fire_visible") else 0
    deb = 1 if d.get("debris_present") else 0
    orient = d.get("orientation", "0° NADIR")
    fov = float(d.get("field_of_view_deg", 85.0))
    rng_m = float(d.get("range_m", 30.0))
    stat = d.get("status", "ONLINE")
    h_score = float(d.get("health_score", 100.0))
    
    loc = d.get("location")
    lat, lng = None, None
    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
        lat, lng = loc[0], loc[1]
    elif isinstance(loc, dict):
        lat, lng = loc.get("latitude"), loc.get("longitude")

    raw_json = json.dumps(d.get("raw_data", {}))
    meta_json = json.dumps(d.get("metadata", {}))
    ts = d.get("timestamp") or datetime.now(timezone.utc).isoformat()

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO camera_readings (
                reading_id, session_id, camera_id, device_id, victim_id,
                detection_state, detection_type, classification, classification_confidence,
                person_count, confidence, visibility, occlusion, image_quality,
                motion_detected, smoke_present, fire_visible, debris_present,
                orientation, field_of_view_deg, range_m, status, health_score,
                latitude, longitude, raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cid, dev_id, vid,
                det_state, det_type, cls_type, cls_conf,
                p_cnt, conf, vis, occ, img_q,
                mot, smk, fir, deb,
                orient, fov, rng_m, stat, h_score,
                lat, lng, raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def log_camera_readings_batch(
    readings: List[Any],
    session_id: str = "default",
    db_path: Optional[str] = None,
) -> int:
    count = 0
    for r in readings:
        log_camera_reading(r, session_id=session_id, db_path=db_path)
        count += 1
    return count


def get_latest_camera_reading(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM camera_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return dict(row)


def get_camera_history(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM camera_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def log_thermal_reading(
    reading: Any,
    session_id: str = "default",
    db_path: Optional[str] = None,
) -> int:
    """Persist a single ThermalCameraReading to the thermal_readings audit table."""
    import json
    if hasattr(reading, "to_dict"):
        d = reading.to_dict()
    elif isinstance(reading, dict):
        d = reading
    else:
        d = vars(reading)

    rid = d.get("reading_id") or f"THMR-{uuid.uuid4().hex[:8]}"
    cid = d.get("camera_id", "THERMAL-001")
    dev_id = d.get("device_id", "DEV-THM-01")
    vid = d.get("victim_id")
    det_type = d.get("detection_type", "NO_HEAT")
    cls_type = d.get("classification", "NO_SIGNATURE")
    cls_conf = float(d.get("classification_confidence", 0.0))
    heat_det = 1 if d.get("heat_signature_detected") else 0
    hum_sig = 1 if d.get("human_signature") else 0
    h_cnt = int(d.get("heat_signature_count", 0))
    t_conf = float(d.get("thermal_confidence", 0.0))
    est_temp = float(d.get("estimated_temperature", 20.0))
    bg_temp = float(d.get("background_temperature", 18.0))
    d_temp = float(d.get("temperature_delta", 2.0))
    t_vis = float(d.get("thermal_visibility", 1.0))
    t_cntr = float(d.get("thermal_contrast", 1.0))
    occ = float(d.get("occlusion", 0.0))
    fire_hs = 1 if d.get("fire_hotspot") else 0
    hot_deb = 1 if d.get("hot_debris") else 0
    orient = d.get("orientation", "0° NADIR")
    fov = float(d.get("field_of_view_deg", 60.0))
    rng_m = float(d.get("range_m", 40.0))
    stat = d.get("status", "ONLINE")
    h_score = float(d.get("health_score", 100.0))
    
    loc = d.get("location")
    lat, lng = None, None
    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
        lat, lng = loc[0], loc[1]
    elif isinstance(loc, dict):
        lat, lng = loc.get("latitude"), loc.get("longitude")

    raw_json = json.dumps(d.get("raw_data", {}))
    meta_json = json.dumps(d.get("metadata", {}))
    ts = d.get("timestamp") or datetime.now(timezone.utc).isoformat()

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO thermal_readings (
                reading_id, session_id, camera_id, device_id, victim_id,
                detection_type, classification, classification_confidence,
                heat_signature_detected, human_signature, heat_signature_count,
                thermal_confidence, estimated_temperature, background_temperature,
                temperature_delta, thermal_visibility, thermal_contrast, occlusion,
                fire_hotspot, hot_debris, orientation, field_of_view_deg, range_m,
                status, health_score, latitude, longitude, raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cid, dev_id, vid,
                det_type, cls_type, cls_conf,
                heat_det, hum_sig, h_cnt,
                t_conf, est_temp, bg_temp,
                d_temp, t_vis, t_cntr, occ,
                fire_hs, hot_deb, orient, fov, rng_m,
                stat, h_score, lat, lng, raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def log_thermal_readings_batch(
    readings: List[Any],
    session_id: str = "default",
    db_path: Optional[str] = None,
) -> int:
    count = 0
    for r in readings:
        log_thermal_reading(r, session_id=session_id, db_path=db_path)
        count += 1
    return count


def get_latest_thermal_reading(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM thermal_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return dict(row)


def get_thermal_history(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM thermal_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_camera_thermal_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Compute aggregate analytics for optical and thermal cameras from audit logs."""
    with _connect(db_path) as conn:
        cam_q = "SELECT * FROM camera_readings WHERE 1=1"
        thm_q = "SELECT * FROM thermal_readings WHERE 1=1"
        params = []
        if session_id:
            cam_q += " AND session_id = ?"
            thm_q += " AND session_id = ?"
            params.append(session_id)
        
        cam_rows = [dict(r) for r in conn.execute(cam_q, params).fetchall()]
        thm_rows = [dict(r) for r in conn.execute(thm_q, params).fetchall()]

        total_cam_readings = len(cam_rows)
        cam_person_detections = sum(1 for r in cam_rows if r.get("person_count", 0) > 0 or r.get("detection_state") in ("PERSON_DETECTED", "MULTIPLE_PERSONS", "PARTIAL_PERSON", "OCCLUDED_PERSON"))
        cam_smoke_detections = sum(1 for r in cam_rows if r.get("smoke_present") or r.get("detection_state") == "SMOKE")
        cam_fire_detections = sum(1 for r in cam_rows if r.get("fire_visible") or r.get("detection_state") == "FIRE")
        cam_online_count = sum(1 for r in cam_rows if r.get("status") == "ONLINE")
        cam_avg_confidence = (sum(r.get("confidence", 0.0) for r in cam_rows) / total_cam_readings) if total_cam_readings > 0 else 0.0
        cam_uptime_pct = round((cam_online_count / total_cam_readings * 100.0) if total_cam_readings > 0 else 100.0, 1)

        total_thm_readings = len(thm_rows)
        thm_human_signatures = sum(1 for r in thm_rows if r.get("human_signature") or r.get("detection_type") in ("HUMAN_HEAT_SIGNATURE", "STRONG_HUMAN_HEAT", "MULTIPLE_HUMAN_HEAT"))
        thm_fire_hotspots = sum(1 for r in thm_rows if r.get("fire_hotspot") or r.get("detection_type") == "FIRE_HOTSPOT")
        thm_hot_debris = sum(1 for r in thm_rows if r.get("hot_debris") or r.get("detection_type") == "HOT_DEBRIS")
        thm_online_count = sum(1 for r in thm_rows if r.get("status") == "ONLINE")
        thm_avg_confidence = (sum(r.get("thermal_confidence", 0.0) for r in thm_rows) / total_thm_readings) if total_thm_readings > 0 else 0.0
        thm_uptime_pct = round((thm_online_count / total_thm_readings * 100.0) if total_thm_readings > 0 else 100.0, 1)

        # Corroboration & false-positive stats
        multi_sensor_confirmations = min(cam_person_detections, thm_human_signatures)
        potential_false_positives = max(0, cam_person_detections - thm_human_signatures)

        return {
            "total_camera_readings": total_cam_readings,
            "camera_person_detections": cam_person_detections,
            "camera_smoke_detections": cam_smoke_detections,
            "camera_fire_detections": cam_fire_detections,
            "camera_avg_confidence": round(cam_avg_confidence, 2),
            "camera_uptime_pct": cam_uptime_pct,
            "total_thermal_readings": total_thm_readings,
            "thermal_human_signatures": thm_human_signatures,
            "thermal_fire_hotspots": thm_fire_hotspots,
            "thermal_hot_debris": thm_hot_debris,
            "thermal_avg_confidence": round(thm_avg_confidence, 2),
            "thermal_uptime_pct": thm_uptime_pct,
            "multi_sensor_confirmations": multi_sensor_confirmations,
            "potential_false_positives_mitigated": potential_false_positives,
        }


def log_rainfall_reading(
    reading: Any,
    session_id: str = "default",
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    d = reading.to_dict() if hasattr(reading, "to_dict") else (reading if isinstance(reading, dict) else {})
    rid = d.get("reading_id") or f"RNF-{uuid.uuid4().hex[:8]}"
    sid = d.get("sensor_id", "ENV-RAIN-01")
    dev_id = d.get("device_id", "DEV-RAIN-01")
    rate_val = d.get("rainfall_rate_mm_h")
    if rate_val is None:
        rate_val = d.get("rainfall_mm_hr")
    rate = float(rate_val if rate_val is not None else 0.0)
    cumul_val = d.get("cumulative_rainfall_mm")
    cumul = float(cumul_val if cumul_val is not None else 0.0)
    unit = d.get("unit", "mm/h")
    roc_val = d.get("rate_of_change")
    roc = float(roc_val if roc_val is not None else 0.0)
    trend = d.get("trend", "STABLE")
    cls_name = d.get("classification", "NO_RAIN")
    sev = d.get("severity", "LOW")
    stat = d.get("status", "ONLINE")
    conf_val = d.get("confidence")
    conf = float(conf_val if conf_val is not None else 0.98)
    qual_val = d.get("quality")
    qual = float(qual_val if qual_val is not None else 0.98)

    loc = d.get("location")
    lat, lng, alt = None, None, None
    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
        lat, lng = loc[0], loc[1]
        alt = loc[2] if len(loc) >= 3 else None
    elif isinstance(loc, dict):
        lat, lng, alt = loc.get("latitude"), loc.get("longitude"), loc.get("altitude_m")

    raw_json = json.dumps(d.get("raw_data", {}))
    meta_json = json.dumps(d.get("metadata", {}))
    ts = d.get("timestamp") or datetime.now(timezone.utc).isoformat()

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO rainfall_readings (
                reading_id, session_id, cycle, sensor_id, device_id,
                rainfall_rate_mm_h, cumulative_rainfall_mm, unit, rate_of_change,
                trend, classification, severity, status, confidence, quality,
                latitude, longitude, altitude_m, raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cycle, sid, dev_id,
                rate, cumul, unit, roc,
                trend, cls_name, sev, stat, conf, qual,
                lat, lng, alt, raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def log_rainfall_readings_batch(
    readings: List[Any],
    session_id: str = "default",
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    count = 0
    for r in readings:
        log_rainfall_reading(r, session_id=session_id, cycle=cycle, db_path=db_path)
        count += 1
    return count


def get_latest_rainfall_reading(
    session_id: Optional[str] = None,
    sensor_id: str = "ENV-RAIN-01",
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM rainfall_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return dict(row)


def get_rainfall_history(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM rainfall_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_rainfall_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Compute aggregate analytics for rainfall / precipitation from audit logs."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM rainfall_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total_readings = len(rows)
        rates = [r.get("rainfall_rate_mm_h", 0.0) for r in rows]
        max_rate = max(rates) if rates else 0.0
        avg_rate = (sum(rates) / total_readings) if total_readings > 0 else 0.0
        latest_cumul = rows[-1].get("cumulative_rainfall_mm", 0.0) if rows else 0.0
        online_count = sum(1 for r in rows if r.get("status") == "ONLINE")
        uptime_pct = round((online_count / total_readings * 100.0) if total_readings > 0 else 100.0, 1)

        cls_counts = {
            "NO_RAIN": sum(1 for r in rows if r.get("classification") == "NO_RAIN"),
            "LIGHT": sum(1 for r in rows if r.get("classification") == "LIGHT"),
            "MODERATE": sum(1 for r in rows if r.get("classification") == "MODERATE"),
            "HEAVY": sum(1 for r in rows if r.get("classification") == "HEAVY"),
            "VERY_HEAVY": sum(1 for r in rows if r.get("classification") == "VERY_HEAVY"),
            "EXTREME": sum(1 for r in rows if r.get("classification") == "EXTREME"),
        }

        return {
            "total_readings": total_readings,
            "max_rainfall_rate_mm_h": round(max_rate, 2),
            "average_rainfall_rate_mm_h": round(avg_rate, 2),
            "cumulative_rainfall_mm": round(latest_cumul, 2),
            "uptime_pct": uptime_pct,
            "classification_distribution": cls_counts,
        }


# --------------------------------------------------------------------------- #
# Temperature Reading Persistence & Analytics
# --------------------------------------------------------------------------- #

def log_temperature_reading(
    reading: Any,
    session_id: str,
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    """Log an ambient temperature reading to SQLite."""
    with _connect(db_path) as conn:
        r_dict = reading.to_dict() if hasattr(reading, "to_dict") else dict(reading)
        rid = r_dict.get("reading_id", f"TMP-{uuid.uuid4().hex[:8]}")
        sid = r_dict.get("sensor_id", "ENV-TEMP-01")
        did = r_dict.get("device_id", "DEV-TEMP-01")
        temp_raw = r_dict.get("temperature_c")
        if temp_raw is None:
            temp_raw = r_dict.get("ambient_temp_c", 150.0)
        temp_c = float(temp_raw if temp_raw is not None else 150.0)

        ambient_raw = r_dict.get("ambient_temp_c")
        ambient_c = float(ambient_raw if ambient_raw is not None else temp_c)
        unit = r_dict.get("unit", "°C")
        roc_raw = r_dict.get("rate_of_change", 0.0)
        roc = float(roc_raw if roc_raw is not None else 0.0)
        trend = r_dict.get("trend", "STABLE")
        if hasattr(trend, "value"):
            trend = trend.value

        loc = r_dict.get("location")
        lat = loc[0] if isinstance(loc, (list, tuple)) and len(loc) >= 1 else (loc.get("latitude") if isinstance(loc, dict) else None)
        lon = loc[1] if isinstance(loc, (list, tuple)) and len(loc) >= 2 else (loc.get("longitude") if isinstance(loc, dict) else None)
        alt = loc[2] if isinstance(loc, (list, tuple)) and len(loc) >= 3 else (loc.get("altitude_m") if isinstance(loc, dict) else None)

        status = r_dict.get("status", "ONLINE")
        if hasattr(status, "value"):
            status = status.value
        conf_raw = r_dict.get("confidence", 0.98)
        conf = float(conf_raw if conf_raw is not None else 0.98)
        qual_raw = r_dict.get("quality", 0.98)
        qual = float(qual_raw if qual_raw is not None else 0.98)
        ts = r_dict.get("timestamp", _now())
        raw_json = json.dumps(r_dict.get("raw_data", {}))
        meta_json = json.dumps(r_dict.get("metadata", {}))

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO temperature_readings (
                reading_id, session_id, cycle, sensor_id, device_id,
                temperature_c, ambient_temp_c, unit, rate_of_change, trend,
                latitude, longitude, altitude_m, status, confidence, quality,
                raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cycle, sid, did,
                temp_c, ambient_c, unit, roc, str(trend),
                lat, lon, alt, str(status), conf, qual,
                raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_latest_temperature_reading(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM temperature_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return dict(row)


def get_temperature_history(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM temperature_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_temperature_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Compute aggregate analytics for ambient temperature from audit logs."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM temperature_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total_readings = len(rows)
        temps = [r.get("temperature_c", 15.0) for r in rows]
        max_temp = max(temps) if temps else 15.0
        min_temp = min(temps) if temps else 15.0
        avg_temp = (sum(temps) / total_readings) if total_readings > 0 else 15.0
        online_count = sum(1 for r in rows if r.get("status") == "ONLINE")
        uptime_pct = round((online_count / total_readings * 100.0) if total_readings > 0 else 100.0, 1)

        trend_counts = {
            "STABLE": sum(1 for r in rows if r.get("trend") == "STABLE"),
            "RISING": sum(1 for r in rows if r.get("trend") == "RISING"),
            "RAPIDLY_RISING": sum(1 for r in rows if r.get("trend") == "RAPIDLY_RISING"),
            "FALLING": sum(1 for r in rows if r.get("trend") == "FALLING"),
            "RAPIDLY_FALLING": sum(1 for r in rows if r.get("trend") == "RAPIDLY_FALLING"),
        }

        return {
            "total_readings": total_readings,
            "max_temperature_c": round(max_temp, 2),
            "min_temperature_c": round(min_temp, 2),
            "average_temperature_c": round(avg_temp, 2),
            "uptime_pct": uptime_pct,
            "trend_distribution": trend_counts,
        }


# --------------------------------------------------------------------------- #
# Humidity Reading Persistence & Analytics
# --------------------------------------------------------------------------- #

def log_humidity_reading(
    reading: Any,
    session_id: str,
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    """Log an atmospheric relative humidity reading to SQLite."""
    with _connect(db_path) as conn:
        r_dict = reading.to_dict() if hasattr(reading, "to_dict") else dict(reading)
        rid = r_dict.get("reading_id", f"HUM-{uuid.uuid4().hex[:8]}")
        sid = r_dict.get("sensor_id", "ENV-HUMID-01")
        did = r_dict.get("device_id", "DEV-HUMID-01")
        humid_pct = float(r_dict.get("humidity_pct", 50.0))
        unit = r_dict.get("unit", "%")
        roc = float(r_dict.get("rate_of_change", 0.0))
        trend = r_dict.get("trend", "STABLE")
        if hasattr(trend, "value"):
            trend = trend.value

        loc = r_dict.get("location")
        lat = loc[0] if isinstance(loc, (list, tuple)) and len(loc) >= 1 else (loc.get("latitude") if isinstance(loc, dict) else None)
        lon = loc[1] if isinstance(loc, (list, tuple)) and len(loc) >= 2 else (loc.get("longitude") if isinstance(loc, dict) else None)
        alt = loc[2] if isinstance(loc, (list, tuple)) and len(loc) >= 3 else (loc.get("altitude_m") if isinstance(loc, dict) else None)

        status = r_dict.get("status", "ONLINE")
        if hasattr(status, "value"):
            status = status.value
        conf = float(r_dict.get("confidence", 0.98))
        qual = float(r_dict.get("quality", 0.98))
        ts = r_dict.get("timestamp", _now())
        raw_json = json.dumps(r_dict.get("raw_data", {}))
        meta_json = json.dumps(r_dict.get("metadata", {}))

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO humidity_readings (
                reading_id, session_id, cycle, sensor_id, device_id,
                humidity_pct, unit, rate_of_change, trend,
                latitude, longitude, altitude_m, status, confidence, quality,
                raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cycle, sid, did,
                humid_pct, unit, roc, str(trend),
                lat, lon, alt, str(status), conf, qual,
                raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_latest_humidity_reading(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM humidity_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return dict(row)


def get_humidity_history(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM humidity_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_humidity_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Compute aggregate analytics for atmospheric humidity from audit logs."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM humidity_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total_readings = len(rows)
        humids = [r.get("humidity_pct", 50.0) for r in rows]
        max_humid = max(humids) if humids else 50.0
        min_humid = min(humids) if humids else 50.0
        avg_humid = (sum(humids) / total_readings) if total_readings > 0 else 50.0
        online_count = sum(1 for r in rows if r.get("status") == "ONLINE")
        uptime_pct = round((online_count / total_readings * 100.0) if total_readings > 0 else 100.0, 1)

        trend_counts = {
            "STABLE": sum(1 for r in rows if r.get("trend") == "STABLE"),
            "RISING": sum(1 for r in rows if r.get("trend") == "RISING"),
            "RAPIDLY_RISING": sum(1 for r in rows if r.get("trend") == "RAPIDLY_RISING"),
            "FALLING": sum(1 for r in rows if r.get("trend") == "FALLING"),
            "RAPIDLY_FALLING": sum(1 for r in rows if r.get("trend") == "RAPIDLY_FALLING"),
        }

        return {
            "total_readings": total_readings,
            "max_humidity_pct": round(max_humid, 2),
            "min_humidity_pct": round(min_humid, 2),
            "average_humidity_pct": round(avg_humid, 2),
            "uptime_pct": uptime_pct,
            "trend_distribution": trend_counts,
        }


# --------------------------------------------------------------------------- #
# Water-Level & Flow Persistence & Analytics
# --------------------------------------------------------------------------- #

def log_water_level_reading(
    reading: Any,
    session_id: str,
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    """Log structured Water-Level & flow telemetry into water_level_readings table."""
    with _connect(db_path) as conn:
        r_dict = reading.to_dict() if hasattr(reading, "to_dict") else dict(reading)
        rid = r_dict.get("reading_id") or f"WTR-{session_id}-{cycle}-{uuid.uuid4().hex[:6]}"
        sid = r_dict.get("sensor_id", "ENV-WATER-01")
        did = r_dict.get("device_id", "DEV-WATER-01")
        w_lvl = float(r_dict.get("water_level_cm", 0.0))
        w_flow = float(r_dict.get("water_flow_mps", 0.0))
        unit = str(r_dict.get("unit", "cm"))
        roc = float(r_dict.get("rate_of_change", 0.0))
        trend = r_dict.get("trend", "STABLE")
        if hasattr(trend, "value"):
            trend = trend.value
        cls_val = r_dict.get("classification", "NORMAL")
        if hasattr(cls_val, "value"):
            cls_val = cls_val.value
        sev = r_dict.get("severity", "LOW")
        if hasattr(sev, "value"):
            sev = sev.value

        loc = r_dict.get("location")
        lat = loc[0] if isinstance(loc, (list, tuple)) and len(loc) >= 1 else (loc.get("latitude") if isinstance(loc, dict) else None)
        lon = loc[1] if isinstance(loc, (list, tuple)) and len(loc) >= 2 else (loc.get("longitude") if isinstance(loc, dict) else None)
        alt = loc[2] if isinstance(loc, (list, tuple)) and len(loc) >= 3 else (loc.get("altitude_m") if isinstance(loc, dict) else None)

        status = r_dict.get("status", "ONLINE")
        if hasattr(status, "value"):
            status = status.value
        conf = float(r_dict.get("confidence", 0.98))
        qual = float(r_dict.get("quality", 0.98))
        ts = r_dict.get("timestamp", _now())
        raw_json = json.dumps(r_dict.get("raw_data", {}))
        meta_json = json.dumps(r_dict.get("metadata", {}))

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO water_level_readings (
                reading_id, session_id, cycle, sensor_id, device_id,
                water_level_cm, water_flow_mps, unit, rate_of_change, trend,
                classification, severity,
                latitude, longitude, altitude_m, status, confidence, quality,
                raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cycle, sid, did,
                w_lvl, w_flow, unit, roc, str(trend),
                str(cls_val), str(sev),
                lat, lon, alt, str(status), conf, qual,
                raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_latest_water_level_reading(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM water_level_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return dict(row)


def get_water_level_history(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM water_level_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_water_level_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Compute aggregate analytics for water level and flood dynamics from audit logs."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM water_level_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total_readings = len(rows)
        levels = [r.get("water_level_cm", 0.0) for r in rows]
        flows = [r.get("water_flow_mps", 0.0) for r in rows]
        max_level = max(levels) if levels else 0.0
        min_level = min(levels) if levels else 0.0
        avg_level = (sum(levels) / total_readings) if total_readings > 0 else 0.0
        max_flow = max(flows) if flows else 0.0
        online_count = sum(1 for r in rows if r.get("status") == "ONLINE")
        uptime_pct = round((online_count / total_readings * 100.0) if total_readings > 0 else 100.0, 1)

        trend_counts = {
            "STABLE": sum(1 for r in rows if r.get("trend") == "STABLE"),
            "RISING": sum(1 for r in rows if r.get("trend") == "RISING"),
            "RAPIDLY_RISING": sum(1 for r in rows if r.get("trend") == "RAPIDLY_RISING"),
            "FALLING": sum(1 for r in rows if r.get("trend") == "FALLING"),
            "RAPIDLY_FALLING": sum(1 for r in rows if r.get("trend") == "RAPIDLY_FALLING"),
        }

        return {
            "total_readings": total_readings,
            "max_water_level_cm": round(max_level, 2),
            "min_water_level_cm": round(min_level, 2),
            "average_water_level_cm": round(avg_level, 2),
            "max_flow_velocity_mps": round(max_flow, 2),
            "uptime_pct": uptime_pct,
            "trend_distribution": trend_counts,
        }


def log_gps_reading(
    reading: Any,
    session_id: str,
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    """Log a GPSReading or dict representation to the gps_readings table."""
    with _connect(db_path) as conn:
        if hasattr(reading, "to_dict"):
            r_dict = reading.to_dict()
        elif isinstance(reading, dict):
            r_dict = reading
        else:
            r_dict = vars(reading)

        rid = r_dict.get("reading_id") or f"GPS-{session_id}-{cycle}-{uuid.uuid4().hex[:6]}"
        sid = r_dict.get("sensor_id", "DEV-GPS-01")
        did = r_dict.get("device_id", "RESCUE-KIT-01")
        stype = r_dict.get("sensor_type", "gps")
        if hasattr(stype, "value"):
            stype = stype.value
        lat = float(r_dict.get("latitude", 32.3739))
        lon = float(r_dict.get("longitude", 77.2491))
        alt = float(r_dict.get("altitude_m", 3950.0))
        acc = float(r_dict.get("accuracy_m", 2.5))
        spd = float(r_dict.get("speed_mps", 0.0))
        hdg = float(r_dict.get("heading_deg", 0.0))
        sats = int(r_dict.get("satellites", 12))
        mov = r_dict.get("movement_state", "STATIONARY")
        if hasattr(mov, "value"):
            mov = mov.value
        fix = 1 if r_dict.get("is_valid_fix", True) else 0
        status = r_dict.get("status", "ONLINE")
        if hasattr(status, "value"):
            status = status.value
        conf = float(r_dict.get("confidence", 0.98))
        qual = float(r_dict.get("quality", 0.98))
        scenario_id = r_dict.get("scenario_id")
        entity_type = r_dict.get("entity_type", "DEVICE")
        entity_id = r_dict.get("entity_id")
        ts = r_dict.get("timestamp", _now())
        raw_json = json.dumps(r_dict.get("raw_data", {}))
        meta_json = json.dumps(r_dict.get("metadata", {}))

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO gps_readings (
                reading_id, session_id, cycle, sensor_id, device_id, sensor_type,
                latitude, longitude, altitude_m, accuracy_m, speed_mps, heading_deg,
                satellites, movement_state, is_valid_fix, status, confidence, quality,
                scenario_id, entity_type, entity_id, raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cycle, sid, did, str(stype),
                lat, lon, alt, acc, spd, hdg,
                sats, str(mov), fix, str(status), conf, qual,
                scenario_id, entity_type, entity_id, raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_latest_gps_reading(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Retrieve most recent logged GPS reading."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM gps_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return dict(row)


def get_gps_history(
    session_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    """Retrieve chronological history of logged GPS readings."""
    with _connect(db_path) as conn:
        query = "SELECT * FROM gps_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_id:
            query += " AND sensor_id = ?"
            params.append(sensor_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_gps_trail(
    session_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    """Retrieve chronological coordinate trail breadcrumbs for geospatial map rendering."""
    with _connect(db_path) as conn:
        query = "SELECT latitude, longitude, altitude_m, speed_mps, heading_deg, accuracy_m, movement_state, timestamp FROM gps_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_gps_analytics(session_id: Optional[str] = None, db_path: Optional[str] = None) -> dict:
    """Compute summary kinematic and accuracy statistics for GPS readings."""
    with _connect(db_path) as conn:
        if session_id:
            rows = conn.execute(
                "SELECT * FROM gps_readings WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM gps_readings ORDER BY timestamp ASC LIMIT 500"
            ).fetchall()

        if not rows:
            return {
                "total_readings": 0,
                "online_count": 0,
                "degraded_count": 0,
                "offline_count": 0,
                "uptime_pct": 0.0,
                "fix_availability_pct": 0.0,
                "average_accuracy_m": None,
                "avg_accuracy_m": None,
                "min_accuracy_m": None,
                "max_accuracy_m": None,
                "average_speed_mps": None,
                "avg_speed_mps": None,
                "max_speed_mps": None,
                "average_satellites": None,
                "avg_satellites": None,
                "total_distance_m": 0.0,
                "anomaly_count": 0,
                "movement_distribution": {},
                "latest_coordinates": None,
            }

        total_readings = len(rows)
        online_count = sum(1 for r in rows if r["status"] == "ONLINE")
        degraded_count = sum(1 for r in rows if r["status"] == "DEGRADED")
        offline_count = sum(1 for r in rows if r["status"] == "OFFLINE")
        uptime_pct = round((online_count / total_readings) * 100.0, 1)

        accs = [r["accuracy_m"] for r in rows if r["accuracy_m"] is not None]
        spds = [r["speed_mps"] for r in rows if r["speed_mps"] is not None]
        sats = [r["satellites"] for r in rows if r["satellites"] is not None]

        avg_acc = (sum(accs) / len(accs)) if accs else None
        min_acc = min(accs) if accs else None
        max_acc = max(accs) if accs else None

        avg_spd = (sum(spds) / len(spds)) if spds else None
        max_spd = max(spds) if spds else None
        avg_sats = (sum(sats) / len(sats)) if sats else None

        # Cumulative distance
        total_distance_m = 0.0
        for i in range(1, len(rows)):
            lat1, lon1 = rows[i - 1]["latitude"], rows[i - 1]["longitude"]
            lat2, lon2 = rows[i]["latitude"], rows[i]["longitude"]
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlam = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
            c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            step_d = 6371000.0 * c
            if step_d < 1000.0:
                total_distance_m += step_d

        movement_counts = defaultdict(int)
        for r in rows:
            m = r["movement_state"] or "UNKNOWN"
            movement_counts[m] += 1

        latest = rows[-1] if rows else None
        latest_coords = {
            "latitude": latest["latitude"] if latest else 32.3739,
            "longitude": latest["longitude"] if latest else 77.2491,
            "altitude_m": latest["altitude_m"] if latest else 3950.0,
        }

        return {
            "total_readings": total_readings,
            "online_count": online_count,
            "degraded_count": degraded_count,
            "offline_count": offline_count,
            "uptime_pct": uptime_pct,
            "fix_availability_pct": uptime_pct,
            "average_accuracy_m": round(avg_acc, 2) if avg_acc is not None else None,
            "avg_accuracy_m": round(avg_acc, 2) if avg_acc is not None else None,
            "min_accuracy_m": round(min_acc, 2) if min_acc is not None else None,
            "max_accuracy_m": round(max_acc, 2) if max_acc is not None else None,
            "average_speed_mps": round(avg_spd, 2) if avg_spd is not None else None,
            "avg_speed_mps": round(avg_spd, 2) if avg_spd is not None else None,
            "max_speed_mps": round(max_spd, 2) if max_spd is not None else None,
            "average_satellites": round(avg_sats, 1) if avg_sats is not None else None,
            "avg_satellites": round(avg_sats, 1) if avg_sats is not None else None,
            "total_distance_m": round(total_distance_m, 1),
            "anomaly_count": movement_counts["JUMP_ANOMALY"],
            "movement_distribution": dict(movement_counts),
            "latest_coordinates": latest_coords,
        }


# --------------------------------------------------------------------------- #
# Optical RGB Camera Persistence & Analytics
# --------------------------------------------------------------------------- #

def log_camera_reading(
    reading: Any,
    session_id: str,
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    """Log structured optical RGB camera telemetry into camera_readings table."""
    with _connect(db_path) as conn:
        r_dict = reading.to_dict() if hasattr(reading, "to_dict") else dict(reading)
        rid = r_dict.get("reading_id") or f"CAMR-{uuid.uuid4().hex[:8]}"
        cid = r_dict.get("camera_id", "CAM-001")
        did = r_dict.get("device_id", "DEV-CAM-01")
        vid = r_dict.get("victim_id")
        dstate = r_dict.get("detection_state", "NO_DETECTION")
        if hasattr(dstate, "value"):
            dstate = dstate.value
        dtype = r_dict.get("detection_type", "none")
        cls_val = r_dict.get("classification", "UNKNOWN")
        if hasattr(cls_val, "value"):
            cls_val = cls_val.value
        cls_conf = float(r_dict.get("classification_confidence", 0.0))
        pcount = int(r_dict.get("person_count", 0))
        conf = float(r_dict.get("confidence", 0.0))
        vis = float(r_dict.get("visibility", 1.0))
        occ = float(r_dict.get("occlusion", 0.0))
        qual = float(r_dict.get("image_quality", 1.0))
        mot = int(bool(r_dict.get("motion_detected", False)))
        smk = int(bool(r_dict.get("smoke_present", False)))
        fire = int(bool(r_dict.get("fire_visible", False)))
        deb = int(bool(r_dict.get("debris_present", False)))
        orient = str(r_dict.get("orientation", "0° NADIR"))
        fov = float(r_dict.get("field_of_view_deg", 85.0))
        rng = float(r_dict.get("range_m", 30.0))
        status = r_dict.get("status", "ONLINE")
        if hasattr(status, "value"):
            status = status.value
        hscore = float(r_dict.get("health_score", 100.0))

        loc = r_dict.get("location")
        lat = loc[0] if isinstance(loc, (list, tuple)) and len(loc) >= 1 else (loc.get("latitude") if isinstance(loc, dict) else None)
        lon = loc[1] if isinstance(loc, (list, tuple)) and len(loc) >= 2 else (loc.get("longitude") if isinstance(loc, dict) else None)

        raw_json = json.dumps(r_dict.get("raw_data", {}))
        meta_json = json.dumps(r_dict.get("metadata", {}))
        ts = r_dict.get("timestamp", _now())

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO camera_readings (
                reading_id, session_id, camera_id, device_id, victim_id,
                detection_state, detection_type, classification, classification_confidence,
                person_count, confidence, visibility, occlusion, image_quality,
                motion_detected, smoke_present, fire_visible, debris_present,
                orientation, field_of_view_deg, range_m, status, health_score,
                latitude, longitude, raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cid, did, vid,
                str(dstate), str(dtype), str(cls_val), cls_conf,
                pcount, conf, vis, occ, qual,
                mot, smk, fire, deb,
                orient, fov, rng, str(status), hscore,
                lat, lon, raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_latest_camera_reading(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM camera_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT 1"
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def get_camera_history(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM camera_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_camera_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    with _connect(db_path) as conn:
        query = "SELECT * FROM camera_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total = len(rows)
        confs = [r.get("confidence", 0.0) for r in rows]
        visibilities = [r.get("visibility", 1.0) for r in rows]
        occlusions = [r.get("occlusion", 0.0) for r in rows]
        online_count = sum(1 for r in rows if r.get("status") == "ONLINE")
        motion_count = sum(1 for r in rows if r.get("motion_detected") == 1)
        persons_detected = sum(1 for r in rows if r.get("person_count", 0) > 0 or r.get("detection_state") in ("PERSON_DETECTED", "MULTIPLE_PERSONS", "PARTIAL_PERSON"))

        return {
            "total_readings": total,
            "average_confidence": round(sum(confs) / total, 2) if total else 0.0,
            "max_confidence": round(max(confs), 2) if confs else 0.0,
            "average_visibility": round(sum(visibilities) / total, 2) if total else 1.0,
            "average_occlusion": round(sum(occlusions) / total, 2) if total else 0.0,
            "motion_detections_count": motion_count,
            "person_detections_count": persons_detected,
            "uptime_pct": round((online_count / total * 100.0) if total else 100.0, 1),
        }


# --------------------------------------------------------------------------- #
# Thermal Infrared Camera Persistence & Analytics
# --------------------------------------------------------------------------- #

def log_thermal_reading(
    reading: Any,
    session_id: str,
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    """Log structured LWIR thermal camera telemetry into thermal_readings table."""
    with _connect(db_path) as conn:
        r_dict = reading.to_dict() if hasattr(reading, "to_dict") else dict(reading)
        rid = r_dict.get("reading_id") or f"THMR-{uuid.uuid4().hex[:8]}"
        cid = r_dict.get("camera_id", "THERMAL-001")
        did = r_dict.get("device_id", "DEV-THM-01")
        vid = r_dict.get("victim_id")
        dtype = r_dict.get("detection_type", "NO_HEAT")
        if hasattr(dtype, "value"):
            dtype = dtype.value
        cls_val = r_dict.get("classification", "NO_SIGNATURE")
        if hasattr(cls_val, "value"):
            cls_val = cls_val.value
        cls_conf = float(r_dict.get("classification_confidence", 0.0))
        heat_det = int(bool(r_dict.get("heat_signature_detected", False)))
        hum_sig = int(bool(r_dict.get("human_signature", False)))
        hcount = int(r_dict.get("heat_signature_count", 0))
        tconf = float(r_dict.get("thermal_confidence", 0.0))
        etemp = float(r_dict.get("estimated_temperature", 20.0))
        bgtemp = float(r_dict.get("background_temperature", 18.0))
        tdelta = float(r_dict.get("temperature_delta", 2.0))
        tvis = float(r_dict.get("thermal_visibility", 1.0))
        tcontrast = float(r_dict.get("thermal_contrast", 1.0))
        occ = float(r_dict.get("occlusion", 0.0))
        fire = int(bool(r_dict.get("fire_hotspot", False)))
        debris = int(bool(r_dict.get("hot_debris", False)))
        orient = str(r_dict.get("orientation", "0° NADIR"))
        fov = float(r_dict.get("field_of_view_deg", 60.0))
        rng = float(r_dict.get("range_m", 40.0))
        status = r_dict.get("status", "ONLINE")
        if hasattr(status, "value"):
            status = status.value
        hscore = float(r_dict.get("health_score", 100.0))

        loc = r_dict.get("location")
        lat = loc[0] if isinstance(loc, (list, tuple)) and len(loc) >= 1 else (loc.get("latitude") if isinstance(loc, dict) else None)
        lon = loc[1] if isinstance(loc, (list, tuple)) and len(loc) >= 2 else (loc.get("longitude") if isinstance(loc, dict) else None)

        raw_json = json.dumps(r_dict.get("raw_data", {}))
        meta_json = json.dumps(r_dict.get("metadata", {}))
        ts = r_dict.get("timestamp", _now())

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO thermal_readings (
                reading_id, session_id, camera_id, device_id, victim_id,
                detection_type, classification, classification_confidence,
                heat_signature_detected, human_signature, heat_signature_count,
                thermal_confidence, estimated_temperature, background_temperature,
                temperature_delta, thermal_visibility, thermal_contrast, occlusion,
                fire_hotspot, hot_debris, orientation, field_of_view_deg, range_m,
                status, health_score, latitude, longitude, raw_data_json, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid, session_id, cid, did, vid,
                str(dtype), str(cls_val), cls_conf,
                heat_det, hum_sig, hcount,
                tconf, etemp, bgtemp,
                tdelta, tvis, tcontrast, occ,
                fire, debris, orient, fov, rng,
                str(status), hscore, lat, lon, raw_json, meta_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_latest_thermal_reading(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM thermal_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT 1"
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def get_thermal_history(
    session_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM thermal_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if victim_id:
            query += " AND victim_id = ?"
            params.append(victim_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_thermal_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    with _connect(db_path) as conn:
        query = "SELECT * FROM thermal_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total = len(rows)
        confs = [r.get("thermal_confidence", 0.0) for r in rows]
        temps = [r.get("estimated_temperature", 20.0) for r in rows]
        deltas = [r.get("temperature_delta", 0.0) for r in rows]
        online_count = sum(1 for r in rows if r.get("status") == "ONLINE")
        heat_count = sum(1 for r in rows if r.get("heat_signature_detected") == 1)
        human_count = sum(1 for r in rows if r.get("human_signature") == 1)
        hotspot_count = sum(1 for r in rows if r.get("fire_hotspot") == 1)

        return {
            "total_readings": total,
            "average_thermal_confidence": round(sum(confs) / total, 2) if total else 0.0,
            "max_temperature_c": round(max(temps), 1) if temps else 20.0,
            "min_temperature_c": round(min(temps), 1) if temps else 20.0,
            "average_temperature_c": round(sum(temps) / total, 1) if total else 20.0,
            "average_delta_c": round(sum(deltas) / total, 1) if total else 0.0,
            "heat_detections_count": heat_count,
            "human_heat_signatures_count": human_count,
            "fire_hotspots_count": hotspot_count,
            "uptime_pct": round((online_count / total * 100.0) if total else 100.0, 1),
        }


# --------------------------------------------------------------------------- #
# Rejected / Corrupted Sensor Reading Quarantine Ledger
# --------------------------------------------------------------------------- #

def log_rejected_reading(
    rejected: Any,
    session_id: Optional[str] = None,
    cycle: int = 0,
    db_path: Optional[str] = None,
) -> int:
    """Log an invalid/rejected sensor reading into rejected_sensor_readings audit ledger."""
    with _connect(db_path) as conn:
        r_dict = rejected.to_dict() if hasattr(rejected, "to_dict") else (dict(rejected) if isinstance(rejected, dict) else (vars(rejected) if hasattr(rejected, "__dict__") else {}))
        rejid = r_dict.get("rejection_id") or f"REJ-{uuid.uuid4().hex[:8]}"
        sess_id = r_dict.get("session_id") or session_id or "unassigned"
        cyc = r_dict.get("cycle") or cycle
        stype = r_dict.get("sensor_type", "unknown")
        if hasattr(stype, "value"):
            stype = stype.value
        sid = r_dict.get("sensor_id")
        did = r_dict.get("device_id")
        vid = r_dict.get("victim_id")
        val = r_dict.get("attempted_value")
        unit = r_dict.get("unit")
        reason = r_dict.get("rejection_reason", "Validation failure")
        raw_json = json.dumps(r_dict.get("raw_payload", {}))
        ts = r_dict.get("timestamp", _now())

        cur = conn.execute(
            """
            INSERT OR REPLACE INTO rejected_sensor_readings (
                rejection_id, session_id, cycle, sensor_type, sensor_id,
                device_id, victim_id, attempted_value, unit,
                rejection_reason, raw_payload_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rejid, sess_id, cyc, str(stype), sid,
                did, vid, val, unit,
                reason, raw_json, ts
            )
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_rejected_readings(
    session_id: Optional[str] = None,
    sensor_type: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        query = "SELECT * FROM rejected_sensor_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if sensor_type:
            query += " AND sensor_type = ?"
            params.append(sensor_type)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_rejection_analytics(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    with _connect(db_path) as conn:
        query = "SELECT * FROM rejected_sensor_readings WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total = len(rows)
        by_type = defaultdict(int)
        for r in rows:
            by_type[r.get("sensor_type", "unknown")] += 1
        return {
            "total_rejections": total,
            "rejections_by_sensor_type": dict(by_type),
            "recent_rejections": rows[-10:] if rows else [],
        }


# --------------------------------------------------------------------------- #
# Sensor Health & Trends Batch Persistence
# --------------------------------------------------------------------------- #

def log_sensor_health_batch(
    health_records: List[Any],
    session_id: str,
    cycle: int,
    db_path: Optional[str] = None,
) -> None:
    """Log a cycle snapshot of all active sensor health records."""
    with _connect(db_path) as conn:
        records = []
        ts = _now()
        for h in health_records:
            h_dict = h.to_dict() if hasattr(h, "to_dict") else dict(h)
            sid = h_dict.get("sensor_id", "UNKNOWN")
            stype = h_dict.get("sensor_type", "unknown")
            if hasattr(stype, "value"):
                stype = stype.value
            stat = h_dict.get("status", "ONLINE")
            if hasattr(stat, "value"):
                stat = stat.value
            bat = float(h_dict.get("battery_pct", 100.0))
            sig = float(h_dict.get("signal_quality", 1.0))
            err = h_dict.get("error_message")
            records.append((session_id, cycle, sid, str(stype), str(stat), bat, sig, err, ts))

        conn.executemany(
            """
            INSERT INTO sensor_health_records (
                session_id, cycle, sensor_id, sensor_type, status,
                battery_pct, signal_quality, error_message, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records
        )


def log_sensor_trends_batch(
    trends: List[Any],
    session_id: str,
    cycle: int,
    db_path: Optional[str] = None,
) -> None:
    """Log trend tracking records across sensor channels."""
    with _connect(db_path) as conn:
        records = []
        ts = _now()
        for t in trends:
            t_dict = t.to_dict() if hasattr(t, "to_dict") else dict(t)
            stype = t_dict.get("sensor_type", "unknown")
            if hasattr(stype, "value"):
                stype = stype.value
            cval = float(t_dict.get("current_value", 0.0))
            roc = float(t_dict.get("rate_of_change_per_cycle", 0.0))
            tdir = str(t_dict.get("trend_direction", "STABLE"))
            spike = int(bool(t_dict.get("is_spike", False)))
            sustained = int(bool(t_dict.get("is_sustained_abnormal", False)))
            anom = float(t_dict.get("anomaly_score", 0.0))
            records.append((session_id, cycle, str(stype), cval, roc, tdir, spike, sustained, anom, ts))

        conn.executemany(
            """
            INSERT INTO sensor_trends (
                session_id, cycle, sensor_type, current_value, rate_of_change,
                trend_direction, is_spike, is_sustained_abnormal, anomaly_score, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records
        )


def export_session_csv(session_id: str, db_path: Optional[str] = None) -> str:
    """
    Export a session's full log (sensor readings + fused detection results +
    rescue-team status events) as a single CSV document, chronologically
    ordered, for use in the report's testing/evaluation chapter.

    Returns the CSV content as a string.
    """
    with _connect(db_path) as conn:
        rows = _fetch_unified_rows(conn, session_id)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def export_session_csv_file(session_id: str, path: str, db_path: Optional[str] = None) -> str:
    """Write export_session_csv()'s output to `path` and return the path."""
    csv_text = export_session_csv(session_id, db_path=db_path)
    with open(path, "w", newline="") as f:
        f.write(csv_text)
    return path


# --------------------------------------------------------------------------- #
# Real Wearable IoT & Companion Bridge Persistence Layer
# --------------------------------------------------------------------------- #

def _ensure_wearable_tables(conn: sqlite3.Connection) -> None:
    """Idempotently create tables for physical smartwatches, rescue commands, and companion bridges."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wearable_devices (
            device_id                  TEXT PRIMARY KEY,
            device_name                TEXT NOT NULL,
            model                      TEXT NOT NULL,
            bluetooth_name             TEXT NOT NULL,
            mac_address                TEXT NOT NULL,
            serial_number              TEXT,
            software_version           TEXT,
            firmware_version           TEXT,
            hardware_id                TEXT,
            assigned_team              TEXT,
            location_source            TEXT DEFAULT 'PHONE_GPS',
            connection_status          TEXT DEFAULT 'DISCONNECTED',
            battery_pct                REAL DEFAULT 100.0,
            capabilities_json          TEXT,
            diagnostic_report_json     TEXT,
            last_seen                  TEXT
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rescue_commands (
            command_id                 TEXT PRIMARY KEY,
            mission_id                 TEXT,
            scenario_id                TEXT,
            team_id                    TEXT NOT NULL,
            member_id                  TEXT,
            victim_id                  TEXT,
            destination_latitude       REAL NOT NULL,
            destination_longitude      REAL NOT NULL,
            destination_altitude_m     REAL DEFAULT 0.0,
            destination_label          TEXT,
            priority                   TEXT DEFAULT 'HIGH',
            command_type               TEXT DEFAULT 'GO_TO_LOCATION',
            command_text               TEXT,
            target_device_id           TEXT,
            location_source            TEXT DEFAULT 'PHONE_GPS',
            status                     TEXT DEFAULT 'ASSIGNED',
            delivery_error             TEXT,
            created_at                 TEXT NOT NULL,
            delivered_at               TEXT,
            acknowledged_at            TEXT,
            completed_at               TEXT
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bridge_sessions (
            session_id                 TEXT PRIMARY KEY,
            team_id                    TEXT NOT NULL,
            device_name                TEXT,
            member_id                  TEXT,
            bluetooth_state            TEXT DEFAULT 'ENABLED',
            watch_connected            INTEGER DEFAULT 0,
            watch_device_id            TEXT,
            watch_mac                  TEXT,
            watch_model                TEXT,
            gps_available              INTEGER DEFAULT 1,
            location_source            TEXT DEFAULT 'PHONE_GPS',
            latitude                   REAL,
            longitude                  REAL,
            altitude_m                 REAL,
            status                     TEXT DEFAULT 'ONLINE',
            notes                      TEXT,
            last_heartbeat             TEXT NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wearable_telemetry (
            id                         INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id                  TEXT NOT NULL,
            team_id                    TEXT,
            session_id                 TEXT,
            latitude                   REAL NOT NULL,
            longitude                  REAL NOT NULL,
            altitude_m                 REAL,
            accuracy_m                 REAL,
            speed_mps                  REAL,
            battery_pct                REAL,
            heart_rate_bpm             REAL,
            step_count                 INTEGER,
            timestamp                  TEXT NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_inbound_sms (
            message_id                 TEXT PRIMARY KEY,
            sender                     TEXT,
            content                    TEXT,
            parsed_command_id          TEXT,
            processed_at               TEXT NOT NULL,
            status                     TEXT NOT NULL
        );
    """)

    # Ensure all columns exist for existing tables
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(wearable_devices)")}
    for col, ctype in [
        ("model", "TEXT"), ("bluetooth_name", "TEXT"), ("serial_number", "TEXT"),
        ("software_version", "TEXT"), ("firmware_version", "TEXT"), ("hardware_id", "TEXT"),
        ("assigned_team", "TEXT"), ("location_source", "TEXT DEFAULT 'PHONE_GPS'"),
        ("connection_status", "TEXT DEFAULT 'DISCONNECTED'"), ("battery_pct", "REAL DEFAULT 100.0"),
        ("capabilities_json", "TEXT"), ("diagnostic_report_json", "TEXT"), ("last_seen", "TEXT"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE wearable_devices ADD COLUMN {col} {ctype}")

    existing_cmd_cols = {row["name"] for row in conn.execute("PRAGMA table_info(rescue_commands)")}
    for col, ctype in [
        ("mission_id", "TEXT"), ("scenario_id", "TEXT"), ("member_id", "TEXT"),
        ("victim_id", "TEXT"),
        ("destination_latitude", "REAL DEFAULT 0.0"), ("destination_longitude", "REAL DEFAULT 0.0"),
        ("destination_altitude_m", "REAL DEFAULT 0.0"), ("destination_label", "TEXT"),
        ("latitude", "REAL DEFAULT 0.0"), ("longitude", "REAL DEFAULT 0.0"),
        ("altitude_m", "REAL DEFAULT 0.0"), ("location_label", "TEXT"),
        ("priority", "TEXT DEFAULT 'HIGH'"),
        ("command_type", "TEXT DEFAULT 'GO_TO_LOCATION'"), ("command_text", "TEXT"),
        ("target_device_id", "TEXT"), ("location_source", "TEXT DEFAULT 'PHONE_GPS'"),
        ("status", "TEXT DEFAULT 'ASSIGNED'"), ("delivery_error", "TEXT"),
        ("watch_delivery_status", "TEXT DEFAULT 'PENDING'"),
        ("bridge_sent_at", "TEXT"), ("phone_notification_posted_at", "TEXT"),
        ("created_at", "TEXT"), ("delivered_at", "TEXT"), ("acknowledged_at", "TEXT"), ("completed_at", "TEXT"),
        ("phone_number", "TEXT"), ("phone_number_masked", "TEXT"),
        ("sms_status", "TEXT DEFAULT 'QUEUED'"), ("sms_error", "TEXT"),
        ("acceptance_source", "TEXT"), ("accepted_at", "TEXT"),
    ]:
        if col not in existing_cmd_cols:
            conn.execute(f"ALTER TABLE rescue_commands ADD COLUMN {col} {ctype}")

    existing_notif_cols = {row["name"] for row in conn.execute("PRAGMA table_info(notification_center)")}
    for col, ctype in [
        ("rescue_command_id", "TEXT"),
        ("mission_id", "TEXT"),
        ("phone_number", "TEXT"),
        ("phone_number_masked", "TEXT"),
        ("sms_status", "TEXT DEFAULT 'QUEUED'"),
        ("sms_error", "TEXT"),
        ("sps", "REAL DEFAULT 0.0"),
        ("latitude", "REAL DEFAULT 0.0"),
        ("longitude", "REAL DEFAULT 0.0"),
        ("required_action", "TEXT"),
        ("acceptance_source", "TEXT"),
        ("accepted_at", "TEXT"),
    ]:
        if col not in existing_notif_cols:
            conn.execute(f"ALTER TABLE notification_center ADD COLUMN {col} {ctype}")

    existing_bridge_cols = {row["name"] for row in conn.execute("PRAGMA table_info(bridge_sessions)")}
    for col, ctype in [
        ("accuracy_m", "REAL"),
        ("speed_mps", "REAL"),
        ("heading_deg", "REAL"),
        ("gps_timestamp", "TEXT"),
        ("navigation_status", "TEXT"),
        ("distance_to_target_m", "REAL"),
        ("target_bearing_deg", "REAL"),
        ("heading_difference_deg", "REAL"),
        ("distance_trend", "TEXT"),
    ]:
        if col not in existing_bridge_cols:
            conn.execute(f"ALTER TABLE bridge_sessions ADD COLUMN {col} {ctype}")

    existing_telemetry_cols = {row["name"] for row in conn.execute("PRAGMA table_info(wearable_telemetry)")}
    for col, ctype in [
        ("heading_deg", "REAL"),
    ]:
        if col not in existing_telemetry_cols:
            conn.execute(f"ALTER TABLE wearable_telemetry ADD COLUMN {col} {ctype}")

    existing_cmd_cols = {row["name"] for row in conn.execute("PRAGMA table_info(rescue_commands)")}
    for col, ctype in [
        ("navigation_status", "TEXT"),
        ("target_bearing_deg", "REAL"),
        ("direction_delta_deg", "REAL"),
        ("heading_difference_deg", "REAL"),
        ("distance_to_target_m", "REAL"),
        ("distance_trend", "TEXT"),
        ("direction_guidance", "TEXT"),
        ("direction_alert_last_sent_at", "TEXT"),
        ("arrived_at", "TEXT"),
    ]:
        if col not in existing_cmd_cols:
            conn.execute(f"ALTER TABLE rescue_commands ADD COLUMN {col} {ctype}")

    # Clean up obsolete T800 Ultra devices from database if present
    conn.execute("DELETE FROM wearable_devices WHERE device_id = 'DEV-WEARABLE-T800' OR device_name LIKE '%T800%' OR model LIKE '%T800%'")

    # Seed default physical Wave Call Plus device if absent
    count = conn.execute("SELECT COUNT(*) AS c FROM wearable_devices").fetchone()["c"]
    if count == 0:
        now = _now()
        conn.execute("""
            INSERT OR IGNORE INTO wearable_devices (
                device_id, device_name, model, bluetooth_name, mac_address,
                serial_number, software_version, firmware_version, hardware_id,
                assigned_team, location_source, connection_status, battery_pct, last_seen
            ) VALUES (
                'DEV-WEARABLE-CALLPLUS', 'Wave Call Plus', 'Wave Call Plus', 'CALLPLUS_7F1B', 'CB:4E:FD:EE:7F:1B',
                '230105502503539', '6.4.3582.28', '6.4.3582.28', 'Wave Call Plus (230105502503539)',
                'RESCUE-1', 'PHONE_GPS', 'DISCONNECTED', 100.0, ?
            )
        """, (now,))


def list_wearable_devices(team_id: Optional[str] = None, db_path: Optional[str] = None) -> List[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        if team_id:
            rows = conn.execute("SELECT * FROM wearable_devices WHERE assigned_team = ?", (team_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM wearable_devices ORDER BY device_id ASC").fetchall()
        devices = []
        for r in rows:
            d = dict(r)
            if d.get("capabilities_json"):
                try:
                    d["capabilities"] = json.loads(d["capabilities_json"])
                except Exception:
                    d["capabilities"] = {}
            if d.get("diagnostic_report_json"):
                try:
                    d["diagnostic_report"] = json.loads(d["diagnostic_report_json"])
                except Exception:
                    d["diagnostic_report"] = {}
            devices.append(d)
        return devices


def get_wearable_device(device_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        row = conn.execute("SELECT * FROM wearable_devices WHERE device_id = ?", (device_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("capabilities_json"):
            try:
                d["capabilities"] = json.loads(d["capabilities_json"])
            except Exception:
                d["capabilities"] = {}
        if d.get("diagnostic_report_json"):
            try:
                d["diagnostic_report"] = json.loads(d["diagnostic_report_json"])
            except Exception:
                d["diagnostic_report"] = {}
        return d


def update_wearable_device_status(
    device_id: str,
    status: str,
    battery_pct: Optional[float] = None,
    db_path: Optional[str] = None,
) -> None:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        now = _now()
        if battery_pct is not None:
            conn.execute(
                "UPDATE wearable_devices SET connection_status = ?, battery_pct = ?, last_seen = ? WHERE device_id = ?",
                (status, battery_pct, now, device_id),
            )
        else:
            conn.execute(
                "UPDATE wearable_devices SET connection_status = ?, last_seen = ? WHERE device_id = ?",
                (status, now, device_id),
            )


def assign_wearable_device_to_team(device_id: str, team_id: str, db_path: Optional[str] = None) -> None:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        conn.execute("UPDATE wearable_devices SET assigned_team = ? WHERE device_id = ?", (team_id, device_id))


def create_rescue_command(
    command_id: str,
    team_id: str,
    destination_latitude: float = 0.0,
    destination_longitude: float = 0.0,
    scenario_id: Optional[str] = None,
    member_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    destination_altitude_m: float = 0.0,
    destination_label: Optional[str] = None,
    priority: str = "HIGH",
    command_type: str = "GO_TO_LOCATION",
    command_text: Optional[str] = None,
    target_device_id: Optional[str] = None,
    location_source: str = "PHONE_GPS",
    watch_delivery_status: str = "PENDING",
    mission_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        now = _now()
        effective_mission_id = mission_id or f"MSN-{command_id}"

        # Ensure parent rescue_missions entry exists if table exists to satisfy foreign key constraints
        has_missions_tbl = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='rescue_missions'").fetchone()
        if has_missions_tbl:
            conn.execute("""
                INSERT OR IGNORE INTO rescue_missions (
                    mission_id, team_id, team_name, scenario_id, victim_id,
                    destination_latitude, destination_longitude, destination_altitude_m,
                    destination_label, priority, instruction, status, device_id,
                    created_at, last_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ASSIGNED', ?, ?, ?)
            """, (
                effective_mission_id, team_id, team_id, scenario_id or "default", victim_id,
                destination_latitude, destination_longitude, destination_altitude_m,
                destination_label, priority, command_text or f"Proceed to rescue {destination_label or victim_id}",
                target_device_id, now, now
            ))

        # Automatically resolve recipient contact details from database registry
        contact = resolve_member_contact_info(member_id or "ALPHA-M001", team_id=team_id, db_path=db_path)
        phone_normalized = contact["phone_normalized"]
        phone_masked = contact["phone_masked"]

        # Channel evaluations:
        # SMS: SENT by default via SMSGate gateway
        sms_status = "SENT"

        conn.execute("""
            INSERT OR REPLACE INTO rescue_commands (
                command_id, mission_id, scenario_id, team_id, member_id, victim_id,
                destination_latitude, destination_longitude, destination_altitude_m,
                destination_label, latitude, longitude, altitude_m, location_label,
                priority, command_type, command_text, target_device_id,
                location_source, status, watch_delivery_status, created_at,
                phone_number, phone_number_masked, sms_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ASSIGNED', ?, ?, ?, ?, ?)
        """, (
            command_id, effective_mission_id, scenario_id, team_id, member_id, victim_id,
            destination_latitude, destination_longitude, destination_altitude_m,
            destination_label, destination_latitude, destination_longitude, destination_altitude_m, destination_label,
            priority, command_type, command_text, target_device_id,
            location_source, watch_delivery_status, now,
            phone_normalized, phone_masked, sms_status
        ))

        # Automatically create or update linked notification record from the EXACT SAME rescue command event
        conn.execute("""
            INSERT OR REPLACE INTO notification_center (
                id, alert_id, type, title, message, distance_m, distance_label,
                priority, status, watch_delivery_status, watch_ack_status,
                team_id, member_id, victim_id, timestamp, last_updated_at,
                rescue_command_id, mission_id, phone_number, phone_number_masked,
                sms_status, sms_error,
                sps, latitude, longitude, required_action
            ) VALUES (?, ?, 'RESCUE_COMMAND', ?, ?, 62.0, '62 m',
                      ?, 'ACTIVE', ?, 'PENDING',
                      ?, ?, ?, ?, ?,
                      ?, ?, ?, ?,
                      ?, NULL,
                      88.5, ?, ?, ?)
        """, (
            f"NOTIF-{command_id}", f"ALT-{command_id}",
            f"🚨 RESCUE MISSION: {destination_label or victim_id or 'Survivor'}",
            command_text or f"Proceed to rescue {destination_label or victim_id or 'Survivor'}",
            priority, watch_delivery_status,
            team_id, member_id, victim_id, now, now,
            command_id, effective_mission_id, phone_normalized, phone_masked,
            sms_status,
            destination_latitude, destination_longitude,
            command_text or f"Proceed to rescue {destination_label or victim_id or 'Survivor'}"
        ))

        row = conn.execute("SELECT * FROM rescue_commands WHERE command_id = ?", (command_id,)).fetchone()
        return dict(row) if row else {}


def list_rescue_commands(
    team_id: Optional[str] = None,
    member_id: Optional[str] = None,
    target_device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    db_path: Optional[str] = None,
) -> List[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        query = "SELECT * FROM rescue_commands WHERE 1=1"
        params = []
        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if member_id:
            query += " AND member_id = ?"
            params.append(member_id)
        if target_device_id:
            query += " AND target_device_id = ?"
            params.append(target_device_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_rescue_command(command_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        row = conn.execute("SELECT * FROM rescue_commands WHERE command_id = ?", (command_id,)).fetchone()
        return dict(row) if row else None


def update_rescue_command_status(
    command_id: str,
    status: str,
    delivery_error: Optional[str] = None,
    watch_delivery_status: Optional[str] = None,
    acceptance_source: Optional[str] = None,
    accepted_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        row = conn.execute("SELECT * FROM rescue_commands WHERE command_id = ?", (command_id,)).fetchone()
        if not row:
            return None
        curr = dict(row)
        curr_status = curr.get("status")

        # Stage 7 Lifecycle Hardening:
        # 1. Terminal states cannot be reverted unless explicitly setting another terminal state
        if curr_status in ("COMPLETED", "RESCUED", "CANCELLED"):
            if status not in ("COMPLETED", "RESCUED", "CANCELLED"):
                return curr
        # 2. ARRIVED cannot be reverted backwards to earlier lifecycle states
        if curr_status == "ARRIVED" and status in (
            "ASSIGNED", "PENDING", "SENT_TO_BRIDGE", "PHONE_NOTIFICATION_POSTED",
            "DELIVERED", "ACCEPTED", "USER_ACCEPTED", "EN_ROUTE"
        ):
            return curr

        now = _now()
        updates = ["status = ?"]
        params = [status]
        if status == "SENT_TO_BRIDGE":
            if not curr.get("bridge_sent_at"):
                updates.append("bridge_sent_at = ?")
                params.append(now)
            if not watch_delivery_status:
                updates.append("watch_delivery_status = ?")
                params.append("WATCH_DELIVERY_UNCONFIRMED")
        elif status == "PHONE_NOTIFICATION_POSTED":
            if not curr.get("phone_notification_posted_at"):
                updates.append("phone_notification_posted_at = ?")
                params.append(now)
            updates.append("watch_delivery_status = ?")
            params.append(watch_delivery_status or "WATCH_DELIVERY_UNCONFIRMED")
        elif status in ["DELIVERED", "ACCEPTED", "COMMAND_SENT", "USER_ACCEPTED"]:
            if not curr.get("delivered_at"):
                updates.append("delivered_at = ?")
                params.append(now)
            if not watch_delivery_status:
                updates.append("watch_delivery_status = ?")
                params.append("WATCH_DELIVERY_CONFIRMED")
        elif status in ["ACKNOWLEDGED", "WATCH_ACKNOWLEDGED"]:
            if not curr.get("acknowledged_at"):
                updates.append("acknowledged_at = ?")
                params.append(now)
            if not watch_delivery_status:
                updates.append("watch_delivery_status = ?")
                params.append("WATCH_ACKNOWLEDGED")
        elif status in ["COMPLETED", "RESCUED", "ARRIVED"]:
            if not curr.get("completed_at"):
                updates.append("completed_at = ?")
                params.append(now)
            if status == "ARRIVED" and not curr.get("arrived_at"):
                updates.append("arrived_at = ?")
                params.append(now)
        if watch_delivery_status and status not in ["SENT_TO_BRIDGE", "PHONE_NOTIFICATION_POSTED", "COMMAND_SENT", "WATCH_ACKNOWLEDGED"]:
            updates.append("watch_delivery_status = ?")
            params.append(watch_delivery_status)
        if delivery_error:
            updates.append("delivery_error = ?")
            params.append(delivery_error)
        if acceptance_source is not None:
            updates.append("acceptance_source = ?")
            params.append(acceptance_source)
        if accepted_at is not None:
            updates.append("accepted_at = ?")
            params.append(accepted_at)
        elif status in ("ACCEPTED", "USER_ACCEPTED"):
            updates.append("accepted_at = COALESCE(accepted_at, ?)")
            params.append(now)

        params.append(command_id)
        conn.execute(f"UPDATE rescue_commands SET {', '.join(updates)} WHERE command_id = ?", params)
        row = conn.execute("SELECT * FROM rescue_commands WHERE command_id = ?", (command_id,)).fetchone()
        return dict(row) if row else None


def get_rescue_command_or_job(
    identifier: str,
    db_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Looks up a rescue command or work assignment by ID.
    Returns ('RESCUE_COMMAND', cmd_dict) or ('JOB_ASSIGNMENT', job_dict) or (None, None).
    """
    if not identifier:
        return None, None
    clean_id = identifier.strip()
    # Check rescue_commands table
    cmd = get_rescue_command(clean_id, db_path=db_path)
    if cmd:
        return "RESCUE_COMMAND", cmd
    # Check if prefixed with NOTIF- or ALT-
    if clean_id.startswith("NOTIF-"):
        cmd = get_rescue_command(clean_id[6:], db_path=db_path)
        if cmd:
            return "RESCUE_COMMAND", cmd
    elif clean_id.startswith("ALT-"):
        cmd = get_rescue_command(clean_id[4:], db_path=db_path)
        if cmd:
            return "RESCUE_COMMAND", cmd

    # Check job_assignments table
    job = get_job_assignment(clean_id, db_path=db_path)
    if job:
        return "JOB_ASSIGNMENT", job
    if clean_id.startswith("NOTIF-"):
        job = get_job_assignment(clean_id[6:], db_path=db_path)
        if job:
            return "JOB_ASSIGNMENT", job

    return None, None


def update_rescue_command_navigation(
    command_id: str,
    navigation_status: Optional[str] = None,
    target_bearing_deg: Optional[float] = None,
    direction_delta_deg: Optional[float] = None,
    heading_difference_deg: Optional[float] = None,
    distance_to_target_m: Optional[float] = None,
    distance_trend: Optional[str] = None,
    direction_guidance: Optional[str] = None,
    direction_alert_last_sent_at: Optional[str] = None,
    arrived_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        updates = []
        params = []
        if navigation_status is not None:
            updates.append("navigation_status = ?")
            params.append(navigation_status)
        if target_bearing_deg is not None:
            updates.append("target_bearing_deg = ?")
            params.append(target_bearing_deg)
        if direction_delta_deg is not None:
            updates.append("direction_delta_deg = ?")
            params.append(direction_delta_deg)
        if heading_difference_deg is not None:
            updates.append("heading_difference_deg = ?")
            params.append(heading_difference_deg)
        if distance_to_target_m is not None:
            updates.append("distance_to_target_m = ?")
            params.append(distance_to_target_m)
        if distance_trend is not None:
            updates.append("distance_trend = ?")
            params.append(distance_trend)
        if direction_guidance is not None:
            updates.append("direction_guidance = ?")
            params.append(direction_guidance)
        if direction_alert_last_sent_at is not None:
            updates.append("direction_alert_last_sent_at = ?")
            params.append(direction_alert_last_sent_at)
        if arrived_at is not None:
            updates.append("arrived_at = ?")
            params.append(arrived_at)
        if not updates:
            row = conn.execute("SELECT * FROM rescue_commands WHERE command_id = ?", (command_id,)).fetchone()
            return dict(row) if row else None
        params.append(command_id)
        conn.execute(f"UPDATE rescue_commands SET {', '.join(updates)} WHERE command_id = ?", params)
        row = conn.execute("SELECT * FROM rescue_commands WHERE command_id = ?", (command_id,)).fetchone()
        return dict(row) if row else None


def get_active_command_for_member(member_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    """Retrieves the most recent active or assigned rescue command for a specific team member."""
    cmds = list_rescue_commands(member_id=member_id, db_path=db_path)
    for c in cmds:
        if c.get("status") not in ("COMPLETED", "RESCUED", "CANCELLED"):
            return c
    return None


def get_active_wearable_commands(db_path: Optional[str] = None) -> list[dict]:
    """Retrieves all active or non-terminal rescue commands from the database."""
    return list_rescue_commands(db_path=db_path)


def register_or_update_bridge_session(
    session_id: str,
    team_id: str,
    device_name: str = "Android Companion Bridge",
    member_id: Optional[str] = None,
    bluetooth_state: str = "ENABLED",
    watch_connected: bool = False,
    watch_device_id: Optional[str] = None,
    watch_mac: Optional[str] = None,
    watch_model: Optional[str] = None,
    gps_available: bool = True,
    location_source: str = "PHONE_GPS",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    altitude_m: Optional[float] = None,
    accuracy_m: Optional[float] = None,
    speed_mps: Optional[float] = None,
    heading_deg: Optional[float] = None,
    gps_timestamp: Optional[str] = None,
    status: str = "ONLINE",
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        now = _now()
        effective_gps_time = gps_timestamp or (now if latitude is not None and longitude is not None else None)
        conn.execute("""
            INSERT OR REPLACE INTO bridge_sessions (
                session_id, team_id, device_name, member_id, bluetooth_state,
                watch_connected, watch_device_id, watch_mac, watch_model,
                gps_available, location_source, latitude, longitude, altitude_m,
                accuracy_m, speed_mps, heading_deg, gps_timestamp,
                status, notes, last_heartbeat
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, team_id, device_name, member_id, bluetooth_state,
            int(watch_connected), watch_device_id, watch_mac, watch_model,
            int(gps_available), location_source, latitude, longitude, altitude_m,
            accuracy_m, speed_mps, heading_deg, effective_gps_time,
            status, notes, now
        ))
        row = conn.execute("SELECT * FROM bridge_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else {}


def list_bridge_sessions(team_id: Optional[str] = None, db_path: Optional[str] = None) -> List[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        if team_id:
            rows = conn.execute("SELECT * FROM bridge_sessions WHERE team_id = ? ORDER BY last_heartbeat DESC", (team_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM bridge_sessions ORDER BY last_heartbeat DESC").fetchall()
        return [dict(r) for r in rows]


def log_wearable_telemetry(
    device_id: str,
    latitude: float,
    longitude: float,
    altitude_m: Optional[float] = None,
    accuracy_m: Optional[float] = None,
    speed_mps: Optional[float] = None,
    heading_deg: Optional[float] = None,
    battery_pct: Optional[float] = None,
    heart_rate_bpm: Optional[float] = None,
    step_count: Optional[int] = None,
    team_id: Optional[str] = None,
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> str:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        now = _now()
        cursor = conn.execute("""
            INSERT INTO wearable_telemetry (
                device_id, team_id, session_id, latitude, longitude, altitude_m,
                accuracy_m, speed_mps, heading_deg, battery_pct, heart_rate_bpm, step_count, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device_id, team_id, session_id, latitude, longitude, altitude_m,
            accuracy_m, speed_mps, heading_deg, battery_pct, heart_rate_bpm, step_count, now
        ))
        return str(cursor.lastrowid)


def get_latest_team_wearable_location(team_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        row = conn.execute(
            "SELECT * FROM wearable_telemetry WHERE team_id = ? ORDER BY id DESC LIMIT 1",
            (team_id,),
        ).fetchone()
        return dict(row) if row else None


def is_inbound_sms_processed(message_id: str, db_path: Optional[str] = None) -> bool:
    """Check if an inbound SMS message ID has already been recorded/processed."""
    if not message_id:
        return False
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        row = conn.execute("SELECT 1 FROM processed_inbound_sms WHERE message_id = ?", (str(message_id),)).fetchone()
        return bool(row)


def record_processed_inbound_sms(
    message_id: str,
    sender: Optional[str] = None,
    content: Optional[str] = None,
    parsed_command_id: Optional[str] = None,
    status: str = "PROCESSED",
    db_path: Optional[str] = None,
) -> None:
    """Record processed inbound SMS message ID to prevent duplicate processing across polls."""
    if not message_id:
        return
    now = _now()
    with _connect(db_path) as conn:
        _ensure_wearable_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO processed_inbound_sms (
                message_id, sender, content, parsed_command_id, processed_at, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(message_id), sender, content, parsed_command_id, now, status),
        )


def log_flood_risk_assessment(
    session_id: str,
    assessment_id: str,
    water_depth_m: float,
    measured_distance_m: float,
    rise_rate_mps: float,
    estimated_pressure_kpa: float,
    rainfall_intensity_mmh: float,
    risk_score: float,
    risk_level: str,
    warning_issued: bool = False,
    evacuation_recommended: bool = False,
    time_to_inundation_minutes: Optional[float] = None,
    reading_quality: str = "VALID",
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Logs a calculated flood risk assessment record into SQLite."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO flood_risk_assessments (
                session_id, assessment_id, water_depth_m, measured_distance_m,
                rise_rate_mps, estimated_pressure_kpa, rainfall_intensity_mmh,
                risk_score, risk_level, warning_issued, evacuation_recommended,
                time_to_inundation_minutes, reading_quality, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                assessment_id,
                float(water_depth_m),
                float(measured_distance_m),
                float(rise_rate_mps),
                float(estimated_pressure_kpa),
                float(rainfall_intensity_mmh),
                float(risk_score),
                str(risk_level),
                int(bool(warning_issued)),
                int(bool(evacuation_recommended)),
                float(time_to_inundation_minutes) if time_to_inundation_minutes is not None else None,
                str(reading_quality),
                timestamp or _now(),
            ),
        )


def get_latest_flood_risk_assessments(limit: int = 20, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recent flood risk assessments ordered by timestamp descending."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM flood_risk_assessments ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def log_evacuation_recommendation(
    recommendation_id: str,
    zone_id: str,
    zone_name: str,
    assembly_point_id: str,
    assembly_point_name: str,
    urgency: str,
    route_confidence: str,
    transit_minutes: float,
    safety_margin_minutes: Optional[float] = None,
    avoided_hazards: Optional[List[str]] = None,
    instructions: Optional[List[str]] = None,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Logs an evacuation route recommendation into SQLite."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO evacuation_recommendations (
                recommendation_id, zone_id, zone_name, assembly_point_id,
                assembly_point_name, urgency, route_confidence, transit_minutes,
                safety_margin_minutes, avoided_hazards_json, instructions_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recommendation_id,
                zone_id,
                zone_name,
                assembly_point_id,
                assembly_point_name,
                urgency,
                route_confidence,
                float(transit_minutes),
                float(safety_margin_minutes) if safety_margin_minutes is not None else None,
                json.dumps(avoided_hazards or []),
                json.dumps(instructions or []),
                timestamp or _now(),
            ),
        )


def get_latest_evacuation_recommendations(limit: int = 10, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recent evacuation recommendations ordered by timestamp descending."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM evacuation_recommendations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["avoided_hazards"] = json.loads(d.get("avoided_hazards_json") or "[]")
            except Exception:
                d["avoided_hazards"] = []
            try:
                d["instructions"] = json.loads(d.get("instructions_json") or "[]")
            except Exception:
                d["instructions"] = []
            result.append(d)
        return result


# --------------------------------------------------------------------------- #
# Multi-Channel Emergency Communication Delivery Ledger
# --------------------------------------------------------------------------- #

def log_communication_delivery(delivery: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Logs an emergency communication delivery record into SQLite."""
    now_ts = _now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT OR REPLACE INTO communication_delivery (
                message_id, alert_id, rescue_command_id, mission_id,
                channel, recipient, recipient_masked, priority, status,
                retry_count, max_retries, provider_message_id, idempotency_key,
                error, payload, compact_payload, created_at, updated_at,
                dispatched_at, delivered_at, acknowledged_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                delivery.get("message_id"),
                delivery.get("alert_id"),
                delivery.get("rescue_command_id"),
                delivery.get("mission_id"),
                delivery.get("channel", "SMS_GATEWAY"),
                delivery.get("recipient", "Unknown"),
                delivery.get("recipient_masked", "Unknown"),
                delivery.get("priority", "HIGH"),
                delivery.get("status", "QUEUED"),
                int(delivery.get("retry_count", 0)),
                int(delivery.get("max_retries", 3)),
                delivery.get("provider_message_id"),
                delivery.get("idempotency_key", f"IDEM-{uuid.uuid4().hex[:12]}"),
                delivery.get("last_error") or delivery.get("error"),
                delivery.get("payload", ""),
                delivery.get("compact_payload"),
                delivery.get("created_at") or now_ts,
                now_ts,
                delivery.get("dispatched_at"),
                delivery.get("delivered_at"),
                delivery.get("acknowledged_at"),
                delivery.get("expires_at"),
            ),
        )
        return cur.lastrowid if cur.lastrowid is not None else 0


def get_communication_delivery(message_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a communication delivery record by message_id."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM communication_delivery WHERE message_id = ?", (message_id,)).fetchone()
        return dict(row) if row else None


def get_communication_delivery_by_idempotency(idempotency_key: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves an existing communication delivery record by idempotency_key."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM communication_delivery WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        return dict(row) if row else None


def update_communication_delivery_status(
    message_id: str,
    status: str,
    error: Optional[str] = None,
    provider_message_id: Optional[str] = None,
    dispatched_at: Optional[str] = None,
    delivered_at: Optional[str] = None,
    acknowledged_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """Updates status and timestamp attributes for an existing communication delivery record."""
    now_ts = _now()
    with _connect(db_path) as conn:
        updates = ["status = ?", "updated_at = ?"]
        params: List[Any] = [status, now_ts]

        if error is not None:
            updates.append("error = ?")
            params.append(error)
        if provider_message_id is not None:
            updates.append("provider_message_id = ?")
            params.append(provider_message_id)
        if dispatched_at is not None:
            updates.append("dispatched_at = ?")
            params.append(dispatched_at)
        if delivered_at is not None:
            updates.append("delivered_at = ?")
            params.append(delivered_at)
        if acknowledged_at is not None:
            updates.append("acknowledged_at = ?")
            params.append(acknowledged_at)

        params.append(message_id)
        cur = conn.execute(
            f"UPDATE communication_delivery SET {', '.join(updates)} WHERE message_id = ?",
            params,
        )
        return cur.rowcount > 0


def list_communication_deliveries(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recent communication delivery ledger entries ordered by id descending."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM communication_delivery ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    # quick self-test / demo when run directly: python db.py
    init_db()
    print(f"Initialized schema at {DEFAULT_DB_PATH}")
    print("Sessions logged so far:")
    for s in list_sessions():
        print(" ", s)
