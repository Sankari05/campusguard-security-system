"""
End-to-End Test Suite for Scenario-Based Staff Registration, Matching, and Commander Job Allocation.

Covers:
1. Case 1: Register Staff with Disaster Scenario
2. Case 2: Job Creation with Scenario
3. Case 3: Matching Scenario Staff Retrieval
4. Case 4: Successful Job Allocation
5. Case 5: Ineligible Assignment Rejection (Strict 400 Error)
6. Case 6: Multi-Scenario Staff Member & Multi-Hazard Handling
7. Case 7: Staff Job Processing, Status Updates & Commander Verification
8. Case 8: Newly Created Team Dynamic Integration with Scenario Matching
"""

import uuid
import pytest


def test_case_1_register_staff_with_disaster_scenario(api_client):
    """Case 1: Admin registers staff with specific disaster scenarios."""
    # 1. Register a staff member specifically trained in Flood Response
    res = api_client.post(
        "/admin/personnel/add",
        json={
            "full_name": "Major Ananya Roy",
            "role": "Flood Rescue Specialist",
            "phone": "+91 98765 11111",
            "email": "ananya.roy@sar.gov.in",
            "status": "Active",
            "badge_id": "FLD-007",
            "scenarios": ["flood", "cyclone", "tsunami"],
        },
    )
    assert res.status_code == 200
    person_id = res.json()["person_id"]
    assert person_id.startswith("P")

    # 2. Query individual personnel by ID
    get_res = api_client.get(f"/admin/personnel/{person_id}")
    assert get_res.status_code == 200
    person_data = get_res.json()["personnel"]
    assert person_data["person_id"] == person_id
    assert person_data["full_name"] == "Major Ananya Roy"
    assert "flood" in person_data["scenarios"]
    assert "cyclone" in person_data["scenarios"]
    assert "tsunami" in person_data["scenarios"]

    # 3. Query all personnel list
    list_res = api_client.get("/admin/personnel")
    assert list_res.status_code == 200
    p_in_list = next((p for p in list_res.json()["personnel"] if p["person_id"] == person_id), None)
    assert p_in_list is not None
    assert "flood" in p_in_list["scenarios"]

    # 4. Update scenarios via API endpoint
    patch_res = api_client.patch(
        f"/admin/personnel/{person_id}/scenarios",
        json={"scenarios": ["flood", "dam_failure", "urban_fire"]},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["updated"] is True

    # 5. Verify updated scenarios
    updated_person = api_client.get(f"/admin/personnel/{person_id}").json()["personnel"]
    assert "dam_failure" in updated_person["scenarios"]
    assert "urban_fire" in updated_person["scenarios"]


def test_case_2_job_creation_with_scenario(api_client):
    """Case 2: Commander creates a Job with disaster scenario and metadata."""
    job_payload = {
        "job_name": "Sector 4 Levee Breach Search & Evac",
        "scenario_id": "flood",
        "priority": "HIGH",
        "location": "North Basin Levee Marker 12",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "description": "Rapid water level rise; evacuate stranded civilians from rooftops.",
    }
    create_res = api_client.post("/commander/jobs/create", json=job_payload)
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["created"] is True
    job = data["job"]
    assert job["job_id"].startswith("JOB-")
    assert job["job_name"] == "Sector 4 Levee Breach Search & Evac"
    assert job["scenario_id"] == "flood"
    assert job["scenario_name"] == "Flood"
    assert job["priority"] == "HIGH"
    assert job["status"] == "OPEN"

    # Verify retrieval by job_id
    get_res = api_client.get(f"/commander/jobs/{job['job_id']}")
    assert get_res.status_code == 200
    assert get_res.json()["job"]["job_id"] == job["job_id"]

    # Verify listing filtered by scenario
    list_res = api_client.get("/commander/jobs?scenario_id=flood")
    assert list_res.status_code == 200
    assert any(j["job_id"] == job["job_id"] for j in list_res.json()["jobs"])


def test_case_3_matching_scenario_staff_retrieval(started_client):
    """Case 3: Dynamic scenario matching returns ONLY trained/matching staff for the job."""
    # Register 3 staff members:
    # 1. Flood Specialist
    res1 = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Commander Flood Guy", "role": "Flood Lead", "scenarios": ["flood", "dam_failure"]},
    )
    p1 = res1.json()["person_id"]

    # 2. Chemical Hazmat Specialist
    res2 = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Dr. Hazmat Pro", "role": "Hazmat Specialist", "scenarios": ["chemical_spill", "gas_leak"]},
    )
    p2 = res2.json()["person_id"]

    # 3. Inactive Flood Rescuer
    res3 = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Inactive Officer", "role": "Flood Backup", "status": "Inactive", "scenarios": ["flood"]},
    )
    p3 = res3.json()["person_id"]

    # Create a Chemical Spill job
    c_job_res = started_client.post(
        "/commander/jobs/create",
        json={"job_name": "Decontaminate Factory Hall A", "scenario_id": "chemical_spill", "priority": "CRITICAL"},
    )
    c_job = c_job_res.json()["job"]

    # Query eligible staff for the Chemical Spill job
    eligible_res = started_client.get(f"/commander/jobs/{c_job['job_id']}/eligible-staff")
    assert eligible_res.status_code == 200
    eligible_data = eligible_res.json()

    eligible_personnel_ids = [e.get("personnel_id") for e in eligible_data["eligible"]]
    ineligible_personnel_ids = [ie.get("personnel_id") for ie in eligible_data["ineligible"]]

    # Hazmat guy must be eligible
    assert p2 in eligible_personnel_ids
    # Flood guy must be ineligible
    assert p1 in ineligible_personnel_ids
    # Inactive officer must be ineligible
    assert p3 in ineligible_personnel_ids

    # Query eligible staff for Flood scenario directly
    flood_query = started_client.get("/commander/eligible-staff?scenario_id=flood").json()
    flood_eligible_ids = [e.get("personnel_id") for e in flood_query["eligible"]]
    flood_ineligible_ids = [ie.get("personnel_id") for ie in flood_query["ineligible"]]

    assert p1 in flood_eligible_ids
    assert p2 in flood_ineligible_ids
    assert p3 in flood_ineligible_ids


