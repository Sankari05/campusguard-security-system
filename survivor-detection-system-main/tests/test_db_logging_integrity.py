"""
test_db_logging_integrity.py
-------------------------------
Additional edge-case / integrity coverage for backend/db.py, complementing
the existing tests/test_db.py (session creation, event logging + CSV
export, full end-to-end API run). This file focuses on:

  * row-count integrity: every SensorReading / FusionResult passed to
    log_detection_cycle() produces exactly one DB row
  * data-type / value fidelity through the sqlite round trip
    (bool -> 0/1 -> back, enum -> .value string, floats preserved)
  * multiple cycles accumulate rather than overwrite
  * multiple independent sessions don't leak rows into each other
  * CSV export ordering is chronological and stable
  * re-running init_db() against an existing DB file is a safe no-op
    (schema migration idempotency)
"""

import csv
import io

import pytest

import db
from models import SensorType, GPSCoordinate
from fusion_engine import fuse_victim, TriageClass
from tests.conftest import make_reading


LOC = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)


class TestLogDetectionCycleRowCounts:
    def test_row_count_matches_readings_and_victim_count(self, tmp_db_path):
        db.create_session(
            session_id="s1", seed=1, enable_degradation=False,
            victim_count=2, db_path=tmp_db_path,
        )
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 80.0, victim_id="A"),
            make_reading(SensorType.THERMAL_IMAGING, 25.0, victim_id="A"),
            make_reading(SensorType.HEART_RATE_RADAR, 0.0, victim_id="B"),
        ]
        fusion_results = {
            "A": fuse_victim([r for r in readings if r.victim_id == "A"], victim_id="A"),
            "B": fuse_victim([r for r in readings if r.victim_id == "B"], victim_id="B"),
        }
        db.log_detection_cycle("s1", cycle=1, readings=readings,
                                fusion_results_by_victim=fusion_results, db_path=tmp_db_path)

        counts = db.session_counts("s1", db_path=tmp_db_path)
        assert counts["sensor_readings"] == 3
        assert counts["detection_results"] == 2

    def test_multiple_cycles_accumulate_rather_than_overwrite(self, tmp_db_path):
        db.create_session(
            session_id="s2", seed=None, enable_degradation=False,
            victim_count=1, db_path=tmp_db_path,
        )
        for cycle in range(1, 6):
            readings = [make_reading(SensorType.HEART_RATE_RADAR, 70.0, victim_id="A")]
            fusion_results = {"A": fuse_victim(readings, victim_id="A")}
            db.log_detection_cycle("s2", cycle=cycle, readings=readings,
                                    fusion_results_by_victim=fusion_results, db_path=tmp_db_path)
        counts = db.session_counts("s2", db_path=tmp_db_path)
        assert counts["sensor_readings"] == 5
        assert counts["detection_results"] == 5

    def test_empty_readings_and_empty_fusion_results_logs_nothing_and_does_not_error(self, tmp_db_path):
        db.create_session(
            session_id="s3", seed=None, enable_degradation=False,
            victim_count=0, db_path=tmp_db_path,
        )
        db.log_detection_cycle("s3", cycle=1, readings=[],
                                fusion_results_by_victim={}, db_path=tmp_db_path)
        counts = db.session_counts("s3", db_path=tmp_db_path)
        assert counts["sensor_readings"] == 0
        assert counts["detection_results"] == 0


class TestDataFidelityThroughRoundTrip:
    def test_boolean_and_enum_fields_round_trip_correctly(self, tmp_db_path):
        db.create_session(
            session_id="s4", seed=None, enable_degradation=False,
            victim_count=1, db_path=tmp_db_path,
        )
        # deliberately construct a HIGH/tapping result
        readings = [
            make_reading(SensorType.ACOUSTIC, 45.0, victim_id="TAP"),
            make_reading(SensorType.HEART_RATE_RADAR, 40.0, victim_id="TAP"),
        ]
        result = fuse_victim(readings, victim_id="TAP")
        assert result.tapping_detected is True  # sanity on the fixture itself

        db.log_detection_cycle("s4", cycle=1, readings=readings,
                                fusion_results_by_victim={"TAP": result}, db_path=tmp_db_path)

        csv_text = db.export_session_csv("s4", db_path=tmp_db_path)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        detection_rows = [r for r in rows if r["record_type"] == "detection_result"]
        assert len(detection_rows) == 1
        row = detection_rows[0]
        assert row["tapping_detected"] == "1"
        assert row["triage_class"] == result.triage_class.value
        assert row["triage_class"] in (TriageClass.HIGH.value,)

    def test_float_precision_preserved_within_tolerance(self, tmp_db_path):
        db.create_session(
            session_id="s5", seed=None, enable_degradation=False,
            victim_count=1, db_path=tmp_db_path,
        )
        readings = [make_reading(SensorType.HEART_RATE_RADAR, 73.456, victim_id="P")]
        result = fuse_victim(readings, victim_id="P")
        db.log_detection_cycle("s5", cycle=1, readings=readings,
                                fusion_results_by_victim={"P": result}, db_path=tmp_db_path)

        csv_text = db.export_session_csv("s5", db_path=tmp_db_path)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        sensor_row = next(r for r in rows if r["record_type"] == "sensor_reading")
        assert float(sensor_row["value"]) == pytest.approx(73.456, abs=1e-6)

    def test_contributing_sensors_serialized_as_comma_joined_string(self, tmp_db_path):
        db.create_session(
            session_id="s6", seed=None, enable_degradation=False,
            victim_count=1, db_path=tmp_db_path,
        )
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 80.0, victim_id="M"),
            make_reading(SensorType.THERMAL_IMAGING, 25.0, victim_id="M"),
        ]
        result = fuse_victim(readings, victim_id="M")
        db.log_detection_cycle("s6", cycle=1, readings=readings,
                                fusion_results_by_victim={"M": result}, db_path=tmp_db_path)
        csv_text = db.export_session_csv("s6", db_path=tmp_db_path)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        detection_row = next(r for r in rows if r["record_type"] == "detection_result")
        sensors = set(detection_row["contributing_sensors"].split(","))
        assert sensors == {SensorType.HEART_RATE_RADAR.value, SensorType.THERMAL_IMAGING.value}


