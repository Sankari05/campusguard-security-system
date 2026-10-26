# app/api/v1/api.py
"""
API v1 Router Aggregator.
Combines all domain-specific routers into a single master router.
Enforces strict JWT authentication dependencies across all protected resources.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.endpoints import (
    auth,
    copilot,
    duty,
    emergency,
    gate,
    handover,
    lost_found,
    maintenance,
    organizations,
    parcels,
    parking,
    patrol,
    students,
    visitors,
    zone_risk,
)

api_router = APIRouter()

# ── Authentication & Identity ──────────────────────────────────
# Contains public login/forgot/reset alongside protected logout/me
api_router.include_router(auth.router)

# ── Multi-Tenant GuardMate Platform (SaaS Onboarding & Tenant Controls) ──
api_router.include_router(organizations.router)

# ── Core CampusGuard Gate Security (Protected) ─────────────────
api_router.include_router(gate.router, dependencies=[Depends(get_current_user)])
api_router.include_router(students.router, dependencies=[Depends(get_current_user)])
api_router.include_router(parcels.router, dependencies=[Depends(get_current_user)])
api_router.include_router(emergency.router, dependencies=[Depends(get_current_user)])
api_router.include_router(handover.router, dependencies=[Depends(get_current_user)])
api_router.include_router(handover.router, prefix="/shift-handover", dependencies=[Depends(get_current_user)])

# ── Visitor Management (Hybrid: Public Kiosk + Protected Staff Actions) ─
api_router.include_router(visitors.router)

# ── SmartWatchman AI Pillars (Protected Staff Operations) ──────
api_router.include_router(maintenance.router, prefix="/maintenance", tags=["Maintenance"], dependencies=[Depends(get_current_user)])
api_router.include_router(parking.router, prefix="/parking", tags=["Parking"], dependencies=[Depends(get_current_user)])
api_router.include_router(patrol.router, prefix="/patrol", tags=["Patrol"], dependencies=[Depends(get_current_user)])
api_router.include_router(lost_found.router, prefix="/lost-found", tags=["Lost and Found"], dependencies=[Depends(get_current_user)])
api_router.include_router(duty.router, prefix="/duty", tags=["Duty Attendance"], dependencies=[Depends(get_current_user)])
api_router.include_router(zone_risk.router, prefix="/zone-risk", tags=["Zone & Weather Risk"], dependencies=[Depends(get_current_user)])

# ── Cognitive Guard Co-Pilot (Protected AI Advisory Operations) ─
api_router.include_router(copilot.router, prefix="/copilot", tags=["AI Guard Co-Pilot"], dependencies=[Depends(get_current_user)])
