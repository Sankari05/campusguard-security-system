"""
test_api_edge_cases.py
------------------------
Additional edge-case coverage for backend/api.py, complementing the
existing tests/test_api.py smoke tests. Focuses on:

  * error responses (unknown scenario, malformed advance request)
  * response schema/content checks beyond status codes
  * scenario switching / restart behavior
  * idempotency and repeated-call behavior
  * /scenarios listing endpoint
  * /health liveness contract
"""

import pytest


class TestHealthEndpoint:
    def test_health_returns_ok_and_timestamp(self, api_client):
        r = api_client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "time" in body and body["time"]


class TestScenarioListingAndErrors:
    def test_scenarios_endpoint_lists_available_scenarios(self, api_client):
        r = api_client.get("/scenarios")
        assert r.status_code == 200
        scenarios = r.json()["scenarios"]
        assert isinstance(scenarios, list)
        assert len(scenarios) >= 1
        ids = {s["scenario_id"] for s in scenarios}
        assert "himalaya_avalanche" in ids

    def test_start_unknown_scenario_returns_404(self, api_client):
        r = api_client.post("/scenario/start", json={"scenario": "does_not_exist"})
        assert r.status_code == 404

    def test_advance_with_zero_steps_returns_400(self, started_client):
        r = started_client.post("/rescue-team/advance", json={"steps": 0})
        assert r.status_code == 400

    def test_advance_with_negative_steps_returns_400(self, started_client):
        r = started_client.post("/rescue-team/advance", json={"steps": -3})
        assert r.status_code == 400

    def test_advance_before_start_returns_409(self, api_client):
        r = api_client.post("/rescue-team/advance", json={"steps": 1})
        assert r.status_code == 409

    def test_export_unknown_session_returns_404(self, api_client):
        r = api_client.get("/sessions/nonexistent-session-id/export.csv")
        assert r.status_code == 404


class TestScenarioStartVariants:
    def test_start_with_defaults_uses_himalaya_scenario(self, api_client):
        r = api_client.post("/scenario/start", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["scenario_id"] == "himalaya_avalanche"
        assert body["victim_count"] == 4

    def test_restarting_scenario_resets_cycle_count(self, api_client):
        api_client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        for _ in range(3):
            api_client.get("/victims")
        r = api_client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        assert r.json()["cycle"] == 0

    def test_two_runs_with_same_seed_produce_same_first_cycle_readings(self, api_client):
        api_client.post("/scenario/start", json={"seed": 99, "enable_degradation": False})
        first_run = api_client.get("/victims").json()

        api_client.post("/scenario/reset")
        api_client.post("/scenario/start", json={"seed": 99, "enable_degradation": False})
        second_run = api_client.get("/victims").json()

        first_values = {
            v["victim_id"]: {k: s["value"] for k, s in v["sensors"].items()}
            for v in first_run["victims"]
        }
        second_values = {
            v["victim_id"]: {k: s["value"] for k, s in v["sensors"].items()}
            for v in second_run["victims"]
        }
        assert first_values == second_values


class TestVictimsAndQueueResponseShape:
    def test_victims_payload_has_expected_fields_per_victim(self, started_client):
        r = started_client.get("/victims")
        body = r.json()
        for v in body["victims"]:
            assert set(["victim_id", "location", "sensors", "sensor_node_online", "fusion"]).issubset(v.keys())
            loc = v["location"]
            assert set(["latitude", "longitude", "altitude_m"]).issubset(loc.keys())
            fusion = v["fusion"]
            assert set(
                ["confidence_pct", "triage_class", "sps", "hazard_multiplier", "tapping_detected"]
            ).issubset(fusion.keys())

    def test_queue_ranks_start_at_one_and_are_contiguous(self, started_client):
        for _ in range(2):
            started_client.get("/victims")
        r = started_client.get("/queue")
        ranks = [item["rank"] for item in r.json()["queue"]]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_queue_triage_classes_are_valid_enum_values(self, started_client):
        started_client.get("/victims")
        r = started_client.get("/queue")
        valid = {"HIGH", "MEDIUM", "LOW", "NO_VITAL_SIGNS", "SAFE"}
        for item in r.json()["queue"]:
            assert item["triage_class"] in valid

    def test_queue_reflects_doctrine_ordering_end_to_end(self, started_client):
        for _ in range(3):
            started_client.get("/victims")
        r = started_client.get("/queue")
        classes = [item["triage_class"] for item in r.json()["queue"]]
        order_map = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NO_VITAL_SIGNS": 3, "SAFE": 4}
        numeric = [order_map[c] for c in classes]
        assert numeric == sorted(numeric)


class TestRescueTeamStatusEndpoint:
    def test_rescue_team_status_before_any_advance_has_no_arrivals(self, started_client):
        started_client.get("/victims")
        r = started_client.get("/rescue-team/status")
        assert r.status_code == 200
        assert r.json()["dispatch_sim"]["reached"] == []

    def test_repeated_status_calls_do_not_duplicate_team_assignments(self, started_client):
        started_client.get("/victims")
        r1 = started_client.get("/rescue-team/status")
        r2 = started_client.get("/rescue-team/status")
        assigned_1 = {t["team_id"]: t["assigned_victim_id"] for t in r1.json()["teams"]}
        assigned_2 = {t["team_id"]: t["assigned_victim_id"] for t in r2.json()["teams"]}
        assert assigned_1 == assigned_2
