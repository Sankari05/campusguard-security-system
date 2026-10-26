"""
app.core.validators
Centralized validation helpers for student, faculty, and contact fields.
Enforces RFC compliant email checks, Indian mobile formats, and age constraints.
"""

import re
from datetime import date as _date, datetime as _datetime
from typing import Optional
from fastapi import HTTPException
import database as db

_EMAIL_RE = re.compile(
    r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'
)
_MOBILE_RE = re.compile(r'^[6-9][0-9]{9}$')
_NAME_RE = re.compile(r'^[A-Za-z]+( [A-Za-z]+)*$')

_DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "throwam.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "guerrillamailblock.com", "grr.la", "guerrillamail.info", "spam4.me",
    "fakeinbox.com", "maildrop.cc", "dispostable.com", "mailnull.com",
    "spamgourmet.com", "trashmail.me", "throwaway.email", "discard.email",
    "mailnesia.com", "tempinbox.com", "spamex.com", "mytemp.email",
    "burnermail.io", "temp-mail.org", "getnada.com", "anonaddy.com",
}


def validate_email(value: str, field: str = "Email", exclude_id: str = "") -> str:
    """Validate email address. Raises HTTPException(422 or 409) on failure."""
    v = (value or "").strip()
    if not v:
        raise HTTPException(status_code=422, detail=f"{field} is required.")
    if " " in v:
        raise HTTPException(status_code=422, detail=f"Spaces are not allowed in {field.lower()}.")
    if len(v) < 5:
        raise HTTPException(status_code=422, detail=f"{field} is too short (minimum 5 characters).")
    if len(v) > 254:
        raise HTTPException(status_code=422, detail=f"{field} is too long (maximum 254 characters).")
    if not _EMAIL_RE.match(v):
        raise HTTPException(status_code=422, detail=f"Please enter a valid {field.lower()} address.")

    parts = v.split("@")
    if len(parts) != 2 or not parts[0]:
        raise HTTPException(status_code=422, detail=f"Username part (before @) is missing in {field.lower()}.")
    local, domain = parts
    if not domain or domain.startswith(".") or ".." in domain:
        raise HTTPException(status_code=422, detail=f"Domain part (after @) is invalid in {field.lower()}.")
    if re.search(r'[^A-Za-z0-9._%+\-]', local):
        raise HTTPException(status_code=422, detail=f"{field} contains invalid characters.")
    if domain.lower() in _DISPOSABLE_DOMAINS:
        raise HTTPException(status_code=422, detail="Temporary/disposable email addresses are not allowed.")

    dup = db.check_email_duplicate(v, exclude_id)
    if dup.get("exists"):
        role = dup.get("role", "record")
        name = dup.get("name", "")
        raise HTTPException(
            status_code=409,
            detail=f"This email address is already registered to {name} ({role}).",
        )
    return v


def validate_mobile(value: str, field: str = "Mobile Number", exclude_id: str = "") -> str:
    """Validate Indian mobile number (10 digits starting 6-9). Raises HTTPException on failure."""
    v = (value or "").strip()
    if not v:
        raise HTTPException(status_code=422, detail=f"{field} is required.")
    if re.search(r'[A-Za-z]', v):
        raise HTTPException(status_code=422, detail=f"{field} must not contain letters.")
    if re.search(r'[^0-9]', v):
        raise HTTPException(status_code=422, detail=f"{field} must not contain special characters.")
    if len(v) != 10:
        raise HTTPException(status_code=422, detail=f"{field} must be exactly 10 digits.")
    if not _MOBILE_RE.match(v):
        raise HTTPException(status_code=422, detail=f"{field} must start with 6, 7, 8, or 9.")

    dup = db.check_mobile_duplicate(v, exclude_id)
    if dup.get("exists"):
        role = dup.get("role", "record")
        name = dup.get("name", "")
        raise HTTPException(
            status_code=409,
            detail=f"{field} {v} is already registered to {name} ({role}).",
        )
    return v


def validate_dob(dob_str: str, role: str, designation: str = "") -> str:
    """
    Validate date_of_birth and return normalized YYYY-MM-DD.
    Enforces age boundaries by role:
      - student: 17 <= age <= 50
      - faculty: age >= 25 (or 32 for associate)
      - hod: age >= 35
    """
    v = (dob_str or "").strip()
    if not v:
        raise HTTPException(status_code=422, detail="Date of Birth is required.")

    parsed = None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            parsed = _datetime.strptime(v, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        raise HTTPException(status_code=422, detail="Please enter a valid date.")

    today = _date.today()
    if parsed > today:
        raise HTTPException(status_code=422, detail="Future dates are not allowed.")

    age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    role_norm = (role or "").lower()
    desig_norm = (designation or "").lower()

    if role_norm == "student":
        if age < 17 or age > 50:
            raise HTTPException(status_code=422, detail="Student must be between 17 and 50 years old.")
    elif role_norm in ("faculty", "classincharge"):
        if "associate" in desig_norm:
            if age < 32:
                raise HTTPException(status_code=422, detail="Associate Professor must be at least 32 years old.")
        else:
            if age < 25:
                raise HTTPException(status_code=422, detail="Assistant Professor must be at least 25 years old.")
    elif role_norm == "hod":
        if age < 35:
            raise HTTPException(status_code=422, detail="HOD must be at least 35 years old.")

    return parsed.strftime("%Y-%m-%d")


def validate_name(val: str, label: str = "Name") -> str:
    """Validate name field (letters and single spaces)."""
    v = (val or "").strip()
    if not v:
        raise HTTPException(status_code=422, detail=f"{label} is required.")
    if len(v) < 2 or len(v) > 50:
        raise HTTPException(status_code=422, detail=f"{label} must be between 2 and 50 characters.")
    if not _NAME_RE.match(v):
        raise HTTPException(status_code=422, detail=f"{label} must contain letters and single spaces only.")
    return v