class TestSessionIsolation:
    def test_rows_from_different_sessions_do_not_leak(self, tmp_db_path):
        db.create_session(session_id="iso-1", seed=1, enable_degradation=False,
                           victim_count=1, db_path=tmp_db_path)
        db.create_session(session_id="iso-2", seed=2, enable_degradation=False,
                           victim_count=1, db_path=tmp_db_path)

        readings_1 = [make_reading(SensorType.HEART_RATE_RADAR, 80.0, victim_id="A")]
        result_1 = fuse_victim(readings_1, victim_id="A")
        db.log_detection_cycle("iso-1", cycle=1, readings=readings_1,
                                fusion_results_by_victim={"A": result_1}, db_path=tmp_db_path)

        counts_1 = db.session_counts("iso-1", db_path=tmp_db_path)
        counts_2 = db.session_counts("iso-2", db_path=tmp_db_path)
        assert counts_1["sensor_readings"] == 1
        assert counts_2["sensor_readings"] == 0

    def test_list_sessions_returns_all_created_sessions(self, tmp_db_path):
        db.create_session(session_id="list-1", seed=None, enable_degradation=False,
                           victim_count=1, db_path=tmp_db_path)
        db.create_session(session_id="list-2", seed=None, enable_degradation=False,
                           victim_count=1, db_path=tmp_db_path)
        sessions = db.list_sessions(db_path=tmp_db_path)
        ids = {s["session_id"] for s in sessions}
        assert {"list-1", "list-2"}.issubset(ids)


class TestCsvExportOrdering:
    def test_export_is_chronologically_ordered(self, tmp_db_path):
        db.create_session(session_id="chrono", seed=None, enable_degradation=False,
                           victim_count=1, db_path=tmp_db_path)
        for cycle in range(1, 4):
            readings = [make_reading(SensorType.HEART_RATE_RADAR, 70.0, victim_id="A")]
            result = fuse_victim(readings, victim_id="A")
            db.log_detection_cycle("chrono", cycle=cycle, readings=readings,
                                    fusion_results_by_victim={"A": result}, db_path=tmp_db_path)
        csv_text = db.export_session_csv("chrono", db_path=tmp_db_path)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        timestamps = [r["timestamp"] for r in rows]
        assert timestamps == sorted(timestamps)


class TestSchemaMigrationIdempotency:
    def test_init_db_twice_on_same_file_is_safe(self, tmp_db_path):
        # tmp_db_path already had init_db() called once by the fixture;
        # calling it again must not raise or duplicate/clobber schema.
        db.init_db(tmp_db_path)
        db.create_session(session_id="post-migration", seed=None,
                           enable_degradation=False, victim_count=1, db_path=tmp_db_path)
        sessions = db.list_sessions(db_path=tmp_db_path)
        assert any(s["session_id"] == "post-migration" for s in sessions)

    def test_create_session_with_or_replace_overwrites_same_id(self, tmp_db_path):
        db.create_session(session_id="dup", seed=1, enable_degradation=False,
                           victim_count=1, db_path=tmp_db_path)
        db.create_session(session_id="dup", seed=2, enable_degradation=True,
                           victim_count=4, db_path=tmp_db_path)
        sessions = {s["session_id"]: s for s in db.list_sessions(db_path=tmp_db_path)}
        assert sessions["dup"]["seed"] == 2
        assert sessions["dup"]["victim_count"] == 4
