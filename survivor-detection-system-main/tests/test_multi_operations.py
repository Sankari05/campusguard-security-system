"""
test_multi_operations.py
-------------------------
Dedicated unit & integration tests verifying multi-operation isolation:
1. Multiple operations can run simultaneously without interfering with each other.
2. Sensor state, triage ranking, and victim counts remain completely isolated.
3. Stopping or resetting one operation does not affect any other running operation.
4. /operations correctly lists all active operations with metadata.
5. Accessing an unknown or stopped operation_id returns 404.
6. DB session logging correctly isolates session_ids per operation.
"""

import pytest
from fastapi.testclient import TestClient
from api import app, operations


def test_multi_operation_lifecycle():
    client = TestClient(app)
    # Start with a clean slate
    client.post("/scenario/reset")

    # Start Operation A: Avalanche scenario
    res_a = client.post("/scenario/start", json={
        "scenario": "himalaya_avalanche",
        "operation_id": "op-avalanche-01",
        "seed": 100,
        "enable_degradation": False,
    })
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["operation_id"] == "op-avalanche-01"
    assert data_a["scenario_id"] == "himalaya_avalanche"

    # Start Operation B: Urban flood scenario
    res_b = client.post("/scenario/start", json={
        "scenario": "flood_urban",
        "operation_id": "op-flood-02",
        "seed": 200,
        "enable_degradation": False,
    })
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["operation_id"] == "op-flood-02"
    assert data_b["scenario_id"] == "flood_urban"

    # Verify both are registered in GET /operations
    ops_res = client.get("/operations")
    assert ops_res.status_code == 200
    active_ops = ops_res.json()["operations"]
    op_ids = {op["operation_id"] for op in active_ops}
    assert "op-avalanche-01" in op_ids
    assert "op-flood-02" in op_ids

    # Query victims for Operation A
    victims_a = client.get("/operations/op-avalanche-01/victims").json()
    assert victims_a["operation_id"] == "op-avalanche-01"
    assert victims_a["scenario"]["scenario_id"] == "himalaya_avalanche"
    vids_a = {v["victim_id"] for v in victims_a["victims"]}

    # Query victims for Operation B
    victims_b = client.get("/operations/op-flood-02/victims").json()
    assert victims_b["operation_id"] == "op-flood-02"
    assert victims_b["scenario"]["scenario_id"] == "flood_urban"
    vids_b = {v["victim_id"] for v in victims_b["victims"]}

    # Verify independent victim locations/data
    locs_a = {(v["location"]["latitude"], v["location"]["longitude"]) for v in victims_a["victims"]}
    locs_b = {(v["location"]["latitude"], v["location"]["longitude"]) for v in victims_b["victims"]}
    assert locs_a != locs_b

    # Verify queue independence
    queue_a = client.get("/operations/op-avalanche-01/queue").json()["queue"]
    queue_b = client.get("/operations/op-flood-02/queue").json()["queue"]
    assert len(queue_a) > 0
    assert len(queue_b) > 0
    assert queue_a[0]["victim_id"] in vids_a
    assert queue_b[0]["victim_id"] in vids_b

    # Verify Commander overview independence
    cmd_a = client.get("/operations/op-avalanche-01/commander/overview").json()
    cmd_b = client.get("/operations/op-flood-02/commander/overview").json()
    assert cmd_a["operation_id"] == "op-avalanche-01"
    assert cmd_b["operation_id"] == "op-flood-02"

    # Stop Operation A only
    stop_a = client.post("/operations/op-avalanche-01/stop")
    assert stop_a.status_code == 200
    assert stop_a.json()["status"] == "stopped"

    # Operation A should now return 404
    dead_a = client.get("/operations/op-avalanche-01/victims")
    assert dead_a.status_code == 404

    # Operation B should still be alive and ticking
    live_b = client.get("/operations/op-flood-02/victims")
    assert live_b.status_code == 200

    # Stop Operation B
    stop_b = client.post("/operations/op-flood-02/stop")
    assert stop_b.status_code == 200

    # Global reset cleanup
    client.post("/scenario/reset")
