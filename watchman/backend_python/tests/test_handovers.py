# tests/test_handovers.py
def test_current_handover(client):
    response = client.get("/api/handovers/current")
    assert response.status_code == 200
    data = response.json()
    assert data["hasActiveHandover"] is True
    assert "handover" in data


def test_unresolved_tasks(client):
    response = client.get("/api/handovers/unresolved-tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
