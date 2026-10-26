# app/services/organization_service.py
"""
GuardMate Multi-Tenant Organization Management Service.
Handles Tenant Onboarding, Super-Admin Vetting, Gate/Shift Setup, Guard Provisioning,
and Multi-Industry Operational Adaptation (College, Hospital, Apartment, Factory, Office).
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.gate_log import GateLog
from app.models.organization import IncidentReport, Organization, OrganizationGate, OrganizationShift
from app.models.user import User
from app.schemas.organization import (
    GateCreateRequest,
    GuardCreateRequest,
    IncidentCreateRequest,
    OrganizationApproveRequest,
    OrganizationRegisterRequest,
    OrganizationRejectRequest,
    ShiftCreateRequest,
)
from app.services.audit_service import AuditService


class OrganizationService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    # ── Slug Generator ────────────────────────────────────────────────────────
    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text[:60]

    # ── Step 1-5: Public Self-Serve Organization Registration ──────────────────
    def register_organization(self, req: OrganizationRegisterRequest, ip_address: str = "unknown") -> Organization:
        base_slug = self._slugify(req.name)
        slug = base_slug
        counter = 1
        while self.db.query(Organization).filter(Organization.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        org_type = req.org_type.upper().strip()
        allowed_types = ["COLLEGE", "HOSPITAL", "APARTMENT", "FACTORY", "OFFICE"]
        if org_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid organization type '{org_type}'. Must be one of: {', '.join(allowed_types)}",
            )

        org = Organization(
            slug=slug,
            name=req.name.strip(),
            org_type=org_type,
            contact_person=req.contact_person.strip(),
            contact_email=req.contact_email.strip().lower(),
            contact_phone=req.contact_phone.strip(),
            address=req.address,
            city=req.city or "Chennai",
            gate_count=req.gate_count,
            expected_guards=req.expected_guards,
            security_requirements=req.security_requirements,
            status="PENDING_APPROVAL",
        )
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)

        self.audit.log_event(
            event_type="ORGANIZATION_REGISTERED",
            username=org.contact_email,
            ip_address=ip_address,
            status="SUCCESS",
            details=f"New organization registered: {org.name} ({org.org_type}) in {org.city}. Awaiting Super-Admin review.",
        )
        return org

    # ── Step 6-7: Super-Admin Vetting & Approval / Rejection ───────────────────
    def list_all_organizations(self, status_filter: Optional[str] = None) -> List[Organization]:
        q = self.db.query(Organization)
        if status_filter:
            q = q.filter(Organization.status == status_filter.upper())
        return q.order_by(Organization.created_at.desc()).all()

    def get_organization_by_id(self, org_id: int) -> Organization:
        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        return org

    def approve_organization(
        self,
        org_id: int,
        req: OrganizationApproveRequest,
        reviewer_name: str = "superadmin",
        ip_address: str = "unknown",
    ) -> Dict[str, Any]:
        org = self.get_organization_by_id(org_id)
        if org.status == "APPROVED":
            return {"message": "Organization is already approved.", "organization": org}

        org.status = "APPROVED"
        org.approved_at = datetime.now(timezone.utc)
        org.rejection_reason = None

        # Auto-create Default Gates based on org_type if none configured
        if not org.gates:
            default_gates = {
                "COLLEGE": [("Main Gate 1", "Front Campus Portal", "MAIN"), ("South Gate 2", "Hostel / Sports Gate", "PEDESTRIAN")],
                "HOSPITAL": [("Ambulance Bay", "Emergency Trauma Rapid Clearance", "EMERGENCY"), ("Visitor Gate A", "Main OPD Lobby", "MAIN")],
                "APARTMENT": [("Residents Main Arch", "Boom Barrier RFID Entry", "VEHICLE"), ("Service Gate B", "Couriers & Domestic Staff", "PEDESTRIAN")],
                "FACTORY": [("Raw Material Inward", "Freight & Truck Checkpoint", "CARGO"), ("Weighbridge Exit", "Outward Cargo Audit", "VEHICLE")],
                "OFFICE": [("Tower A Turnstiles", "Corporate Lobby Access", "MAIN"), ("Executive Basement B1", "Employee Parking", "VEHICLE")],
            }
            gates_to_add = default_gates.get(org.org_type, [("Main Gate 1", "Main Entrance", "MAIN")])
            for g_num, g_name, g_type in gates_to_add:
                self.db.add(OrganizationGate(organization_id=org.id, gate_number=g_num, gate_name=g_name, gate_type=g_type))

        # Auto-create Default Shifts if none configured
        if not org.shifts:
            default_shifts = [
                ("Morning Shift", "06:00", "14:00"),
                ("Evening Shift", "14:00", "22:00"),
                ("Night Shift", "22:00", "06:00"),
            ]
            for s_name, s_start, s_end in default_shifts:
                self.db.add(OrganizationShift(organization_id=org.id, shift_name=s_name, start_time=s_start, end_time=s_end))

        # Auto-Provision Organization Admin Account (Step 8)
        admin_username = req.admin_username or f"admin_{org.slug.replace('-', '_')[:20]}"
        admin_password = req.admin_password or "pass123"
        existing_admin = self.db.query(User).filter(
            (User.username == admin_username) | (User.email == org.contact_email)
        ).first()

        if not existing_admin:
            admin_user = User(
                username=admin_username,
                email=org.contact_email,
                password_hash=hash_password(admin_password),
                full_name=f"{org.contact_person} (Admin)",
                phone_number=org.contact_phone,
                role="ORG_ADMIN",
                organization_id=org.id,
                department="Security Operations",
                is_active=True,
            )
            self.db.add(admin_user)
        else:
            existing_admin.organization_id = org.id
            existing_admin.role = "ORG_ADMIN"
            admin_username = existing_admin.username

        self.db.commit()
        self.db.refresh(org)

        self.audit.log_event(
            event_type="ORGANIZATION_APPROVED",
            username=reviewer_name,
            ip_address=ip_address,
            status="SUCCESS",
            details=f"Approved tenant '{org.name}'. Admin account '{admin_username}' provisioned.",
        )

        return {
            "success": True,
            "message": f"Organization '{org.name}' approved successfully.",
            "admin_credentials": {
                "username": admin_username,
                "temporary_password": admin_password,
                "role": "ORG_ADMIN",
                "organization_id": org.id,
                "organization_name": org.name,
            },
        }

    def reject_organization(
        self,
        org_id: int,
        req: OrganizationRejectRequest,
        reviewer_name: str = "superadmin",
        ip_address: str = "unknown",
    ) -> Organization:
        org = self.get_organization_by_id(org_id)
        org.status = "REJECTED"
        org.rejection_reason = req.reason.strip()
        self.db.commit()
        self.db.refresh(org)

        self.audit.log_event(
            event_type="ORGANIZATION_REJECTED",
            username=reviewer_name,
            ip_address=ip_address,
            status="BLOCKED",
            details=f"Rejected tenant '{org.name}'. Reason: {req.reason}",
        )
        return org

    # ── Step 9-11: Organization Setup & Watchman Provisioning ─────────────────
    def get_tenant_setup(self, org_id: int) -> Dict[str, Any]:
        org = self.get_organization_by_id(org_id)
        gates = self.db.query(OrganizationGate).filter(OrganizationGate.organization_id == org_id).all()
        shifts = self.db.query(OrganizationShift).filter(OrganizationShift.organization_id == org_id).all()
        guards = self.db.query(User).filter(User.organization_id == org_id, User.role == "WATCHMAN").all()

        return {
            "organization": {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "org_type": org.org_type,
                "status": org.status,
                "contact_person": org.contact_person,
                "contact_email": org.contact_email,
                "contact_phone": org.contact_phone,
                "address": org.address,
                "city": org.city,
                "gate_count": org.gate_count,
                "expected_guards": org.expected_guards,
                "security_requirements": org.security_requirements,
            },
            "gates": [
                {
                    "id": g.id,
                    "gate_number": g.gate_number,
                    "gate_name": g.gate_name,
                    "gate_type": g.gate_type,
                    "is_active": g.is_active,
                }
                for g in gates
            ],
            "shifts": [
                {
                    "id": s.id,
                    "shift_name": s.shift_name,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "is_active": s.is_active,
                }
                for s in shifts
            ],
            "guards": [
                {
                    "id": gd.id,
                    "username": gd.username,
                    "full_name": gd.full_name,
                    "email": gd.email,
                    "phone_number": gd.phone_number,
                    "assigned_gate": gd.assigned_gate,
                    "assigned_shift": gd.assigned_shift,
                    "is_active": gd.is_active,
                }
                for gd in guards
            ],
            "counts": {
                "gates": len(gates),
                "shifts": len(shifts),
                "guards": len(guards),
            },
        }

    def add_gate(self, org_id: int, req: GateCreateRequest) -> OrganizationGate:
        self.get_organization_by_id(org_id)
        gate = OrganizationGate(
            organization_id=org_id,
            gate_number=req.gate_number.strip(),
            gate_name=req.gate_name.strip(),
            gate_type=req.gate_type.upper().strip(),
        )
        self.db.add(gate)
        self.db.commit()
        self.db.refresh(gate)
        return gate

    def add_shift(self, org_id: int, req: ShiftCreateRequest) -> OrganizationShift:
        self.get_organization_by_id(org_id)
        shift = OrganizationShift(
            organization_id=org_id,
            shift_name=req.shift_name.strip(),
            start_time=req.start_time.strip(),
            end_time=req.end_time.strip(),
        )
        self.db.add(shift)
        self.db.commit()
        self.db.refresh(shift)
        return shift

    def list_guards(self, org_id: int) -> List[User]:
        return self.db.query(User).filter(User.organization_id == org_id, User.role == "WATCHMAN").all()

    def create_guard(self, org_id: int, req: GuardCreateRequest, admin_name: str = "admin") -> User:
        org = self.get_organization_by_id(org_id)

        # Check unique username and email
        if self.db.query(User).filter(User.username == req.username).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

        guard = User(
            username=req.username.strip(),
            email=req.email.strip().lower(),
            password_hash=hash_password(req.password),
            full_name=req.full_name.strip(),
            phone_number=req.phone_number.strip(),
            role="WATCHMAN",
            organization_id=org.id,
            assigned_gate=req.assigned_gate.strip(),
            assigned_shift=req.assigned_shift.strip(),
            department="Gate Security",
            is_active=True,
        )
        self.db.add(guard)
        self.db.commit()
        self.db.refresh(guard)

        self.audit.log_event(
            event_type="GUARD_CREATED",
            username=admin_name,
            gate_number=guard.assigned_gate,
            status="SUCCESS",
            details=f"Created Watchman '{guard.username}' for {org.name} assigned to {guard.assigned_gate} ({guard.assigned_shift})",
        )
        return guard

    # ── Step 14-16: Industry Vertical Features & Adaptive Watchman Engine ──────
    def get_watchman_profile(self, user: User) -> Dict[str, Any]:
        org = None
        if user.organization_id:
            org = self.db.query(Organization).filter(Organization.id == user.organization_id).first()

        org_type = (org.org_type if org else "COLLEGE").upper()

        # Dynamic modules tailored to the 5 industry verticals
        vertical_modules = {
            "COLLEGE": {
                "title": "Campus Security & Curfew Terminal",
                "badge_color": "#2563EB",
                "modules": [
                    {"id": "outpass", "label": "Student Digital Out-Pass", "desc": "Verify roll number & parental approval", "icon": "🎓"},
                    {"id": "curfew", "label": "Hostel Curfew Tracker", "desc": "21:30 Entry logs & late slip generation", "icon": "🌙"},
                    {"id": "parent_visitors", "label": "Parent & Guest Passes", "desc": "Hostel warden clearance workflow", "icon": "👥"},
                    {"id": "vehicles", "label": "Student/Staff Parking Stickers", "desc": "Authorized two-wheelers & cars", "icon": "🚗"},
                ],
            },
            "HOSPITAL": {
                "title": "Hospital Emergency & Critical Bay Terminal",
                "badge_color": "#DC2626",
                "modules": [
                    {"id": "ambulance", "label": "Ambulance Rapid Clearance", "desc": "Trauma team auto-alert & siren trigger", "icon": "🚑"},
                    {"id": "icu_passes", "label": "ICU / Inpatient Attendant Passes", "desc": "1 Attendant policy enforcement", "icon": "🏥"},
                    {"id": "doctor_priority", "label": "Doctor Emergency Parking", "desc": "Reserved doctor lane barrier control", "icon": "🩺"},
                    {"id": "biowaste", "label": "Bio-Waste & Oxygen Transport", "desc": "Hazardous supply inward/outward log", "icon": "☣️"},
                ],
            },
            "APARTMENT": {
                "title": "Gated Community Resident Security Terminal",
                "badge_color": "#059669",
                "modules": [
                    {"id": "parcels", "label": "E-Commerce Courier Desk", "desc": "Amazon/Swiggy delivery OTP notification", "icon": "📦"},
                    {"id": "intercom", "label": "Flat Intercom Pre-Approval", "desc": "Resident app approval before guest entry", "icon": "🏢"},
                    {"id": "domestic_help", "label": "Maid & Driver Biometric Log", "desc": "Daily domestic staff pass", "icon": "🧹"},
                    {"id": "visitor_parking", "label": "Guest Vehicle Allocation", "desc": "Numbered bay assignment", "icon": "🚙"},
                ],
            },
            "FACTORY": {
                "title": "Industrial Plant & Freight Terminal",
                "badge_color": "#D97706",
                "modules": [
                    {"id": "rgp_pass", "label": "Material Gate Pass (RGP / NRGP)", "desc": "Returnable & Non-returnable stock pass", "icon": "📋"},
                    {"id": "weighbridge", "label": "Weighbridge Freight Audit", "desc": "Gross / Tare weight slip verification", "icon": "⚖️"},
                    {"id": "driver_ppe", "label": "Driver PPE & Safety Gear Check", "desc": "Helmet, safety shoes & high-vis vest", "icon": "🦺"},
                    {"id": "hazmat", "label": "Chemical / Hazardous Entry", "desc": "Fire safety officer escort protocol", "icon": "🔥"},
                ],
            },
            "OFFICE": {
                "title": "Corporate Tech Park Access Terminal",
                "badge_color": "#7C3AED",
                "modules": [
                    {"id": "employee_badges", "label": "Turnstile Badge Validation", "desc": "RFID / Face tap staff access", "icon": "💳"},
                    {"id": "vendor_nda", "label": "Visitor NDA & Host Approval", "desc": "Digital NDA sign-off on iPad kiosk", "icon": "📝"},
                    {"id": "laptop_audit", "label": "Asset & Laptop Serial Check", "desc": "Client proprietary device gate pass", "icon": "💻"},
                    {"id": "after_hours", "label": "After-Hours Facility Access", "desc": "Manager pre-authorization verification", "icon": "🕒"},
                ],
            },
        }

        active_vertical = vertical_modules.get(org_type, vertical_modules["COLLEGE"])

        return {
            "guard": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "assigned_gate": user.assigned_gate,
                "assigned_shift": user.assigned_shift,
            },
            "organization": {
                "id": org.id if org else None,
                "name": org.name if org else "Campus Central Security",
                "slug": org.slug if org else "campus",
                "org_type": org_type,
            },
            "vertical_profile": active_vertical,
        }

    # ── Security Incidents & Daily Operations ─────────────────────────────────
    def create_incident(self, user: User, req: IncidentCreateRequest) -> IncidentReport:
        incident = IncidentReport(
            organization_id=user.organization_id,
            reported_by_id=user.id,
            reported_by_name=user.full_name or user.username,
            gate_number=req.gate_number or user.assigned_gate,
            incident_type=req.incident_type.upper(),
            severity=req.severity.upper(),
            description=req.description.strip(),
            action_taken=req.action_taken.strip() if req.action_taken else None,
            status="OPEN",
        )
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)

        self.audit.log_event(
            event_type="SECURITY_INCIDENT_REPORTED",
            username=user.username,
            gate_number=incident.gate_number,
            status="WARNING" if incident.severity in ["HIGH", "CRITICAL"] else "SUCCESS",
            details=f"Incident {incident.incident_type} ({incident.severity}): {incident.description[:100]}",
        )
        return incident

    def list_incidents(self, organization_id: Optional[int] = None) -> List[IncidentReport]:
        q = self.db.query(IncidentReport)
        if organization_id:
            q = q.filter(IncidentReport.organization_id == organization_id)
        return q.order_by(IncidentReport.created_at.desc()).limit(50).all()

    # ── Step 18: Admin Monitoring & Live Telemetry ─────────────────────────────
    def get_tenant_telemetry(self, org_id: int) -> Dict[str, Any]:
        org = self.get_organization_by_id(org_id)
        gates = self.db.query(OrganizationGate).filter(OrganizationGate.organization_id == org_id).all()
        guards = self.db.query(User).filter(User.organization_id == org_id, User.role == "WATCHMAN").all()
        incidents = self.list_incidents(org_id)
        recent_gate_logs = self.db.query(GateLog).order_by(GateLog.entry_time.desc()).limit(15).all()

        return {
            "organization_name": org.name,
            "org_type": org.org_type,
            "status": org.status,
            "active_gates_count": len(gates),
            "guards_on_duty_count": len(guards),
            "open_incidents_count": sum(1 for inc in incidents if inc.status == "OPEN"),
            "gates": [{"gate_number": g.gate_number, "gate_name": g.gate_name, "gate_type": g.gate_type} for g in gates],
            "guards": [{"id": g.id, "name": g.full_name, "username": g.username, "gate": g.assigned_gate, "shift": g.assigned_shift} for g in guards],
            "recent_incidents": [
                {
                    "id": inc.id,
                    "incident_type": inc.incident_type,
                    "severity": inc.severity,
                    "description": inc.description,
                    "status": inc.status,
                    "gate_number": inc.gate_number,
                    "created_at": inc.created_at.isoformat() if inc.created_at else None,
                }
                for inc in incidents[:5]
            ],
            "recent_gate_logs": [
                {
                    "id": log.id,
                    "person_name": getattr(log, "person_name", None),
                    "gate_number": getattr(log, "gate_number", None),
                    "direction": getattr(log, "direction", "IN"),
                    "entry_time": log.entry_time.isoformat() if hasattr(log, "entry_time") and log.entry_time else None,
                }
                for log in recent_gate_logs
            ],
        }
