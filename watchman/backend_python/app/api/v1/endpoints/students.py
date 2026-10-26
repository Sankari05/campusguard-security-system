# app/api/v1/endpoints/students.py
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.out_pass import OutPassCreateRequest, OutPassResponse
from app.services.student_service import StudentService

router = APIRouter(tags=["Students & Out-Passes"])


@router.get("/students/verify/{roll_number}")
def verify_student(roll_number: str, db: Session = Depends(get_db)) -> Any:
    service = StudentService(db)
    return service.verify_student_by_roll(roll_number)


@router.get("/outpass/list", response_model=list[OutPassResponse])
def list_out_passes(db: Session = Depends(get_db)) -> Any:
    service = StudentService(db)
    return service.list_out_passes()


@router.post("/outpass/apply", response_model=OutPassResponse)
def apply_out_pass(payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    req = OutPassCreateRequest(
        roll_number=payload.get("roll_number")
        or payload.get("rollNumber")
        or payload.get("studentRollNumber")
        or "",
        student_name=payload.get("student_name") or payload.get("studentName") or "",
        department=payload.get("department") or "",
        reason=payload.get("reason") or "Personal Leave",
        destination=payload.get("destination"),
        out_time_expected=payload.get("out_time_expected") or payload.get("outTimeExpected"),
        in_time_expected=payload.get("in_time_expected") or payload.get("inTimeExpected"),
    )
    service = StudentService(db)
    return service.request_out_pass(req)


@router.post("/outpass/verify-code/{code}")
def verify_outpass_code(code: str, db: Session = Depends(get_db)) -> Any:
    service = StudentService(db)
    res = service.verify_and_exit_gate(code)
    return {
        "valid": True,
        "message": "Pass Verified! Gate Opened for Student.",
        "pass": res,
    }


@router.post("/outpass/{code}/approve", response_model=OutPassResponse)
@router.put("/outpass/{code}/approve", response_model=OutPassResponse)
def approve_out_pass(
    code: str, payload: dict = Body(default={}), db: Session = Depends(get_db)
) -> Any:
    approved_by = payload.get("approved_by") or payload.get("approvedBy") or "HOD / Faculty Warden"
    service = StudentService(db)
    # Check if code is integer ID
    if code.isdigit():
        op = service.out_pass_repo.get_by_id(int(code))
        pass_code = op.pass_code if op else code
    else:
        pass_code = code
    return service.approve_out_pass(pass_code, approved_by)


@router.post("/outpass/{code}/return", response_model=OutPassResponse)
def return_student(code: str, db: Session = Depends(get_db)) -> Any:
    service = StudentService(db)
    return service.mark_student_returned(code)