def test_case_4_successful_job_allocation(started_client):
    """Case 4: Commander assigns job to an eligible staff member successfully."""
    # 1. Register eligible earthquake rescuer
    p_res = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Captain Rohan", "role": "Structural Rescuer", "scenarios": ["earthquake", "building_collapse"]},
    )
    person_id = p_res.json()["person_id"]

    # Add to operation live pool
    u_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={"person_id": person_id, "full_name": "Captain Rohan", "role": "Structural Rescuer", "scenarios": ["earthquake", "building_collapse"]},
    )
    member_id = u_res.json()["member"]["member_id"]

    # 2. Create Earthquake Job
    j_res = started_client.post(
        "/commander/jobs/create",
        json={"job_name": "Tunnel Collapse Shoring", "scenario_id": "earthquake", "priority": "HIGH"},
    )
    job_id = j_res.json()["job"]["job_id"]

    # 3. Assign Job to Member
    assign_res = started_client.post(
        "/commander/jobs/assign",
        json={"job_id": job_id, "member_id": member_id, "notes": "Proceed with heavy jacks."},
    )
    assert assign_res.status_code == 200
    assign_data = assign_res.json()
    assert assign_data["assigned"] is True
    assignment = assign_data["assignment"]
    assert assignment["assignment_id"].startswith("ASN-")
    assert assignment["job_id"] == job_id
    assert assignment["member_id"] == member_id
    assert assignment["status"] == "ASSIGNED"

    # 4. Verify staff member's jobs list
    staff_jobs_res = started_client.get(f"/staff/{member_id}/jobs")
    assert staff_jobs_res.status_code == 200
    staff_jobs = staff_jobs_res.json()["assignments"]
    assert len(staff_jobs) >= 1
    assert any(a["job_id"] == job_id for a in staff_jobs)


def test_case_5_ineligible_assignment_rejection(started_client):
    """Case 5: Strict backend rejection (400 Bad Request) when assigning wrong scenario staff."""
    # 1. Register staff trained ONLY in Avalanche
    p_res = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Snow Patrol Steve", "role": "Avalanche Dog Handler", "scenarios": ["avalanche"]},
    )
    person_id = p_res.json()["person_id"]

    u_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={"person_id": person_id, "full_name": "Snow Patrol Steve", "role": "Avalanche Handler", "scenarios": ["avalanche"]},
    )
    member_id = u_res.json()["member"]["member_id"]

    # 2. Create Wildfire / Urban Fire job
    j_res = started_client.post(
        "/commander/jobs/create",
        json={"job_name": "Chemical Fire Containment", "scenario_id": "urban_fire", "priority": "CRITICAL"},
    )
    job_id = j_res.json()["job"]["job_id"]

    # 3. Attempt Assignment - MUST BE REJECTED WITH HTTP 400
    assign_res = started_client.post(
        "/commander/jobs/assign",
        json={"job_id": job_id, "member_id": member_id, "notes": "Try to assign wrong staff"},
    )
    assert assign_res.status_code == 400
    assert "Staff is not eligible for this disaster scenario." in assign_res.json()["detail"]

    # 4. Verify that NO assignment was created in database
    staff_jobs = started_client.get(f"/staff/{member_id}/jobs").json()["assignments"]
    assert not any(a["job_id"] == job_id for a in staff_jobs)


