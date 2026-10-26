# app/schemas/auth.py
from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username_or_email: Optional[str] = None
    usernameOrEmail: Optional[str] = None
    username: Optional[str] = None
    password: str
    role: Optional[str] = None


class LoginResponse(BaseModel):
    token: Optional[str] = None
    id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    mfa_required: bool = False
    mfa_token: Optional[str] = None
    message: Optional[str] = None


class VerifyMfaRequest(BaseModel):
    mfa_token: str
    otp: str


class ForgotPasswordRequest(BaseModel):
    email_or_username: str


class ResetPasswordRequest(BaseModel):
    email_or_username: str
    otp_token: str
    new_password: str
