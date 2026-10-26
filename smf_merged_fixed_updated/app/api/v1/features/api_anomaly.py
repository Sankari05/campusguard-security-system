# =============================================================
# api_anomaly.py — NEW FILE (additive only)
# Follows the exact register_<feature>_routes(app, ...) pattern
# used by api_hod.py / api_extras.py / api_override.py.
# =============================================================
import logging

from fastapi import Depends, HTTPException

import database_anomaly as anomaly_db

log = logging.getLogger(__name__)


def register_anomaly_routes(app, get_current_user, teacher_required):

    # ensure the new table exists on startup (safe, CREATE TABLE IF NOT EXISTS)
    try:
        anomaly_db.init_anomaly_table()
    except Exception as exc:
        log.warning("anomaly table init skipped: %s", exc)

    @app.post("/api/anomaly/scan")
    def api_anomaly_scan(user: dict = Depends(teacher_required)):
        """Runs the pattern detectors and stores any new flags."""
        try:
            return anomaly_db.run_anomaly_scan()
        except Exception as exc:
            log.exception("anomaly scan failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/anomaly/flags")
    def api_anomaly_flags(dept: str = None, user: dict = Depends(get_current_user)):
        """Lists active (unresolved) anomaly flags, optionally filtered by dept."""
        try:
            eff_dept = dept
            role = (user.get("role") or "").lower()
            if role not in ("admin",) and not dept:
                eff_dept = user.get("dept")
            return anomaly_db.list_active_flags(eff_dept)
        except Exception as exc:
            log.exception("anomaly flags fetch failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.put("/api/anomaly/flags/{flag_id}/resolve")
    def api_anomaly_resolve(flag_id: int, user: dict = Depends(teacher_required)):
        try:
            ok = anomaly_db.resolve_flag(flag_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Flag not found")
            return {"resolved": True, "id": flag_id}
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("anomaly resolve failed")
            raise HTTPException(status_code=500, detail=str(exc))
