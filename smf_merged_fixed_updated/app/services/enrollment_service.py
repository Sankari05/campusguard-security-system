"""
app.services.enrollment_service
Business logic for student and faculty enrollment, email verification OTP, and face dataset collection.
"""

import os
import shutil
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from fastapi import HTTPException, UploadFile
import config
import database as db
from app.repositories.enrollment_repository import EnrollmentRepository
from app.core.logger import get_logger

log = get_logger("enrollment_service")


class EnrollmentService:
    """Enterprise domain service managing the enrollment pipeline."""

    OTP_MAX_ATTEMPTS = 5
    OTP_EXPIRY_MINUTES = 5
    OTP_MAX_RESENDS = 3

    def __init__(self, repo: Optional[EnrollmentRepository] = None):
        self.repo = repo or EnrollmentRepository()

    def send_enrollment_otp(self, email: str) -> Dict[str, Any]:
        """Validate email format and availability, issue cryptographic OTP, and dispatch SMTP email."""
        from app.core.validators import validate_email
        from utils.email_utils import _smtp_cfg
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        norm_email = email.strip().lower()
        # Enforce validation & duplicate check
        validate_email(norm_email)

        # Check existing session resend limit
        existing = self.repo.get_latest_session(norm_email, is_verified=0)
        resend_count = existing["resend_count"] if existing else 0
        if resend_count >= self.OTP_MAX_RESENDS:
            raise HTTPException(
                status_code=429,
                detail=f"Maximum resend attempts ({self.OTP_MAX_RESENDS}) reached. Please use a different email or contact support."
            )

        # Cryptographically secure 6-digit OTP
        otp_plain = "".join(secrets.choice("0123456789") for _ in range(6))
        otp_hash = hashlib.sha256(otp_plain.encode()).hexdigest()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=self.OTP_EXPIRY_MINUTES)).isoformat()

        self.repo.create_session(
            email=norm_email,
            otp_hash=otp_hash,
            expires_at=expires_at,
            resend_count=resend_count + (1 if existing else 0)
        )

        cfg = _smtp_cfg()
        if not cfg["user"] or not cfg["pass"]:
            raise HTTPException(status_code=503, detail="SMTP not configured. Contact administrator.")

        html_body = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:480px;margin:0 auto;background:#f8fafc;border-radius:16px;padding:32px;">
          <div style="text-align:center;margin-bottom:24px;">
            <h2 style="background:linear-gradient(135deg,#06b6d4,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:24px;font-weight:800;margin:0;">EduTrack Pro</h2>
            <p style="color:#64748b;font-size:13px;margin:4px 0 0;">Smart Attendance & Face Recognition System</p>
          </div>
          <div style="background:#fff;border-radius:12px;padding:28px;border:1.5px solid #e2e8f0;text-align:center;">
            <p style="font-size:16px;font-weight:600;color:#0f172a;margin-bottom:8px;">Email Verification OTP</p>
            <p style="color:#64748b;font-size:13px;line-height:1.6;margin-bottom:20px;">Use the one-time password below to verify your student/faculty email address. Valid for 5 minutes.</p>
            <div style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);border:2px dashed #22c55e;border-radius:10px;padding:16px;margin-bottom:20px;">
              <span style="font-size:36px;font-weight:800;letter-spacing:10px;color:#15803d;font-family:monospace;">{otp_plain}</span>
            </div>
            <p style="color:#94a3b8;font-size:12px;margin:0;">If you did not request this, you can safely ignore this email.</p>
          </div>
        </div>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "EduTrack Pro — Email Verification OTP"
        msg["From"] = cfg["from_email"]
        msg["To"] = norm_email
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(cfg["user"], cfg["pass"])
                server.sendmail(cfg["from_email"], [norm_email], msg.as_string())
        except Exception as e:
            log.error("[EnrollOTP] SMTP delivery failed to %s: %s", norm_email, e)
            raise HTTPException(status_code=502, detail=f"Failed to send verification email: {e}")

        log.info("[EnrollOTP] OTP successfully sent to %s", norm_email)
        return {"status": "sent", "message": "OTP sent to your email address."}

    def verify_enrollment_otp(self, email: str, otp: str) -> Dict[str, Any]:
        """Timing-safe verification of the submitted OTP against hashed database record."""
        norm_email = email.strip().lower()
        record = self.repo.get_latest_session(norm_email, is_verified=0)
        if not record:
            raise HTTPException(status_code=400, detail="No active OTP found. Please request a new one.")

        sid = record["id"]
        # Check attempts
        if record["attempts"] >= self.OTP_MAX_ATTEMPTS:
            self.repo.lock_session(sid)
            raise HTTPException(status_code=429, detail=f"OTP locked after {self.OTP_MAX_ATTEMPTS} failed attempts. Please request a new OTP.")

        # Expiry check
        expires_at = datetime.fromisoformat(record["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_at:
            self.repo.lock_session(sid)
            raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

        # Hash comparison
        submitted_hash = hashlib.sha256(otp.strip().encode()).hexdigest()
        if submitted_hash != record["otp_hash"]:
            new_attempts = record["attempts"] + 1
            remaining = self.OTP_MAX_ATTEMPTS - new_attempts
            if remaining <= 0:
                self.repo.lock_session(sid)
                raise HTTPException(status_code=429, detail=f"OTP locked after {self.OTP_MAX_ATTEMPTS} failed attempts. Please request a new OTP.")
            self.repo.update_attempts(sid, new_attempts)
            raise HTTPException(status_code=400, detail=f"Invalid OTP. {remaining} attempt(s) remaining.")

        self.repo.mark_session_verified(sid)
        log.info("[EnrollOTP] Email verified successfully: %s", norm_email)
        return {"status": "verified", "message": "Email verified successfully."}

    async def save_face_images(
        self,
        entity_id: str,
        role: str,
        file_items: List[UploadFile],
        username: str,
        client_ip: str
    ) -> Dict[str, Any]:
        """Save captured webcam face images for dataset training."""
        entity_id = entity_id.strip().upper()
        role = role.strip().lower()
        if not entity_id:
            raise HTTPException(status_code=422, detail="entity_id is required")
        if not file_items:
            raise HTTPException(status_code=422, detail="No files uploaded")

        if role in ("faculty", "classincharge"):
            save_dir = os.path.join(config.BASE_DIR, "data", "known_faces", "faculty", entity_id)
            dataset_dir = os.path.join(config.BASE_DIR, "data", "dataset", "faculty", entity_id)
        elif role == "hod":
            save_dir = os.path.join(config.BASE_DIR, "data", "known_faces", "hod", entity_id)
            dataset_dir = os.path.join(config.BASE_DIR, "data", "dataset", "hod", entity_id)
        else:
            save_dir = os.path.join(config.BASE_DIR, "data", "known_faces", entity_id)
            dataset_dir = os.path.join(config.BASE_DIR, "data", "dataset", entity_id)

        os.makedirs(save_dir, exist_ok=True)
        os.makedirs(dataset_dir, exist_ok=True)

        existing = [f for f in os.listdir(save_dir) if f.lower().endswith(".jpg")]
        start_idx = len(existing)

        saved = 0
        for i, file_item in enumerate(file_items):
            try:
                contents = await file_item.read()
                if not contents:
                    continue
                idx = start_idx + i
                filename = f"{entity_id}_p{idx:04d}.jpg"
                dest_kf = os.path.join(save_dir, filename)
                dest_ds = os.path.join(dataset_dir, filename)
                with open(dest_kf, "wb") as fp:
                    fp.write(contents)
                shutil.copy2(dest_kf, dest_ds)
                saved += 1
            except Exception as e:
                log.warning("Face image save error idx=%d: %s", i, e)

        if saved == 0:
            raise HTTPException(status_code=400, detail="No images could be saved — check file format")

        db.log_audit(username, "enroll_face_images", entity_id, f"{saved} images saved (role={role})", client_ip)
        return {
            "status": "saved",
            "entity_id": entity_id,
            "role": role,
            "count": saved,
            "save_dir": save_dir,
            "message": f"{saved} face images saved for {entity_id}. Run training to activate.",
        }
