"""
app.schemas.override
Pydantic v2 schemas for attendance overrides, audit logs, and approval workflows.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class OverrideCreate(BaseModel):
    student_id: str = Field(..., description="Target student ID (e.g. STU_23CS101)")
    period: str = Field(..., description="Class period (e.g. Period 1, 1)")
    action: str = Field(..., description="Action to perform: mark_present or mark_absent")
    note: str = Field(..., min_length=3, max_length=500, description="Audit reason for manual override")
    date: Optional[str] = Field(None, description="Target attendance date YYYY-MM-DD")
    course_code: Optional[str] = Field(None, description="Subject/Course code (e.g. CS8491)")


class OverrideRecord(BaseModel):
    id: Optional[int] = None
    department: Optional[str] = None
    year: Optional[str] = None
    semester: Optional[str] = None
    section: Optional[str] = None
    student_register_number: Optional[str] = None
    student_name: Optional[str] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    period: Optional[str] = None
    attendance_from: Optional[str] = None
    attendance_to: Optional[str] = None
    reason: Optional[str] = None
    overridden_by: Optional[str] = None
    faculty_id: Optional[str] = None
    faculty_role: Optional[str] = None
    override_date: Optional[str] = None
    override_time: Optional[str] = None

    model_config = {"from_attributes": True}


class OverrideStatsResponse(BaseModel):
    total: int = Field(0, ge=0)
    today: int = Field(0, ge=0)
    faculty_count: int = Field(0, ge=0)
    last_override: Optional[dict] = None
