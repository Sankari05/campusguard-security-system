"""
test_hardware_registry.py
-------------------------
Unit and integration tests for the Centralized Hardware Registry,
topology wiring definitions, and FastAPI hardware endpoints.
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import hardware_registry
from models import SensorType
from api import app

client = TestClient(app)


def test_hardware_inventory_coverage():
    """Verify all 18 sensor modalities are represented in the centralized inventory."""
    inventory = hardware_registry.get_hardware_inventory()
    assert len(inventory) >= 18

    # Check all SensorType values are mapped
    sensor_types_in_inventory = {item["sensor_type"] for item in inventory if item["sensor_type"] is not None}
    for st in SensorType:
        assert st.value in sensor_types_in_inventory, f"Missing {st.value} in hardware inventory"


def test_controllers_and_power_presence():
    """Verify controllers, communication, and power management units exist in inventory."""
    inventory = hardware_registry.get_hardware_inventory()
    categories = {item["category"] for item in inventory}

    assert "CONTROLLER" in categories
    assert "POWER" in categories
    assert "COMMUNICATION" in categories
    assert "SENSOR" in categories
    assert "CAMERA" in categories


def test_hardware_topology_connections():
    """Verify topology connects devices with valid virtual pin mappings and protocols."""
    topology = hardware_registry.get_hardware_topology()
    assert len(topology) >= 20

    for conn in topology:
        assert conn["source_id"]
        assert conn["target_id"]
        assert conn["protocol"]
        assert conn["pin_mapping"]
        assert conn["power_rail"]
        assert conn["data_line"]
        assert conn["is_virtual"] is True


def test_hardware_api_endpoints():
    """Verify GET /hardware/inventory, /hardware/topology, and /hardware/summary return 200 OK."""
    res_inv = client.get("/hardware/inventory")
    assert res_inv.status_code == 200
    data_inv = res_inv.json()
    assert data_inv["status"] == "success"
    assert data_inv["total_equipment"] >= 18
    assert len(data_inv["inventory"]) >= 18

    res_topo = client.get("/hardware/topology")
    assert res_topo.status_code == 200
    data_topo = res_topo.json()
    assert data_topo["status"] == "success"
    assert len(data_topo["topology"]) >= 20

    res_sum = client.get("/hardware/summary")
    assert res_sum.status_code == 200
    data_sum = res_sum.json()
    assert data_sum["status"] == "success"
    assert data_sum["total_equipment"] >= 18
    assert "categories" in data_sum

    res_dev = client.get("/hardware/inventory/DEV-RADAR-01")
    assert res_dev.status_code == 200
    assert res_dev.json()["device"]["device_id"] == "DEV-RADAR-01"


def test_hardware_device_not_found():
    """Verify 404 on nonexistent device ID."""
    res = client.get("/hardware/inventory/NONEXISTENT-DEV-999")
    assert res.status_code == 404