def test_case_6_multi_scenario_staff_and_multi_hazard(started_client):
    """Case 6: Multi-scenario trained staff matches any registered scenarios."""
    p_res = started_client.post(
        "/admin/personnel/add",
        json={
            "full_name": "Senior Inspector Maya",
            "role": "Multi-Disaster Field Officer",
            "scenarios": ["earthquake", "flood", "cyclone", "building_collapse"],
        },
    )
    person_id = p_res.json()["person_id"]

    u_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={"person_id": person_id, "full_name": "Senior Inspector Maya", "role": "Officer", "scenarios": ["earthquake", "flood", "cyclone", "building_collapse"]},
    )
    member_id = u_res.json()["member"]["member_id"]

    # Test Earthquake job -> eligible
    j1 = started_client.post("/commander/jobs/create", json={"job_name": "EQ Survey", "scenario_id": "earthquake"}).json()["job"]
    a1 = started_client.post("/commander/jobs/assign", json={"job_id": j1["job_id"], "member_id": member_id})
    assert a1.status_code == 200

    # Test Cyclone job -> eligible
    j2 = started_client.post("/commander/jobs/create", json={"job_name": "Cyclone Shelter Search", "scenario_id": "cyclone"}).json()["job"]
    a2 = started_client.post("/commander/jobs/assign", json={"job_id": j2["job_id"], "member_id": member_id})
    assert a2.status_code == 200

    # Test Nuclear / Radiological job -> NOT eligible -> 400
    j3 = started_client.post("/commander/jobs/create", json={"job_name": "Nuclear Core Inspection", "scenario_id": "radiological"}).json()["job"]
    a3 = started_client.post("/commander/jobs/assign", json={"job_id": j3["job_id"], "member_id": member_id})
    assert a3.status_code == 400
    assert "Staff is not eligible for this disaster scenario." in a3.json()["detail"]


def test_case_7_staff_job_processing_workflow(started_client):
    """Case 7: Staff member accepts job, updates progress and marks completed."""
    # 1. Create staff and job
    p_res = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Officer Tarun", "role": "Rescue Medic", "scenarios": ["landslide", "earthquake"]},
    )
    p_id = p_res.json()["person_id"]

    u_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={"person_id": p_id, "full_name": "Officer Tarun", "role": "Medic", "scenarios": ["landslide", "earthquake"]},
    )
    m_id = u_res.json()["member"]["member_id"]

    j_res = started_client.post(
        "/commander/jobs/create",
        json={"job_name": "Hillside Mudslide Extraction", "scenario_id": "landslide", "priority": "CRITICAL"},
    )
    job_id = j_res.json()["job"]["job_id"]

    # 2. Assign job
    assign_res = started_client.post(
        "/commander/jobs/assign",
        json={"job_id": job_id, "member_id": m_id, "notes": "Take medkit and stretcher."},
    )
    assert assign_res.status_code == 200
    assignment_id = assign_res.json()["assignment"]["assignment_id"]

    # 3. Staff accepts job
    acc_res = started_client.post(
        f"/staff/jobs/{assignment_id}/status",
        json={"status": "ACCEPTED", "progress_pct": 10, "result_notes": "Accepted. Moving to site."},
    )
    assert acc_res.status_code == 200
    assert acc_res.json()["assignment"]["status"] == "ACCEPTED"
    assert acc_res.json()["assignment"]["progress_pct"] == 10

    # 4. Staff marks IN_PROGRESS with 60% completion
    prog_res = started_client.post(
        f"/staff/jobs/{assignment_id}/status",
        json={"status": "IN_PROGRESS", "progress_pct": 60, "result_notes": "Extrication underway, victim stable."},
    )
    assert prog_res.status_code == 200
    assert prog_res.json()["assignment"]["status"] == "IN_PROGRESS"
    assert prog_res.json()["assignment"]["progress_pct"] == 60

    # 5. Staff marks COMPLETED with 100% completion
    comp_res = started_client.post(
        f"/staff/jobs/{assignment_id}/status",
        json={"status": "COMPLETED", "progress_pct": 100, "result_notes": "Victim safely transported to base ambulance."},
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["assignment"]["status"] == "COMPLETED"
    assert comp_res.json()["assignment"]["progress_pct"] == 100

    # 6. Commander reviews all assignments
    cmd_assignments = started_client.get("/commander/assignments").json()["assignments"]
    matched_asn = next((a for a in cmd_assignments if a["assignment_id"] == assignment_id), None)
    assert matched_asn is not None
    assert matched_asn["status"] == "COMPLETED"
    assert matched_asn["progress_pct"] == 100
    assert "ambulance" in matched_asn["result_notes"]


def test_case_8_master_scenarios_list_integrity(api_client):
    """Verify central disaster scenarios master list endpoint returns all 19 canonical scenarios."""
    res = api_client.get("/disaster-scenarios")
    assert res.status_code == 200
    scenarios = res.json()["scenarios"]
    assert len(scenarios) == 19

    ids = [s["scenario_id"] for s in scenarios]
    assert "earthquake" in ids
    assert "tsunami" in ids
    assert "flood" in ids
    assert "cyclone" in ids
    assert "landslide" in ids
    assert "building_collapse" in ids
    assert "urban_fire" in ids
    assert "wildfire" in ids
    assert "industrial_accident" in ids
    assert "chemical_leak" in ids
    assert "dam_failure" in ids
    assert "avalanche" in ids
    assert "drought" in ids
    assert "heatwave" in ids
    assert "cloudburst" in ids
    assert "stampede" in ids
    assert "transport_accident" in ids
    assert "infrastructure_entrapment" in ids
    assert "multi_hazard" in ids
