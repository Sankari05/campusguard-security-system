# =============================================================
# api_compliance.py — NEW FILE (additive only)
# Follows the exact register_<feature>_routes(app, ...) pattern
# used by api_hod.py / api_extras.py / api_override.py.
# =============================================================
import logging

from fastapi import Depends, HTTPException
from pydantic import BaseModel

import database_compliance as comp_db

log = logging.getLogger(__name__)


class ComplianceCreateReq(BaseModel):
    dept: str = None
    category: str = "NBA"
    title: str
    description: str = ""
    due_date: str = None
    assigned_to: str = None


class ComplianceUpdateReq(BaseModel):
    status: str = None
    dept: str = None
    category: str = None
    title: str = None
    description: str = None
    due_date: str = None
    assigned_to: str = None
    file_path: str = None


def register_compliance_routes(app, get_current_user, admin_required):

    try:
        comp_db.init_compliance_table()
    except Exception as exc:
        log.warning("compliance table init skipped: %s", exc)

    @app.get("/api/compliance/upcoming")
    def api_compliance_upcoming(days: int = 14, dept: str = None, user: dict = Depends(get_current_user)):
        """Items due within the next N days — backs the dashboard notice card."""
        try:
            role = (user.get("role") or "").lower()
            eff_dept = dept
            if role not in ("admin",) and not dept:
                eff_dept = user.get("dept")
            return comp_db.get_upcoming(days, eff_dept)
        except Exception as exc:
            log.exception("compliance upcoming fetch failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/compliance")
    def api_compliance_list(dept: str = None, category: str = None, status: str = None,
                             user: dict = Depends(get_current_user)):
        try:
            role = (user.get("role") or "").lower()
            eff_dept = dept
            if role not in ("admin",) and not dept:
                eff_dept = user.get("dept")
            return comp_db.list_items(eff_dept, category, status)
        except Exception as exc:
            log.exception("compliance list failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/compliance")
    def api_compliance_create(body: ComplianceCreateReq, user: dict = Depends(admin_required)):
        try:
            return comp_db.create_item(
                body.dept, body.category, body.title, body.description,
                body.due_date, body.assigned_to
            )
        except Exception as exc:
            log.exception("compliance create failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.put("/api/compliance/{item_id}")
    def api_compliance_update(item_id: int, body: ComplianceUpdateReq, user: dict = Depends(admin_required)):
        try:
            fields = body.dict(exclude={"status"}, exclude_none=True)
            updated = comp_db.update_item(item_id, status=body.status, **fields)
            if not updated:
                raise HTTPException(status_code=404, detail="Compliance item not found")
            return updated
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("compliance update failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.delete("/api/compliance/{item_id}")
    def api_compliance_delete(item_id: int, user: dict = Depends(admin_required)):
        try:
            ok = comp_db.delete_item(item_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Compliance item not found")
            return {"deleted": True, "id": item_id}
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("compliance delete failed")
            raise HTTPException(status_code=500, detail=str(exc))
