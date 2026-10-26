

# =============================================================
# config.py  —  Smart Attendance System  v9.3
# =============================================================
import os, platform, secrets

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR        = os.path.join(BASE_DIR, "data")
DATASET_DIR     = os.path.join(DATA_DIR, "dataset")
KNOWN_FACES_DIR = os.path.join(DATA_DIR, "known_faces")
MODEL_DIR       = os.path.join(BASE_DIR, "models")
ATTENDANCE_DIR  = os.path.join(BASE_DIR, "attendance")
LOG_DIR         = os.path.join(BASE_DIR, "logs")
STATIC_DIR      = os.path.join(BASE_DIR, "static")
FRONTEND_DIR    = os.path.join(BASE_DIR, "frontend")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ── DATABASE STORAGE & ISOLATION ──────────────────────────────
# In enterprise architectures, DB files MUST NOT reside in public/web root.
# Default to data/attendance.db to prevent accidental static exposure.
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "attendance.db"))

def _migrate_legacy_db_if_needed():
    """Enterprise Safe Migration:
    If attendance.db exists in project root but not in data/,
    safely copy database + WAL/SHM files to the protected data/ folder.
    """
    root_db = os.path.join(BASE_DIR, "attendance.db")
    target_db = DB_PATH
    if os.path.exists(root_db) and not os.path.exists(target_db):
        try:
            import shutil
            os.makedirs(os.path.dirname(target_db), exist_ok=True)
            shutil.copy2(root_db, target_db)
            for suffix in ["-wal", "-shm"]:
                wal_src = root_db + suffix
                if os.path.exists(wal_src):
                    shutil.copy2(wal_src, target_db + suffix)
            print(f"[SECURITY] Successfully relocated attendance.db from root to protected directory: {target_db}")
        except Exception as e:
            print(f"[SECURITY WARNING] Failed to relocate database to {target_db}: {e}")

_migrate_legacy_db_if_needed()

LBPH_MODEL     = os.path.join(MODEL_DIR, "lbph_model.yml")
LBPH_LABELS    = os.path.join(MODEL_DIR, "lbph_labels.pkl")
DLIB_ENCODINGS = os.path.join(MODEL_DIR, "face_encodings.pkl")
TWIN_MODEL        = os.path.join(MODEL_DIR, "twin_model.pkl")
TRAINED_IDS_JSON  = os.path.join(MODEL_DIR, "trained_ids.json")  # selective-training registry
SKELETON_MODEL = os.path.join(MODEL_DIR, "skeleton_svm.pkl")

# ── FACULTY / HOD MODELS ──────────────────────────────────────
FACULTY_DATASET_DIR   = os.path.join(DATA_DIR, "dataset", "faculty")
HOD_DATASET_DIR       = os.path.join(DATA_DIR, "dataset", "hod")
FACULTY_FACES_DIR     = os.path.join(DATA_DIR, "known_faces", "faculty")
HOD_FACES_DIR         = os.path.join(DATA_DIR, "known_faces", "hod")
FACULTY_LBPH_MODEL    = os.path.join(MODEL_DIR, "faculty_face_model.pkl")
HOD_LBPH_MODEL        = os.path.join(MODEL_DIR, "hod_face_model.pkl")

# ── REST API & SECURITY SECRETS ───────────────────────────────
API_HOST               = os.environ.get("API_HOST", "0.0.0.0")
API_PORT               = int(os.environ.get("API_PORT", "8000"))

def _resolve_secret_key() -> str:
    """Enterprise Cryptographic Key Resolver:
    1. Read API_SECRET_KEY from environment or .env.
    2. If missing or equals a known weak default, auto-generate a cryptographically
       strong 256-bit token (secrets.token_hex(32)) and persist to .env for idempotency.
    """
    key = os.environ.get("API_SECRET_KEY", "").strip()
    insecure_defaults = {
        "",
        "smf-super-secret-key-change-in-prod!",
        "smf-secret",
        "secret",
        "changeme"
    }
    if not key or key in insecure_defaults:
        new_key = secrets.token_hex(32)
        env_path = os.path.join(BASE_DIR, ".env")
        try:
            lines = []
            replaced = False
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("API_SECRET_KEY="):
                            lines.append(f"API_SECRET_KEY={new_key}\n")
                            replaced = True
                        else:
                            lines.append(line)
            if not replaced:
                lines.append(f"\n# Auto-generated 256-bit cryptographic API secret key\nAPI_SECRET_KEY={new_key}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            os.environ["API_SECRET_KEY"] = new_key
            return new_key
        except Exception:
            os.environ["API_SECRET_KEY"] = new_key
            return new_key
    return key

API_SECRET_KEY         = _resolve_secret_key()
API_TOKEN_EXPIRY_HOURS = int(os.environ.get("API_TOKEN_EXPIRY_HOURS", "8"))
ADMIN_USERNAME         = os.environ.get("ADMIN_USERNAME",   "admin")
ADMIN_EMAIL            = os.environ.get("ADMIN_EMAIL",      "admin@college.edu").strip().lower()
ADMIN_PASSWORD         = os.environ.get("ADMIN_PASSWORD",   "Admin@123")
TEACHER_USERNAME       = os.environ.get("TEACHER_USERNAME", "teacher")
TEACHER_PASSWORD       = os.environ.get("TEACHER_PASSWORD", "teacher123")

# ── ROLE-BASED LOGIN CREDENTIALS ──────────────────────────────
HOD_PASSWORD           = os.environ.get("HOD_PASSWORD",      "hod123")
INCHARGE_PASSWORD      = os.environ.get("INCHARGE_PASSWORD", "incharge123")
FACULTY_DEFAULT_PASSWORD = os.environ.get("FACULTY_DEFAULT_PASSWORD", "fac@2025")

# F-12: CORS lockdown — read allowed origins from env var.
# Defaults include the local dev origins only (localhost variants used by
# the built-in server and common live-server / Vite dev ports).
# For production, set CORS_ORIGINS env var to your actual frontend domain only.
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,"
    "http://127.0.0.1:5500,http://localhost:5500,http://localhost:8080"
).split(",") if o.strip()]

