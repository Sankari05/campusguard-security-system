# app/api/v1/endpoints/visitors.py
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.visitor import (
    ConfirmEntryRequest,
    VisitorPassResponse,
    VisitorSelfRegisterRequest,
)
from app.services.visitor_service import VisitorService

router = APIRouter(prefix="/visitors", tags=["Visitor Management"])


@router.post("/self-register")
def self_register(payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    name = (
        payload.get("visitor_name")
        or payload.get("visitorName")
        or payload.get("name")
        or "Visitor"
    )
    req = VisitorSelfRegisterRequest(
        visitor_type=payload.get("visitor_type") or payload.get("visitorType") or "STUDENT",
        visitor_name=name,
        identifier=payload.get("identifier") or payload.get("rollNumber") or payload.get("staffId"),
        phone_number=payload.get("phone_number") or payload.get("phoneNumber"),
        department=payload.get("department") or payload.get("departmentToVisit"),
        reason=payload.get("reason") or payload.get("purpose"),
        additional_details=payload.get("additional_details") or payload.get("additionalDetails"),
        person_to_meet=payload.get("person_to_meet") or payload.get("personToMeet"),
        badge_number=payload.get("badge_number") or payload.get("badgeNumber"),
        vehicle_number=payload.get("vehicle_number") or payload.get("vehicleNumber"),
    )
    service = VisitorService(db)
    res = service.self_register(req)
    return {
        "success": True,
        "message": "Digital Gate Pass generated successfully!",
        "passNumber": res.pass_number,
        "otp": res.otp,
        "expiresAt": res.otp_expires_at,
        "visitorPass": res,
    }


@router.post("/verify-otp")
def verify_otp(payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    otp = str(payload.get("otp") or "").strip()
    pass_number = payload.get("pass_number") or payload.get("passNumber") or ""
    service = VisitorService(db)

    # If pass_number provided, verify directly; otherwise find pass by otp
    if pass_number:
        res = service.verify_otp(pass_number, otp)
    else:
        # Search pass by OTP
        passes = service.visitor_repo.find_pending_or_approved()
        found = next((p for p in passes if str(p.otp).strip() == otp), None)
        if not found:
            return {"success": False, "error": "Invalid OTP. No visitor pass found with this code."}
        res = service.verify_otp(found.pass_number, otp)

    return {
        "success": True,
        "message": "OTP Verified Successfully!",
        "visitorPass": res,
    }


@router.get("/active", response_model=list[VisitorPassResponse])
def get_active(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Any:
    service = VisitorService(db)
    passes = service.visitor_repo.find_pending_or_approved()
    return [VisitorPassResponse.model_validate(p) for p in passes]


@router.get("/list", response_model=list[VisitorPassResponse])
def list_all(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Any:
    service = VisitorService(db)
    return service.get_all()


@router.post("/{pass_id_or_num}/allow")
@router.post("/{pass_id_or_num}/confirm-entry")
def allow_entry(
    pass_id_or_num: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    service = VisitorService(db)
    # Check if id is integer or pass_number
    if pass_id_or_num.isdigit():
        pass_obj = service.visitor_repo.get_by_id(int(pass_id_or_num))
        pass_num = pass_obj.pass_number if pass_obj else pass_id_or_num
    else:
        pass_num = pass_id_or_num

    req = ConfirmEntryRequest(
        watchman_id=payload.get("watchmanId") or payload.get("watchman_id") or str(current_user.id),
        watchman_name=payload.get("watchmanName")
        or payload.get("watchman_name")
        or current_user.full_name,
        badge_number=payload.get("badgeNumber") or payload.get("badge_number"),
    )
    res = service.confirm_entry(pass_num, req)
    return {
        "success": True,
        "message": "Gate Entry Approved & Barrier Opened!",
        "visitorPass": res,
    }


@router.put("/{pass_id_or_num}/checkout")
def checkout(
    pass_id_or_num: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    service = VisitorService(db)
    if pass_id_or_num.isdigit():
        pass_obj = service.visitor_repo.get_by_id(int(pass_id_or_num))
        pass_num = pass_obj.pass_number if pass_obj else pass_id_or_num
    else:
        pass_num = pass_id_or_num

    res = service.checkout(pass_num)
    return {"success": True, "visitorPass": res}
