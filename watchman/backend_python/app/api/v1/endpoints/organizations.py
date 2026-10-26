# app/api/v1/endpoints/organizations.py
"""
GuardMate Multi-Tenant REST API Endpoints.
Covers Public Registration, Platform Super-Admin Vetting, Tenant Admin Setup,
Guard Provisioning, and Industry-Specific Operational Profiles.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.organization import (
    GateCreateRequest,
    GuardCreateRequest,
    GuardUserResponse,
    IncidentCreateRequest,
    IncidentResponse,
    OrganizationApproveRequest,
    OrganizationGateResponse,
    OrganizationRegisterRequest,
    OrganizationRejectRequest,
    OrganizationResponse,
    OrganizationShiftResponse,
    ShiftCreateRequest,
)
from app.services.organization_service import OrganizationService

router = APIRouter(tags=["Multi-Tenant Organizations"])


# ── 1. Public Self-Serve Registration & Info ──────────────────────────────────
@router.post("/organizations/register", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def register_organization(
    req: OrganizationRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Public endpoint for any College, Hospital, Apartment, Factory, or Office to register."""
    service = OrganizationService(db)
    client_ip = request.client.host if request.client else "unknown"
    return service.register_organization(req, ip_address=client_ip)


@router.get("/organizations/types")
def get_supported_organization_types() -> Any:
    """Returns the 5 supported GuardMate industry verticals and their operational profiles."""
    return [
        {
            "type": "COLLEGE",
            "title": "College & University Campuses",
            "tagline": "Campus Curfew, Student Out-Pass & Hostelite Security",
            "icon": "🎓",
            "features": ["Student Roll Verification", "Digital Out-Pass", "Hostel Curfew Tracker", "Parent Visitor Badges", "Faculty Lane"],
        },
        {
            "type": "HOSPITAL",
            "title": "Hospitals & Healthcare Facilities",
            "tagline": "Emergency Ambulance Bay & Patient Ward Security",
            "icon": "🏥",
            "features": ["Ambulance Rapid Clearance", "ICU / Ward Attendant Passes", "Doctor Priority Parking", "Bio-Waste Transport Log"],
        },
        {
            "type": "APARTMENT",
            "title": "Gated Communities & Residential Towers",
            "tagline": "E-Commerce Courier Desk & Resident Intercom Approvals",
            "icon": "🏢",
            "features": ["Delivery Parcel Desk", "Flat Intercom Pre-Approval", "Domestic Maid/Driver Logs", "Resident Vehicle RFID"],
        },
        {
            "type": "FACTORY",
            "title": "Industrial Plants, Forges & Warehouses",
            "tagline": "Material Returnable Pass, Weighbridge & PPE Gear Audit",
            "icon": "🏭",
            "features": ["Material Gate Pass (RGP / NRGP)", "Weighbridge Freight Audit", "Driver PPE Gear Check", "Hazardous Zone Escort"],
        },
        {
            "type": "OFFICE",
            "title": "Corporate Tech Parks & High-Rise Towers",
            "tagline": "Turnstile Badge Validation & Visitor NDA Registry",
            "icon": "🏛️",
            "features": ["Employee Turnstile Badges", "Client Meeting NDA iPad Kiosk", "Laptop Serial Number Audit", "After-Hours Facility Approval"],
        },
    ]


# ── 2. Super-Admin Vetting & Life Cycle Controls ──────────────────────────────
@router.get("/super-admin/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "ADMIN"])),
) -> Any:
    """Super Admin reviews all registered organizations (Pending, Approved, Rejected)."""
    service = OrganizationService(db)
    return service.list_all_organizations(status_filter=status_filter)


@router.post("/super-admin/organizations/{org_id}/approve")
def approve_organization(
    org_id: int,
    req: OrganizationApproveRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "ADMIN"])),
) -> Any:
    """Super Admin approves organization application and provisions Tenant Admin."""
    service = OrganizationService(db)
    client_ip = request.client.host if request.client else "unknown"
    return service.approve_organization(
        org_id=org_id,
        req=req,
        reviewer_name=current_user.username,
        ip_address=client_ip,
    )


