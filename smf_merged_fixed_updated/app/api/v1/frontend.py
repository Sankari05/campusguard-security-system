"""
app.api.v1.frontend
Router serving frontend HTML portals (admin, hod, faculty, student) and static client assets.
"""

import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
from app.core import config

router = APIRouter(tags=["Frontend & Static Portals"])
frontend_dir = os.path.join(config.BASE_DIR, "frontend")


def _serve_file(filename: str, media_type: str = "text/plain", no_cache: bool = True):
    path = os.path.join(frontend_dir, filename)
    if not os.path.exists(path):
        return HTMLResponse(f"<h2>{filename} not found</h2>", 404)
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    } if no_cache else {}
    return FileResponse(path, media_type=media_type, headers=headers)


dist_dir = os.path.join(frontend_dir, "dist")
dist_index = os.path.join(dist_dir, "index.html")
dist_assets = os.path.join(dist_dir, "assets")


def _serve_portal(subpath: str = ""):
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    p = os.path.join(frontend_dir, "admin.html")
    if os.path.exists(p):
        return FileResponse(p)
    return FileResponse(os.path.join(frontend_dir, "index.html"))


# ── Portal HTML Routes (Authentic Light Theme) ─────────────────
@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin.html", response_class=HTMLResponse)
def serve_admin():
    return _serve_file("admin.html", "text/html")


@router.get("/hod", response_class=HTMLResponse)
@router.get("/hod.html", response_class=HTMLResponse)
def serve_hod():
    return _serve_file("hod.html", "text/html")


@router.get("/faculty", response_class=HTMLResponse)
@router.get("/faculty.html", response_class=HTMLResponse)
def serve_faculty():
    return _serve_file("faculty.html", "text/html")


@router.get("/attendance", response_class=HTMLResponse)
@router.get("/attendance.html", response_class=HTMLResponse)
def serve_attendance_html():
    return _serve_file("attendance.html", "text/html")


@router.get("/student", response_class=HTMLResponse)
@router.get("/student.html", response_class=HTMLResponse)
def serve_student_portal():
    return _serve_file("student.html", "text/html")


@router.get("/", response_class=HTMLResponse)
def frontend_root():
    return _serve_file("admin.html", "text/html")


# ── React SPA Static Assets & Route ──────────────────────────
@router.get("/app", response_class=HTMLResponse)
@router.get("/spa", response_class=HTMLResponse)
@router.get("/spa/{subpath:path}", response_class=HTMLResponse)
def serve_spa(subpath: str = ""):
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return _serve_file("admin.html", "text/html")


@router.get("/assets/{filename:path}")
def serve_spa_assets(filename: str):
    p = os.path.join(dist_assets, filename)
    if os.path.exists(p):
        media = "text/css" if filename.endswith(".css") else "application/javascript" if filename.endswith(".js") else "application/octet-stream"
        return FileResponse(p, media_type=media)
    return HTMLResponse("Asset not found", 404)


# ── Modular ES6 Javascript Route ─────────────────────────────
@router.get("/js/{filename:path}")
def serve_modular_js(filename: str):
    p = os.path.join(frontend_dir, "js", filename)
    if os.path.exists(p):
        return FileResponse(p, media_type="application/javascript")
    return HTMLResponse(f"// JS Module {filename} not found", 404)


# ── Static JS & CSS Assets ───────────────────────────────────
@router.get("/style.css")
def serve_css():
    return _serve_file("style.css", "text/css")


@router.get("/app.js")
def serve_js():
    return _serve_file("app.js", "application/javascript")


@router.get("/features.js")
def serve_features_js():
    return _serve_file("features.js", "application/javascript")


@router.get("/features.css")
def serve_features_css():
    return _serve_file("features.css", "text/css")


@router.get("/enroll_roles.js")
def serve_enroll_roles_js():
    return _serve_file("enroll_roles.js", "application/javascript")


@router.get("/edudrill.js")
def serve_edudrill_js():
    return _serve_file("edudrill.js", "application/javascript")


@router.get("/edudrill.css")
def serve_edudrill_css():
    return _serve_file("edudrill.css", "text/css")


@router.get("/attendance.css")
def serve_attendance_css():
    return _serve_file("attendance.css", "text/css")


@router.get("/attendance.js")
def serve_attendance_js():
    return _serve_file("attendance.js", "application/javascript")


@router.get("/hod_students.js")
def serve_hod_students_js():
    return _serve_file("hod_students.js", "application/javascript")


@router.get("/academics.js")
def serve_academics_js():
    return _serve_file("academics.js", "application/javascript")


@router.get("/compliance.js")
def serve_compliance_js():
    return _serve_file("compliance.js", "application/javascript")


@router.get("/student.js")
def serve_student_js():
    return _serve_file("student.js", "application/javascript")


@router.get("/student.css")
def serve_student_css():
    return _serve_file("student.css", "text/css")


@router.get("/frontend_otp_patch.js")
def serve_otp_js():
    return _serve_file("frontend_otp_patch.js", "application/javascript")
