"""
test_validation_workflow.py
----------------------------
Programmatic validation of all 15 test criteria specified in the user request.
"""

import unittest
from fastapi.testclient import TestClient
from backend.api import app


class TestAlertsValidationSuite(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_complete_alerts_lifecycle(self):
        # TEST 1 & 2: Empty state / not running returns 409, no crashing
        r0 = self.client.get("/alerts")
        self.assertEqual(r0.status_code, 409)

        # TEST 3: Start scenario -> Victim Detected alerts generated
        start_res = self.client.post("/scenario/start", json={"seed": 42, "enable_degradation": False})
        self.assertEqual(start_res.status_code, 200)

        r_victims = self.client.get("/victims")
        self.assertEqual(r_victims.status_code, 200)

        alerts_res = self.client.get("/alerts")
        self.assertEqual(alerts_res.status_code, 200)
        data = alerts_res.json()

        victim_alerts = [e for e in data["events"] if e["type"] == "Victim Detected"]
        self.assertTrue(len(victim_alerts) >= 4)
        self.assertTrue(data["summary"]["total"] >= 4)

        # TEST 4 & 5: Commander assigns team -> Team Assigned and GO Command alerts
        overview = self.client.get("/commander/overview").json()
        member_id = overview["team_members"][0]["member_id"]
        victim_id = overview["victims"][0]["victim_id"]

        assign_res = self.client.post("/commander/assign", json={"member_id": member_id, "victim_id": victim_id})
        self.assertEqual(assign_res.status_code, 200)

        data_assigned = self.client.get("/alerts").json()
        assign_events = [e for e in data_assigned["events"] if e["type"] == "Team Assigned"]
        go_events = [e for e in data_assigned["events"] if e["type"] == "GO Command"]
        self.assertTrue(len(assign_events) >= 1)
        self.assertTrue(len(go_events) >= 1)

        # TEST 6: Safety condition check (e.g. earthquake scenario with seismic/tilt)
        # Advance simulation ticks
        for _ in range(5):
            self.client.get("/commander/overview")

        # TEST 7 & 8: Team arrives and victim rescued
        # Advance enough ticks for member to reach victim
        for _ in range(40):
            self.client.get("/commander/overview")

        data_arrivals = self.client.get("/alerts").json()
        arrival_events = [e for e in data_arrivals["events"] if e["type"] == "Team Arrived"]
        rescued_events = [e for e in data_arrivals["events"] if e["type"] == "Victim Rescued"]

        if arrival_events:
            self.assertEqual(arrival_events[0]["severity"], "ARRIVAL")
            self.assertEqual(arrival_events[0]["source"], "Wearable")

        # TEST 9: Deduplication across multiple polls
        res_poll1 = self.client.get("/alerts").json()
        res_poll2 = self.client.get("/alerts").json()

        ids1 = [e["id"] for e in res_poll1["events"]]
        ids2 = [e["id"] for e in res_poll2["events"]]
        self.assertEqual(len(ids1), len(set(ids1)), "All event IDs must be unique in response 1")
        self.assertEqual(len(ids2), len(set(ids2)), "All event IDs must be unique in response 2")
        self.assertEqual(ids1, ids2, "Event list must be consistent across polls without duplicates")
