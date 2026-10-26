"""
test_db.py
-----------
Tests for backend/db.py's SQLite logging layer, exercised both directly
(unit tests against a throwaway db file) and end-to-end through the REST
API (scenario run -> detection cycles + rescue events logged -> CSV export).

Run with:
    python -m unittest tests/test_db.py -v
"""

import csv
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db
from fastapi.testclient import TestClient
from api import app, state


class TestDbUnit(unittest.TestCase):
    """Direct tests against db.py using a temporary SQLite file."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.init_db(self.db_path)

    def tearDown(self):
        os.remove(self.db_path)

    def test_create_session_and_list(self):
        db.create_session(
            session_id="sess-1", seed=42, enable_degradation=True,
            victim_count=4, db_path=self.db_path,
        )
        sessions = db.list_sessions(db_path=self.db_path)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "sess-1")
        self.assertEqual(sessions[0]["seed"], 42)
        self.assertEqual(sessions[0]["victim_count"], 4)

    def test_log_rescue_status_event_and_export(self):
        db.create_session(
            session_id="sess-2", seed=None, enable_degradation=False,
            victim_count=4, db_path=self.db_path,
        )
        db.log_rescue_status_event(
            session_id="sess-2",
            event_type="team_dispatched",
            team_id="ALPHA",
            victim_id="V2",
            availability="en_route",
            eta_minutes=12.5,
            db_path=self.db_path,
        )
        db.log_rescue_status_event(
            session_id="sess-2",
            event_type="victim_reached",
            team_id="RESCUE-1",
            victim_id="V2",
            arrival_order=1,
            travel_seconds=45.0,
            db_path=self.db_path,
        )

        counts = db.session_counts("sess-2", db_path=self.db_path)
        self.assertEqual(counts["rescue_status_events"], 2)
        self.assertEqual(counts["sensor_readings"], 0)
        self.assertEqual(counts["detection_results"], 0)

        csv_text = db.export_session_csv("sess-2", db_path=self.db_path)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["record_type"], "rescue_status_event")
        event_types = {r["event_type"] for r in rows}
        self.assertEqual(event_types, {"team_dispatched", "victim_reached"})

    def test_export_to_file(self):
        db.create_session(
            session_id="sess-3", seed=1, enable_degradation=False,
            victim_count=4, db_path=self.db_path,
        )
        db.log_rescue_status_event(
            session_id="sess-3", event_type="victim_reached", victim_id="V1",
            db_path=self.db_path,
        )
        out_path = self.db_path + ".csv"
        try:
            returned_path = db.export_session_csv_file("sess-3", out_path, db_path=self.db_path)
            self.assertEqual(returned_path, out_path)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path) as f:
                content = f.read()
            self.assertIn("record_type", content)
            self.assertIn("V1", content)
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)


class TestDbViaApi(unittest.TestCase):
    """End-to-end: run a scenario through the API and check what got logged."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_detection_cycles_and_rescue_events_logged_and_exportable(self):
        r = self.client.post("/scenario/start", json={"seed": 3, "enable_degradation": False})
        self.assertEqual(r.status_code, 200)
        session_id = state.session_id
        self.assertIsNotNone(session_id)

        # A few /victims + /queue calls => several logged detection cycles.
        for _ in range(3):
            self.assertEqual(self.client.get("/victims").status_code, 200)
        self.assertEqual(self.client.get("/queue").status_code, 200)

        # Rescue-team status triggers auto-dispatch logging; advance the
        # dispatch simulation a bit to generate "victim_reached" events too.
        self.assertEqual(self.client.get("/rescue-team/status").status_code, 200)
        for _ in range(50):
            r = self.client.post("/rescue-team/advance", json={"seconds": 30, "steps": 1})
            self.assertEqual(r.status_code, 200)
            if r.json()["dispatch_sim"]["complete"]:
                break

        counts = db.session_counts(session_id)
        self.assertGreater(counts["sensor_readings"], 0)
        self.assertGreater(counts["detection_results"], 0)
        self.assertGreater(counts["rescue_status_events"], 0)

        # /sessions should list this run with matching counts.
        sessions_resp = self.client.get("/sessions")
        self.assertEqual(sessions_resp.status_code, 200)
        listed = {s["session_id"]: s for s in sessions_resp.json()["sessions"]}
        self.assertIn(session_id, listed)
        self.assertEqual(listed[session_id]["counts"], counts)

        # CSV export should be downloadable and contain rows for all three
        # record types, referencing all 4 Himalaya victims.
        export_resp = self.client.get(f"/sessions/{session_id}/export.csv")
        self.assertEqual(export_resp.status_code, 200)
        self.assertEqual(export_resp.headers["content-type"].split(";")[0], "text/csv")

        rows = list(csv.DictReader(io.StringIO(export_resp.text)))
        self.assertEqual(
            len(rows),
            counts["sensor_readings"] + counts["detection_results"]
            + counts["rescue_status_events"] + counts["network_alerts"],
        )
        record_types = {row["record_type"] for row in rows}
        expected_types = {"sensor_reading", "detection_result", "rescue_status_event"}
        if counts["network_alerts"] > 0:
            expected_types.add("network_alert")
        self.assertEqual(record_types, expected_types)

        victim_ids = {row["victim_id"] for row in rows if row["victim_id"]}
        self.assertTrue({"V1", "V2", "V3", "V4"}.issubset(victim_ids))

    def test_export_unknown_session_is_404(self):
        r = self.client.get("/sessions/not-a-real-session/export.csv")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