@router.post("/super-admin/organizations/{org_id}/reject", response_model=OrganizationResponse)
def reject_organization(
    org_id: int,
    req: OrganizationRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "ADMIN"])),
) -> Any:
    """Super Admin rejects organization application with a specific reason."""
    service = OrganizationService(db)
    client_ip = request.client.host if request.client else "unknown"
    return service.reject_organization(
        org_id=org_id,
        req=req,
        reviewer_name=current_user.username,
        ip_address=client_ip,
    )


# ── 3. Tenant Admin Configuration & Guard Management ─────────────────────────
@router.get("/tenant/setup")
def get_tenant_configuration(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ORG_ADMIN", "ADMIN", "SUPER_ADMIN"])),
) -> Any:
    """Get setup details (gates, shifts, guards) for the current user's organization."""
    org_id = current_user.organization_id
    if not org_id and current_user.role in ["ADMIN", "SUPER_ADMIN"]:
        # Fallback to first available approved organization for super admins
        from app.models.organization import Organization
        first_org = db.query(Organization).filter(Organization.status == "APPROVED").first()
        org_id = first_org.id if first_org else 1

    service = OrganizationService(db)
    return service.get_tenant_setup(org_id)


@router.post("/tenant/gates", response_model=OrganizationGateResponse)
def add_organization_gate(
    req: GateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ORG_ADMIN", "ADMIN", "SUPER_ADMIN"])),
) -> Any:
    """Tenant Admin configures a new gate."""
    org_id = current_user.organization_id or 1
    service = OrganizationService(db)
    return service.add_gate(org_id, req)


@router.post("/tenant/shifts", response_model=OrganizationShiftResponse)
def add_organization_shift(
    req: ShiftCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ORG_ADMIN", "ADMIN", "SUPER_ADMIN"])),
) -> Any:
    """Tenant Admin configures a new duty shift."""
    org_id = current_user.organization_id or 1
    service = OrganizationService(db)
    return service.add_shift(org_id, req)


@router.get("/tenant/guards", response_model=List[GuardUserResponse])
def list_organization_guards(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ORG_ADMIN", "ADMIN", "SUPER_ADMIN"])),
) -> Any:
    """Tenant Admin lists all Watchmen belonging to their organization."""
    org_id = current_user.organization_id or 1
    service = OrganizationService(db)
    return service.list_guards(org_id)


@router.post("/tenant/guards", response_model=GuardUserResponse)
def create_organization_guard(
    req: GuardCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ORG_ADMIN", "ADMIN", "SUPER_ADMIN"])),
) -> Any:
    """Tenant Admin provisions a new Watchman with assigned gate and shift."""
    org_id = current_user.organization_id or 1
    service = OrganizationService(db)
    return service.create_guard(org_id, req, admin_name=current_user.username)


@router.get("/tenant/telemetry")
def get_tenant_telemetry(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ORG_ADMIN", "ADMIN", "SUPER_ADMIN"])),
) -> Any:
    """Tenant Admin real-time monitoring and telemetry feed."""
    org_id = current_user.organization_id or 1
    service = OrganizationService(db)
    return service.get_tenant_telemetry(org_id)


# ── 4. Watchman Adaptive Profile & Operational Incidents ──────────────────────
@router.get("/watchman/profile")
def get_watchman_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Returns Watchman's assigned org, gate, shift, and tailored industry profile modules."""
    service = OrganizationService(db)
    return service.get_watchman_profile(current_user)


@router.post("/watchman/incidents", response_model=IncidentResponse)
def report_security_incident(
    req: IncidentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Watchman or Admin logs a security incident scoped to their organization."""
    service = OrganizationService(db)
    return service.create_incident(current_user, req)


@router.get("/watchman/incidents", response_model=List[IncidentResponse])
def list_security_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List security incidents scoped to user's organization."""
    service = OrganizationService(db)
    return service.list_incidents(current_user.organization_id)