# ── CAMERA ────────────────────────────────────────────────────
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480
CAMERA_FPS   = 30

# ── RECOGNITION THRESHOLDS v9.3 ───────────────────────────────
#
# HOW LBPH CONFIDENCE WORKS:
#   dist=0   → conf=100%  (perfect clone of training image)
#   dist=50  → conf= 50%  (with margin=100)
#   dist=100 → conf=  0%  (at boundary)
#   dist>120 → REJECTED
#
# GOAL: enrolled student should score dist 15-50 → conf 50-85%
# The preprocessing fix in train.py + recognizer.py achieves this.
#
# If you still see conf 30-40% after retraining:
#   → Lower LBPH_UNKNOWN_MARGIN to 70 in .env
#   → dist=50, margin=70 → conf = 1-50/70 = 29% → still low
#   → Better solution: re-enrol with 200 images (not 40)
#
LBPH_THRESHOLD          = int(os.environ.get("LBPH_THRESHOLD",      "120"))
LBPH_UNKNOWN_MARGIN     = int(os.environ.get("LBPH_UNKNOWN_MARGIN", "100"))
DLIB_DISTANCE           = float(os.environ.get("DLIB_DISTANCE",     "0.50"))
MIN_CONFIDENCE_PCT      = float(os.environ.get("MIN_CONFIDENCE_PCT", "25"))
MIN_FACE_SIZE           = (80, 80)
CONFIRM_FRAMES_REQUIRED = int(os.environ.get("CONFIRM_FRAMES_REQUIRED", "2"))
DEDUP_WINDOW_SECONDS    = 30
REQUIRE_BOTH_ENGINES    = False
SOLO_ENGINE_CONFIDENCE  = 0.25

# Quality gate — dark skin needs low variance threshold
FACE_VARIANCE_MIN = 25
FACE_QUALITY_MIN  = 0.02

# ── TWIN ─────────────────────────────────────────────────────
TWIN_FEATURE_DIM       = 124
TWIN_MIN_CONFIDENCE    = 0.65
TWIN_SKELETON_WEIGHT   = 0.35
TWIN_IRIS_WEIGHT       = 0.30
TWIN_PERIOCULAR_WEIGHT = 0.20
TWIN_GEOMETRY_WEIGHT   = 0.15

# ── LIVENESS ─────────────────────────────────────────────────
LIVENESS_ON              = os.environ.get("LIVENESS_ON", "true").lower() == "true"
LIVENESS_THRESHOLD       = float(os.environ.get("LIVENESS_THRESHOLD", "0.28"))
SKELETON_LIVENESS_WEIGHT = 0.35
EYE_AR_THRESHOLD         = 0.22
BLINK_CONSEC_FRAMES      = 2
BLINK_REQUIRED           = False

# ── ENROLMENT ─────────────────────────────────────────────────
SAMPLES_PER_PERSON = 200
AUGMENT            = True

# ── CLAHE ─────────────────────────────────────────────────────
CLAHE_LIMIT = 2.0   # v9.3: lighter CLAHE — matches training preprocessing
CLAHE_GRID  = (8, 8)

# ── ATTENDANCE ────────────────────────────────────────────────
SNAPSHOTS_PER_PERIOD  = 5
MIN_PRESENT_SNAPSHOTS = 2

DEFAULT_PERIODS = [
    {"name": "Period_1", "start": "08:55", "end": "09:45"},
    {"name": "Period_2", "start": "09:45", "end": "10:35"},
    # BREAK 10:35 – 10:55
    {"name": "Period_3", "start": "10:55", "end": "11:45"},
    {"name": "Period_4", "start": "11:45", "end": "12:35"},
    # LUNCH 12:35 – 13:35
    {"name": "Period_5", "start": "13:35", "end": "14:25"},
    {"name": "Period_6", "start": "14:25", "end": "15:15"},
    {"name": "Period_7", "start": "15:15", "end": "16:05"},
]

SMS_ENABLED   = os.environ.get("SMS_ENABLED",   "false").lower() == "true"
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
OS_NAME       = platform.system()

def init_dirs():
    for _d in [DATASET_DIR, KNOWN_FACES_DIR, MODEL_DIR,
               ATTENDANCE_DIR, LOG_DIR, STATIC_DIR, FRONTEND_DIR,
               os.path.join(BASE_DIR, "data"),
               FACULTY_DATASET_DIR, HOD_DATASET_DIR,
               FACULTY_FACES_DIR, HOD_FACES_DIR]:
        os.makedirs(_d, exist_ok=True)


# ── F-03: admin password bcrypt detection ─────────────────────
def is_bcrypt(s: str) -> bool:
    """Return True if *s* is a bcrypt hash (starts with '$2b$' or '$2a$').

    Used by api.py _check_admin_password() and auth_routes.py to decide
    whether config.ADMIN_PASSWORD holds a plain-text value (legacy .env)
    or an already-hashed value written by a previous password reset.
    """
    return isinstance(s, str) and s.startswith(("$2b$", "$2a$"))
