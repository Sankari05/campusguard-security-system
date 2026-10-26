"""
test_rescue_dispatch.py
------------------------
End-to-end test of the rescue_dispatch.py simulation, driven entirely
through the REST API (POST /rescue-team/advance / GET /rescue-team/status),
for the 4 fixed Himalaya avalanche victims.

Verifies that:
  * the single-agent dispatch simulation reaches all 4 victims,
  * the arrival order matches the current /queue triage priority order,
  * each victim gets a "reached" status + timestamp once arrived,
  * timestamps are strictly increasing (the team moves forward in time).

Also prints the arrival order and timestamps for manual inspection.

Run with:
    python -m unittest tests/test_rescue_dispatch.py -v
"""

import sys
import os
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from api import app


class TestRescueDispatchFullSequence(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")
        r = self.client.post(
            "/scenario/start", json={"seed": 7, "enable_degradation": False}
        )
        self.assertEqual(r.status_code, 200)

        # Warm up the sensor history so every victim has fused readings
        # (and therefore a known location) before dispatch starts.
        for _ in range(3):
            r = self.client.get("/victims")
            self.assertEqual(r.status_code, 200)

    def test_full_dispatch_sequence_for_all_four_victims(self):
        # Snapshot the current triage priority order to compare against.
        queue_resp = self.client.get("/queue")
        self.assertEqual(queue_resp.status_code, 200)
        expected_order = [item["victim_id"] for item in queue_resp.json()["queue"]]
        self.assertEqual(len(expected_order), 4)

        arrivals = []
        # Step the simulation forward until every victim has been reached,
        # or bail out after a generous number of steps to avoid hanging.
        for _ in range(2000):
            r = self.client.post("/rescue-team/advance", json={"seconds": 30, "steps": 1})
            self.assertEqual(r.status_code, 200)
            body = r.json()
            arrivals.extend(body["arrivals"])
            if body["dispatch_sim"]["complete"]:
                break

        self.assertEqual(len(arrivals), 4, msg=f"arrivals so far: {arrivals}")

        arrival_order = [a["victim_id"] for a in arrivals]
        self.assertEqual(
            arrival_order,
            expected_order,
            msg="Dispatch agent should visit victims in /queue priority order",
        )

        # Arrival order field (1-indexed) should be sequential.
        self.assertEqual([a["order"] for a in arrivals], [1, 2, 3, 4])

        # Timestamps should be valid ISO-8601 and strictly increasing.
        timestamps = [datetime.fromisoformat(a["reached_at"]) for a in arrivals]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertTrue(all(t2 > t1 for t1, t2 in zip(timestamps, timestamps[1:])))

        # Final status endpoint should reflect all 4 victims as "reached".
        status_resp = self.client.get("/rescue-team/status")
        self.assertEqual(status_resp.status_code, 200)
        sim = status_resp.json()["dispatch_sim"]
        self.assertTrue(sim["complete"])
        self.assertEqual(len(sim["remaining"]), 0)
        for vid in expected_order:
            self.assertEqual(sim["victim_status"][vid]["status"], "reached")
            self.assertIsNotNone(sim["victim_status"][vid]["reached_at"])

        # Print the dispatch order + timestamps for manual inspection.
        print("\nRescue dispatch sequence (Himalaya avalanche scenario):")
        for a in arrivals:
            print(
                f"  #{a['order']}  victim={a['victim_id']:<4} "
                f"reached_at={a['reached_at']}  travel_seconds={a['travel_seconds']}"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
