"""
app.schemas.student
Pydantic v2 schemas for student management, enrollment, and attendance metrics.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class StudentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of student")
    roll_number: str = Field(..., min_length=2, max_length=30, description="Unique roll number (e.g. 23CS008)")
    department: str = Field(..., min_length=2, max_length=20, description="Department code (e.g. CSE, ECE)")
    year: Optional[str] = Field(None, description="Academic year (e.g. 4th Year, IV Year)")
    semester: Optional[str] = Field(None, description="Semester (1-8)")
    section: Optional[str] = Field("A", max_length=5, description="Section code (e.g. A, B, C)")
    email: Optional[str] = Field(None, description="Student email address")
    mobile: Optional[str] = Field(None, description="Contact phone number")

    @field_validator("roll_number", "department")
    @classmethod
    def normalize_case(cls, v: str) -> str:
        return v.strip().upper() if v else v


class StudentCreate(StudentBase):
    """Payload sent during student enrollment."""
    course: Optional[str] = Field("B.E", description="Degree program")
    gender: Optional[str] = Field("Other", description="Gender")
    dob: Optional[str] = Field(None, description="Date of birth YYYY-MM-DD")


class StudentResponse(StudentBase):
    student_id: str = Field(..., description="Internal unique student identifier")
    course: Optional[str] = Field(None)
    gender: Optional[str] = Field(None)
    attendance_pct: float = Field(0.0, ge=0.0, le=100.0, description="Attendance percentage in window")
    status: str = Field("critical", description="Status bucket: good, warning, or critical")
    active: int = Field(1, description="1 if active, 0 if disabled")
    enrolled_date: Optional[str] = Field(None)

    model_config = {"from_attributes": True}


class StudentListResponse(BaseModel):
    students: List[StudentResponse]
    total: int = Field(0, ge=0)
    page: int = Field(1, ge=1)
    per_page: int = Field(10, ge=1)
    total_pages: int = Field(1, ge=1)


class StudentStatsResponse(BaseModel):
    total: int = Field(0, ge=0)
    present_today: int = Field(0, ge=0)
    absent_today: int = Field(0, ge=0)
    critical_count: int = Field(0, ge=0)
