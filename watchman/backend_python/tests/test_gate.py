# tests/test_gate.py
def test_gate_lookup_student(client):
    response = client.get("/api/gate/lookup-student/22CS101")
    assert response.status_code == 200
    data = response.json()
    assert data["roll_number"] == "22CS101" or data.get("rollNumber") == "22CS101"


def test_gate_stats(client):
    response = client.get("/api/gate/stats")
    assert response.status_code == 200
    data = response.json()
    assert "totalOnCampus" in data
    assert "entriesToday" in data
    assert "activeVisitors" in data
