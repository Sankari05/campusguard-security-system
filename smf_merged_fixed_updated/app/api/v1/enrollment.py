"""
app.api.v1.enrollment
FastAPI route controller for student & faculty enrollment, email verification OTP, and face images.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from pydantic import BaseModel

from app.services.enrollment_service import EnrollmentService
from auth_utils import admin_required, uname

router = APIRouter(prefix="/api/enroll", tags=["Enrollment & OTP"])
_service = EnrollmentService()


class EnrollOTPSendReq(BaseModel):
    email: str


class EnrollOTPVerifyReq(BaseModel):
    email: str
    otp: str


@router.post("/send-otp")
def api_enroll_send_otp(req: EnrollOTPSendReq):
    """Step 1: Validate email and dispatch 6-digit OTP via SMTP."""
    return _service.send_enrollment_otp(req.email)


@router.post("/verify-otp")
def api_enroll_verify_otp(req: EnrollOTPVerifyReq):
    """Step 2: Verify the submitted 6-digit OTP."""
    return _service.verify_enrollment_otp(req.email, req.otp)


@router.post("/face-images")
async def api_enroll_face_images(
    request: Request,
    user: dict = Depends(admin_required),
):
    """Save captured webcam face images for dataset training."""
    form_data = await request.form()
    entity_id = str(form_data.get("entity_id", "")).strip()
    role = str(form_data.get("role", "student")).strip().lower()
    file_items = form_data.getlist("files")
    client_ip = request.client.host if request.client else "?"
    username = uname(user) if callable(uname) else user.get("sub", "admin")

    return await _service.save_face_images(
        entity_id=entity_id,
        role=role,
        file_items=file_items,
        username=username,
        client_ip=client_ip
    )
