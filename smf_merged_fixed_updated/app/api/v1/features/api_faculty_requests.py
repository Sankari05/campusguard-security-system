# =============================================================
# api_faculty_requests.py — NEW FILE (additive only)
#
# PHASE 1 — Faculty Request Management (Leave + OD approvals)
#
# Follows the exact register_<feature>_routes(app, ...) pattern used
# by api_hod.py / api_anomaly.py / api_workload.py.
#
# Endpoints (all under /api/faculty/requests/*):
#   GET  /api/faculty/requests/leave            (?status=Pending|Approved|Rejected)
#   GET  /api/faculty/requests/leave/{id}
#   POST /api/faculty/requests/leave/{id}/approve
#   POST /api/faculty/requests/leave/{id}/reject
#
#   GET  /api/faculty/requests/od                (?status=Pending|Forwarded|Approved|Rejected)
#       -- HOD role: ?status=Pending is server-side aliased to Forwarded,
#          see list_od_requests() below.
#   GET  /api/faculty/requests/od/{id}
#   POST /api/faculty/requests/od/{id}/approve
#   POST /api/faculty/requests/od/{id}/reject
#
#   GET  /api/faculty/requests/dashboard-counts   (widget data)
#
# Role restriction: faculty only sees requests from students in their
# own department (or class-incharge dept/year/section if applicable).
# Admin/HOD may pass dept filtering implicitly too since they share
# teacher_required scope — but this module is faculty-focused per the
# Phase 1 spec, so admin/hod get an unrestricted (all-department) view.
# =============================================================
import logging

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

import database_faculty_requests as freq

log = logging.getLogger(__name__)


class DecisionReq(BaseModel):
    remarks: str = Field(default="", max_length=500)


def _resolve_scope(user: dict) -> dict:
    """Admin/HOD see all departments; faculty are scoped to their own
    department (or class-incharge dept/year/section)."""
    role = (user.get("role") or "").lower()
    if role in ("admin", "hod"):
        return {"department": None, "year": None, "section": None}
    fac_id = user.get("sub") or user.get("fac_id") or ""
    return freq.get_faculty_scope(fac_id)


def _is_class_incharge(user: dict) -> bool:
    """Admin/HOD are always treated as authorized. Faculty/teacher roles
    must be the registered Class In-Charge of a class to view or decide
    student leave/OD requests — plain subject-teacher faculty are not."""
    role = (user.get("role") or "").lower()
    if role in ("admin", "hod"):
        return True
    fac_id = user.get("sub") or user.get("fac_id") or ""
    try:
        import database as db
        return bool(db.get_faculty_incharge_class(fac_id))
    except Exception:
        log.exception("class-incharge check failed")
        return False


def _require_class_incharge(user: dict):
    if not _is_class_incharge(user):
        raise HTTPException(
            status_code=403,
            detail="Only the Class In-Charge faculty can view or decide "
                   "student leave/OD requests. Subject-teacher faculty "
                   "do not have this access.",
        )


