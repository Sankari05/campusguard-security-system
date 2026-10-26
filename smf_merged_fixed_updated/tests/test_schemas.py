"""
tests/test_schemas.py
Unit tests verifying Pydantic v2 schemas, validations, and serialization.
"""

import pytest
from pydantic import ValidationError
from app.schemas.student import StudentCreate, StudentResponse, StudentListResponse
from app.schemas.override import OverrideCreate, OverrideStatsResponse
from app.schemas.common import ApiResponse, PaginationMeta


def test_student_create_validation_success():
    payload = {
        "name": "Arathilbar nishaS",
        "roll_number": "23cs008",
        "department": "cse",
        "year": "4th Year",
        "section": "A",
        "email": "nisha@college.edu",
    }
    student = StudentCreate(**payload)
    # Field validator must uppercase roll_number and department
    assert student.roll_number == "23CS008"
    assert student.department == "CSE"
    assert student.name == "Arathilbar nishaS"


def test_student_create_validation_failure():
    with pytest.raises(ValidationError):
        # Missing required roll_number and department
        StudentCreate(name="J")


def test_student_response_defaults():
    data = {
        "student_id": "STU_23CS008",
        "name": "Arathilbar nishaS",
        "roll_number": "23CS008",
        "department": "CSE",
        "attendance_pct": 82.5,
        "status": "good",
    }
    resp = StudentResponse(**data)
    assert resp.attendance_pct == 82.5
    assert resp.status == "good"
    assert resp.active == 1


def test_override_create_schema():
    ov = OverrideCreate(
        student_id="STU_23CS008",
        period="1",
        action="mark_present",
        note="Medical certificate submitted",
    )
    assert ov.action == "mark_present"
    assert "Medical" in ov.note


def test_api_response_envelope():
    meta = PaginationMeta(page=1, per_page=10, total=4, total_pages=1)
    envelope = ApiResponse(data={"count": 4}, message="Success")
    assert envelope.success is True
    assert envelope.data["count"] == 4
    assert meta.total_pages == 1
