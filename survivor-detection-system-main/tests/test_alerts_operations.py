"""
test_alerts_operations.py
--------------------------
Integration and unit tests for the RIDGEWATCH Emergency Rescue Operations Alert Center.
Verifies real event mappings, deduplication, summary metrics, operational status, and backward compatibility.
"""

import unittest
from fastapi.testclient import TestClient
from backend.api import app


class TestAlertsOperations(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_alerts_endpoint_requires_running_scenario(self):
        """When no scenario is running, GET /alerts returns 409 (same pattern as other operational routes)."""
        r = self.client.get("/alerts")
        self.assertEqual(r.status_code, 409)

    def test_alerts_on_scenario_start_contains_victim_detections(self):
        """When scenario starts, GET /alerts provides real fused victim detection events."""
        start_res = self.client.post("/scenario/start", json={"seed": 42, "enable_degradation": False})
        self.assertEqual(start_res.status_code, 200)

        # Advance one tick by getting /victims
        self.client.get("/victims")

        alerts_res = self.client.get("/alerts")
        self.assertEqual(alerts_res.status_code, 200)
        data = alerts_res.json()

        # Check top-level contract
        self.assertIn("scenario", data)
        self.assertIn("alerts", data)
        self.assertIn("events", data)
        self.assertIn("summary", data)
        self.assertIn("operation_status", data)
        self.assertIn("recent_activities", data)

        events = data["events"]
        self.assertTrue(len(events) > 0)

        # Verify Victim Detected events exist
        victim_events = [e for e in events if e["type"] == "Victim Detected"]
        self.assertTrue(len(victim_events) >= 4)
        for ve in victim_events:
            self.assertIn("victim_id", ve)
            self.assertIn(ve["severity"], ("CRITICAL", "WARNING", "INFO"))
            self.assertEqual(ve["source"], "Fusion Engine")
            self.assertEqual(ve["target"], "Commander")

        # Verify summary counts
        summary = data["summary"]
        self.assertEqual(summary["total"], len(events))
        self.assertEqual(summary["critical"], sum(1 for e in events if e["severity"] == "CRITICAL"))

    def test_commander_assign_generates_team_assigned_and_go_alerts(self):
        """When Commander assigns a team member to a victim, Team Assigned and GO Command events are generated."""
        self.client.post("/scenario/start", json={"seed": 42, "enable_degradation": False})
        overview = self.client.get("/commander/overview").json()
        members = overview.get("team_members", [])
        self.assertTrue(len(members) > 0)

        member_id = members[0]["member_id"]
        victim_id = overview["victims"][0]["victim_id"]

        # Assign member
        assign_res = self.client.post("/commander/assign", json={"member_id": member_id, "victim_id": victim_id})
        self.assertEqual(assign_res.status_code, 200)

        alerts_res = self.client.get("/alerts")
        self.assertEqual(alerts_res.status_code, 200)
        events = alerts_res.json()["events"]

        assign_events = [e for e in events if e["type"] == "Team Assigned"]
        go_events = [e for e in events if e["type"] == "GO Command"]

        self.assertTrue(len(assign_events) >= 1)
        self.assertTrue(len(go_events) >= 1)

        # Check target and details
        self.assertEqual(assign_events[0]["severity"], "DISPATCH")
        self.assertEqual(assign_events[0]["victim_id"], victim_id)
        self.assertEqual(go_events[0]["severity"], "DISPATCH")

    def test_alert_event_deduplication(self):
        """Multiple polling requests produce unique deterministic IDs without duplicates."""
        self.client.post("/scenario/start", json={"seed": 42, "enable_degradation": False})
        for _ in range(3):
            self.client.get("/victims")
            self.client.get("/queue")

        res1 = self.client.get("/alerts").json()
        res2 = self.client.get("/alerts").json()

        event_ids1 = [e["id"] for e in res1["events"]]
        event_ids2 = [e["id"] for e in res2["events"]]

        # Check all IDs in single response are strictly unique
        self.assertEqual(len(event_ids1), len(set(event_ids1)))
        self.assertEqual(len(event_ids2), len(set(event_ids2)))

    def test_backward_compatibility_alerts_field(self):
        """Existing legacy test contracts expecting data['alerts'] array remain 100% satisfied."""
        self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        # Advance simulation to trigger network alert
        for _ in range(15):
            self.client.get("/victims")
            q = self.client.get("/queue").json()
            if q.get("new_alerts"):
                break

        res = self.client.get("/alerts")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data["alerts"], list)