def register_faculty_request_routes(app, get_current_user, teacher_required, _uname=None):

    try:
        freq.init_tables()
    except Exception as exc:
        log.warning("faculty request tables init skipped: %s", exc)

    def _actor(user: dict) -> str:
        if _uname:
            try:
                return _uname(user)
            except Exception:
                pass
        return user.get("sub") or user.get("fac_id") or "faculty"

    # ── LEAVE ───────────────────────────────────────────────
    @app.get("/api/faculty/requests/leave")
    def list_leave_requests(status: str = None, user: dict = Depends(teacher_required)):
        try:
            _require_class_incharge(user)
            scope = _resolve_scope(user)
            return {"requests": freq.list_leave_requests(scope, status)}
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("list_leave_requests failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/faculty/requests/leave/{req_id}")
    def get_leave_request(req_id: int, user: dict = Depends(teacher_required)):
        _require_class_incharge(user)
        record = freq.get_leave_request(req_id)
        if not record:
            raise HTTPException(status_code=404, detail="Leave request not found")
        return record

    @app.post("/api/faculty/requests/leave/{req_id}/approve")
    def approve_leave_request(req_id: int, payload: DecisionReq = DecisionReq(),
                               user: dict = Depends(teacher_required)):
        _require_class_incharge(user)
        record = freq.decide_leave_request(req_id, "Approved", _actor(user), payload.remarks,
                                            decided_by_role=(user.get("role") or "").lower())
        if not record:
            raise HTTPException(status_code=404, detail="Leave request not found or already decided")
        return record

    @app.post("/api/faculty/requests/leave/{req_id}/reject")
    def reject_leave_request(req_id: int, payload: DecisionReq = DecisionReq(),
                              user: dict = Depends(teacher_required)):
        _require_class_incharge(user)
        record = freq.decide_leave_request(req_id, "Rejected", _actor(user), payload.remarks,
                                            decided_by_role=(user.get("role") or "").lower())
        if not record:
            raise HTTPException(status_code=404, detail="Leave request not found or already decided")
        return record

    # ── OD ──────────────────────────────────────────────────
    @app.get("/api/faculty/requests/od")
    def list_od_requests(status: str = None, user: dict = Depends(teacher_required)):
        try:
            _require_class_incharge(user)
            role = (user.get("role") or "").lower()
            # Server-side status alias: the frontend can keep calling
            # ?status=Pending regardless of role. Faculty queue sees raw
            # 'Pending' rows (awaiting their decision); HOD queue is
            # translated to 'Forwarded' (awaiting their decision) — HOD
            # should never see a 'Pending' row, since that's stage 1 and
            # hasn't reached them yet (mirrors the same guard enforced in
            # hod_decide_od_request()).
            effective_status = status
            if role == "hod" and status == "Pending":
                effective_status = "Forwarded"
            scope = _resolve_scope(user)
            return {"requests": freq.list_od_requests(scope, effective_status)}
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("list_od_requests failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/faculty/requests/od/{req_id}")
    def get_od_request(req_id: int, user: dict = Depends(teacher_required)):
        _require_class_incharge(user)
        record = freq.get_od_request(req_id)
        if not record:
            raise HTTPException(status_code=404, detail="OD request not found")
        return record

    @app.post("/api/faculty/requests/od/{req_id}/approve")
    def approve_od_request(req_id: int, payload: DecisionReq = DecisionReq(),
                            user: dict = Depends(teacher_required)):
        _require_class_incharge(user)
        role = (user.get("role") or "").lower()
        if role == "hod":
            record = freq.hod_decide_od_request(req_id, "Approved", _actor(user), payload.remarks)
            if not record:
                raise HTTPException(
                    status_code=409,
                    detail="Request is not awaiting HOD approval (either still "
                           "pending faculty review, or already finalized).",
                )
        else:
            record = freq.faculty_decide_od_request(req_id, "Approved", _actor(user), payload.remarks)
            if not record:
                raise HTTPException(status_code=404, detail="OD request not found or already decided")
        return record

    @app.post("/api/faculty/requests/od/{req_id}/reject")
    def reject_od_request(req_id: int, payload: DecisionReq = DecisionReq(),
                           user: dict = Depends(teacher_required)):
        _require_class_incharge(user)
        role = (user.get("role") or "").lower()
        if role == "hod":
            record = freq.hod_decide_od_request(req_id, "Rejected", _actor(user), payload.remarks)
            if not record:
                raise HTTPException(
                    status_code=409,
                    detail="Request is not awaiting HOD approval (either still "
                           "pending faculty review, or already finalized).",
                )
        else:
            record = freq.faculty_decide_od_request(req_id, "Rejected", _actor(user), payload.remarks)
            if not record:
                raise HTTPException(status_code=404, detail="OD request not found or already decided")
        return record

    # ── Dashboard widgets ───────────────────────────────────
    @app.get("/api/faculty/requests/dashboard-counts")
    def faculty_request_dashboard_counts(user: dict = Depends(teacher_required)):
        try:
            role = (user.get("role") or "").lower()
            if not _is_class_incharge(user):
                # Subject-teacher-only faculty have no approval queue at all.
                return {"pending_leave_requests": 0, "pending_od_requests": 0,
                        "pending_hod_od": 0, "approved_requests_today": 0,
                        "rejected_requests_today": 0}
            scope = _resolve_scope(user)
            counts = freq.get_request_counts(scope)
            if role == "hod":
                # HOD's "pending OD" KPI should mean "awaiting my decision"
                # (status='Forwarded'), not the global Pending (stage 1,
                # awaiting faculty) count.
                counts["pending_od_requests"] = counts["pending_hod_od"]
            return counts
        except Exception as exc:
            log.exception("faculty_request_dashboard_counts failed")
            raise HTTPException(status_code=500, detail=str(exc))

    log.info("Faculty request management routes registered (/api/faculty/requests/*).")
