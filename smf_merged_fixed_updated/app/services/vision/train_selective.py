

# =============================================================
# train_selective.py  —  EduTrack Pro  v10.1
#
# Selective Training System
# ─────────────────────────
# Trains ONLY the specific user selected, without retraining
# everyone already in the model.
#
# Key Concepts
# ────────────
# 1. trained_ids.json  — metadata file tracks which IDs have
#    already been trained, per role.
#    Location: models/trained_ids.json
#    Structure: {"students": [...], "faculty": [...], "hod": [...]}
#
# 2. Existing model is LOADED, the new person's histogram is
#    APPENDED using cv2.face.LBPHFaceRecognizer::update(),
#    and the model is SAVED back.  All existing trained data
#    is preserved — nothing is retrained.
#
# 3. Dataset paths (must match train.py):
#    Students : data/dataset/STU_*/
#    Faculty  : data/dataset/faculty/<id>/
#    HOD      : data/dataset/hod/<id>/
#
# CLI Menu (invoked from main.py option [2])
# ──────────────────────────────────────────
#   Select Role For Training
#     1  HOD
#     2  Faculty
#     3  Student
#     0  Cancel
#
#   → Shows Already Trained / Not Trained lists
#   → User enters ID to train
#   → Only that ID is processed and appended
# =============================================================

import cv2
import os
import pickle
import json
import logging
import numpy as np
from datetime import datetime

import config

log = logging.getLogger(__name__)

# ── Path constants ─────────────────────────────────────────────
# Path from config (also exported there for other modules)
TRAINED_IDS_PATH = getattr(config, "TRAINED_IDS_JSON",
                           os.path.join(config.MODEL_DIR, "trained_ids.json"))
UNKNOWN_CLASS_ID = "__UNKNOWN__"

# How many synthetic unknown samples to include when building a
# brand-new model from scratch (first person trained).
NEGATIVE_SAMPLES_COUNT = 200


# =============================================================
# Metadata helpers  (trained_ids.json)
# =============================================================

def _load_trained_ids() -> dict:
    """
    Load the trained-IDs registry from disk.
    Returns {"students": [...], "faculty": [...], "hod": [...]}
    Creates an empty registry if the file does not exist.
    """
    if os.path.exists(TRAINED_IDS_PATH):
        try:
            with open(TRAINED_IDS_PATH, "r") as f:
                data = json.load(f)
            # Ensure all three keys are present
            for k in ("students", "faculty", "hod"):
                if k not in data:
                    data[k] = []
            return data
        except Exception as e:
            log.warning("Could not read trained_ids.json: %s — resetting.", e)
    return {"students": [], "faculty": [], "hod": []}


def _save_trained_ids(registry: dict):
    """Persist the registry to disk."""
    os.makedirs(config.MODEL_DIR, exist_ok=True)
    with open(TRAINED_IDS_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def _mark_as_trained(role_key: str, person_id: str):
    """Add person_id to the trained list for role_key and save."""
    reg = _load_trained_ids()
    if person_id not in reg[role_key]:
        reg[role_key].append(person_id)
    _save_trained_ids(reg)


# =============================================================
# Dataset scanner
# =============================================================

def _get_enrolled_ids(role: str) -> list:
    """
    Return list of IDs that have a dataset folder with at least
    one image, for the given role.

    role: "student" | "faculty" | "hod"
    """
    if role == "student":
        base = config.DATASET_DIR          # data/dataset/
        prefix = "STU_"
    elif role == "faculty":
        base = config.FACULTY_DATASET_DIR    # data/dataset/faculty/
        prefix = None
    else:                                  # hod
        base = config.HOD_DATASET_DIR      # data/dataset/hod/
        prefix = None

    if not os.path.isdir(base):
        return []

    ids = []
    for name in sorted(os.listdir(base)):
        if prefix and not name.upper().startswith(prefix.upper()):
            continue
        full = os.path.join(base, name)
        if not os.path.isdir(full):
            continue
        imgs = [f for f in os.listdir(full)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if imgs:
            ids.append(name)
    return ids


def _get_dataset_dir(role: str, person_id: str) -> str:
    """Return full path to the person's image folder."""
    if role == "student":
        return os.path.join(config.DATASET_DIR, person_id)
    elif role == "faculty":
        return os.path.join(config.FACULTY_DATASET_DIR, person_id)
    else:
        return os.path.join(config.HOD_DATASET_DIR, person_id)


# =============================================================
# Preprocessing  (MUST be identical to train.py / recognizer.py)
# =============================================================

def _preprocess(gray: np.ndarray, size: int = 160) -> np.ndarray:
    resized = cv2.resize(gray, (size, size))
    return cv2.equalizeHist(resized)


# =============================================================
# Augmentation  (same set as train.py)
# =============================================================

def _augment(gray: np.ndarray) -> list:
    """
    Focused augmentation — matches train.py.
    Provides robust lighting, contrast and rotation variants.
    """
    h, w = gray.shape
    out  = []

    # 1. Horizontal flip
    out.append(cv2.flip(gray, 1))

    # 2. Key lighting / contrast variants (covers dark skin to bright glare)
    for alpha, beta in [(1.6, 35), (1.2, 15), (0.85, -15), (0.6, -30)]:
        out.append(cv2.convertScaleAbs(gray, alpha=alpha, beta=beta))

    # 3. Gamma curves for shadow/highlight recovery
    for gamma in [1.5, 2.2]:
        tbl = np.array([min(255, int(((i / 255.0) ** (1.0 / gamma)) * 255))
                        for i in range(256)], np.uint8)
        out.append(cv2.LUT(gray, tbl))

    # 4. Subtle rotation variations (+/- 6 degrees)
    for angle in [-6, 6]:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        out.append(cv2.warpAffine(gray, M, (w, h), borderMode=cv2.BORDER_REPLICATE))

    # 5. Gaussian blur (simulates camera motion)
    out.append(cv2.GaussianBlur(gray, (3, 3), 0.8))

    # 6. CLAHE & Equalized variants
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    out.append(clahe.apply(gray))

    return out


# =============================================================
# Negative (unknown) samples
# =============================================================

def _get_negative_samples(n: int = NEGATIVE_SAMPLES_COUNT) -> list:
    """
    Synthetic unknown-face samples — vectorized for sub-second generation.
    Prevents mis-labelling strangers as enrolled students.
    """
    samples = []
    rng = np.random.RandomState(42)

    Y, X = np.ogrid[:160, :160]
    ellipse_mask = ((X - 80) / 56.0) ** 2 + ((Y - 80) / 72.0) ** 2 < 1.0

    for _ in range(n):
        base_val = rng.randint(25, 210)
        img = np.full((160, 160), base_val, dtype=np.int16)
        noise_ellipse = rng.randint(-40, 40, (160, 160))
        img[ellipse_mask] = np.clip(base_val + noise_ellipse[ellipse_mask], 10, 245)
        noise = rng.normal(0, 18, (160, 160)).astype(np.int16)
        img = np.clip(img + noise, 0, 255).astype(np.uint8)
        samples.append(cv2.equalizeHist(img))

    for _ in range(max(20, n // 5)):
        img = rng.randint(50, 210, (160, 160), dtype=np.uint8)
        img = cv2.GaussianBlur(img, (5, 5), 0)
        samples.append(cv2.equalizeHist(img))

    return samples


# =============================================================
# Load images for one person
# =============================================================

def _load_person_images(person_id: str, dataset_path: str,
                        augment: bool = True):
    """
    Read all .jpg/.jpeg/.png images from dataset_path, preprocess
    and optionally augment.  Returns list of preprocessed face arrays.
    """
    imgs = [f for f in sorted(os.listdir(dataset_path))
            if f.lower().endswith((".jpg", ".jpeg", ".png"))]

    if not imgs:
        return []

    faces = []
    for fname in imgs:
        fpath = os.path.join(dataset_path, fname)
        img = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            log.warning("Cannot read image: %s", fpath)
            continue
        p = _preprocess(img)
        faces.append(p)
        if augment and config.AUGMENT:
            faces.extend(_augment(p))

    return faces


# =============================================================
# Core: load existing model OR create fresh one
# =============================================================

def _load_or_create_model():
    """
    Returns (recognizer, label_map, next_label_id)

    label_map  : {int_label: person_id_string}
    next_label_id: int, next available label not yet used
    """
    rec = cv2.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8)

    model_exists = os.path.exists(config.LBPH_MODEL) and \
                   os.path.exists(config.LBPH_LABELS)

    if model_exists:
        try:
            rec.read(config.LBPH_MODEL)
            with open(config.LBPH_LABELS, "rb") as f:
                label_map = pickle.load(f)
            # next available integer label
            real_labels = [k for k, v in label_map.items()
                           if v != UNKNOWN_CLASS_ID]
            next_id = (max(real_labels) + 1) if real_labels else 0
            # unknown label should be just above next_id
            unk_labels = [k for k, v in label_map.items()
                          if v == UNKNOWN_CLASS_ID]
            unknown_label = unk_labels[0] if unk_labels else next_id + 1
            log.info("Loaded existing model: %d persons, next_id=%d",
                     len(real_labels), next_id)
            return rec, label_map, next_id, unknown_label, True
        except Exception as e:
            log.warning("Existing model unreadable (%s) — will create fresh.", e)

    # Brand new — return empty structures
    return rec, {}, 0, 1, False


# =============================================================
# Core: train one person and append to model
# =============================================================

# =============================================================
# Rebuild role-specific pkl  (HOD / Faculty)
# =============================================================

def _rebuild_role_pkl(role: str):
    """
    Rebuild the role-specific pkl bundle (hod_face_model.pkl or
    faculty_face_model.pkl) from ALL enrolled persons for that role.

    This is called automatically after train_one_person() for HOD / Faculty
    so that role_attendance_session.py always loads an up-to-date model.

    The pkl format is:  {"label_map": {int: str}, "yml_bytes": bytes}
    — identical to what enroll_hod.py / enroll_faculty.py produce.
    """
    import tempfile

    if role == "hod":
        dataset_base = config.HOD_DATASET_DIR
        model_path   = config.HOD_LBPH_MODEL
        role_label   = "HOD"
    else:
        dataset_base = config.FACULTY_DATASET_DIR
        model_path   = config.FACULTY_LBPH_MODEL
        role_label   = "Faculty"

    print(f"\n  Rebuilding {role_label} pkl model...", end=" ", flush=True)

    enrolled = _get_enrolled_ids(role)
    if not enrolled:
        print(f"\n  WARNING: No enrolled {role_label}s — pkl not rebuilt.")
        return

    rec = cv2.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8)

    all_faces  = []
    all_labels = []
    label_map  = {}   # {int_label: person_id}

    for lbl, pid in enumerate(enrolled):
        dpath = _get_dataset_dir(role, pid)
        if not os.path.isdir(dpath):
            continue
        faces = _load_person_images(pid, dpath, augment=True)
        if not faces:
            log.warning("_rebuild_role_pkl: no images for %s — skipping", pid)
            continue
        all_faces.extend(faces)
        all_labels.extend([lbl] * len(faces))
        label_map[lbl] = pid

    if not all_faces:
        print(f"\n  WARNING: No images found — {role_label} pkl not rebuilt.")
        return

    rec.train(all_faces, np.array(all_labels))

    os.makedirs(config.MODEL_DIR, exist_ok=True)

    # Save LBPH model to a temp yml, read raw bytes, delete temp file
    tmp_yml = model_path.replace(".pkl", "_tmp_rebuild.yml")
    try:
        rec.save(tmp_yml)
        with open(tmp_yml, "rb") as f:
            yml_bytes = f.read()
    finally:
        if os.path.exists(tmp_yml):
            os.remove(tmp_yml)

    with open(model_path, "wb") as f:
        pickle.dump({"label_map": label_map, "yml_bytes": yml_bytes}, f)

    print(f"done")
    print(f"  {role_label} pkl saved → {model_path}")
    print(f"  Persons in {role_label} pkl: {list(label_map.values())}")



def train_one_person(role: str, person_id: str) -> bool:
    """
    Train ONLY person_id and append/update in the shared LBPH model.

    Steps
    ─────
    1. Load (or create) existing model + label_map
    2. Check if person_id already has a label in label_map
       • If yes  → use their existing label (update, not re-add)
       • If no   → assign next available label
    3. Load images for person_id, preprocess + augment
    4. If model already exists: call rec.update() with new faces
       If model is brand new:   call rec.train() with new faces +
                                negative samples
    5. Save model + updated label_map
    6. Mark person as trained in trained_ids.json

    Returns True on success, False on failure.
    """
    dataset_path = _get_dataset_dir(role, person_id)

    if not os.path.isdir(dataset_path):
        print(f"\n  ERROR: Dataset folder not found: {dataset_path}")
        return False

    print(f"\n{'─'*55}")
    print(f"  Training model for: {person_id}  (role={role})")
    print(f"  Dataset: {dataset_path}")
    print(f"{'─'*55}")

    # ── 1. Load existing model ─────────────────────────────────
    rec, label_map, next_id, unknown_label, model_exists = \
        _load_or_create_model()

    # ── 2. Assign label ────────────────────────────────────────
    # Check if this person is already in the label map
    existing_label = None
    for lbl, pid in label_map.items():
        if pid == person_id:
            existing_label = lbl
            break

    if existing_label is not None:
        person_label = existing_label
        print(f"  Person already has label {person_label} — updating model")
    else:
        person_label = next_id
        # Make sure we don't collide with the unknown label
        if person_label >= unknown_label:
            unknown_label = person_label + 1
        label_map[person_label] = person_id
        print(f"  Assigning new label {person_label}")

    # ── 3. Load images ─────────────────────────────────────────
    print(f"  Loading images from dataset...", end=" ", flush=True)
    fast_mode = os.environ.get("FAST_TRAIN", "true").lower() in ("1", "true", "yes")
    faces = _load_person_images(person_id, dataset_path, augment=not fast_mode)

    if not faces:
        print(f"\n  ERROR: No images loaded from {dataset_path}")
        return False

    raw_count = len([f for f in os.listdir(dataset_path)
                     if f.lower().endswith((".jpg",".jpeg",".png"))])
    print(f"done")
    print(f"  Images found  : {raw_count} raw")
    print(f"  After augment : {len(faces)} total samples")

    labels_arr = np.array([person_label] * len(faces))

    # ── 4. Train or update ─────────────────────────────────────
    if not model_exists:
        # First person ever — train() needs at least 2 different labels.
        # Add negative class so we don't crash.
        print(f"\n  First person in model — building from scratch...")
        print(f"  Running LBPH training...", end=" ", flush=True)

        # Ensure unknown label is different from person_label
        unknown_label = person_label + 1
        label_map[unknown_label] = UNKNOWN_CLASS_ID

        neg = _get_negative_samples(NEGATIVE_SAMPLES_COUNT)
        all_faces  = faces  + neg
        all_labels = list(labels_arr) + [unknown_label]*len(neg)
        rec.train(all_faces, np.array(all_labels))
        print("done")
    else:
        # Model exists → update() appends new histogram data for this person.
        # Existing persons are NOT retrained.
        print(f"\n  Updating existing model (other persons untouched)...")
        print(f"  Running LBPH update...", end=" ", flush=True)
        rec.update(faces, labels_arr)
        print("done")

    # ── 5. Save model + labels ─────────────────────────────────
    os.makedirs(config.MODEL_DIR, exist_ok=True)

    print(f"  Updating model file...", end=" ", flush=True)
    rec.save(config.LBPH_MODEL)
    print("done")

    with open(config.LBPH_LABELS, "wb") as f:
        pickle.dump(label_map, f)

    # Save unknown_label to lbph_meta.json (needed by recognizer.py)
    meta_path = os.path.join(config.MODEL_DIR, "lbph_meta.json")
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as mf:
                meta = json.load(mf)
        except Exception:
            pass
    meta["unknown_label"] = unknown_label
    with open(meta_path, "w") as mf:
        json.dump(meta, mf)

    # ── 6. Mark as trained ─────────────────────────────────────
    role_key = {"student": "students", "faculty": "faculty", "hod": "hod"}[role]
    _mark_as_trained(role_key, person_id)

    # ── 7. Rebuild the role-specific pkl for HOD / Faculty ───────
    # The attendance session loads hod_face_model.pkl (for HOD) or
    # faculty_face_model.pkl (for Faculty) — these are SEPARATE from
    # lbph_model.yml.  Without rebuilding them here, the session keeps
    # loading a stale pkl that was last written at enrolment time,
    # causing "Unknown face detected" even after retraining via option [2].
    if role in ("hod", "faculty"):
        _rebuild_role_pkl(role)

    # ── 8. Update ArcFace Gallery incrementally (< 2 seconds) ─────────
    known_base = {
        "student": config.KNOWN_FACES_DIR,
        "faculty": config.FACULTY_FACES_DIR,
        "hod":     config.HOD_FACES_DIR,
    }.get(role, config.KNOWN_FACES_DIR)
    kf_dir = os.path.join(known_base, person_id)
    src_dir = kf_dir if os.path.isdir(kf_dir) else dataset_path

    try:
        from arcface_engine import ArcFaceEngine
        af_engine = ArcFaceEngine()
        af_count = af_engine.enroll_single_person(person_id, src_dir)
        if af_count > 0:
            print(f"  [ArcFace] Incremental Gallery updated for {person_id} ({af_count} vectors)")
    except Exception as af_err:
        log.warning("ArcFace selective enroll error: %s", af_err)

    # ── 9. Update dlib face encodings if available (skipped in fast mode) ─
    fast_mode = os.environ.get("FAST_TRAIN", "true").lower() in ("1", "true", "yes")
    if not fast_mode:
        try:
            import face_recognition as fr
            dlib_path = config.DLIB_ENCODINGS
            db_enc = {}
            if os.path.exists(dlib_path):
                try:
                    with open(dlib_path, "rb") as df:
                        db_enc = pickle.load(df)
                except Exception:
                    db_enc = {}

            if os.path.isdir(src_dir):
                c_imgs = [f for f in sorted(os.listdir(src_dir))
                          if f.lower().endswith((".jpg", ".jpeg", ".png"))]
                if c_imgs:
                    step = max(1, len(c_imgs) // 10)
                    encs = []
                    for fname in c_imgs[::step][:10]:
                        try:
                            im = fr.load_image_file(os.path.join(src_dir, fname))
                            locs = fr.face_locations(im, model="hog")
                            if locs:
                                e = fr.face_encodings(im, locs[:1], num_jitters=1, model="large")
                                if e:
                                    encs.append(e[0])
                        except Exception:
                            pass
                    if encs:
                        db_enc[person_id] = encs
                        with open(dlib_path, "wb") as df:
                            pickle.dump(db_enc, df)
                        print(f"  Updated dlib encodings ({len(encs)} vectors)")
        except Exception as dlib_err:
            log.debug("Selective dlib encoding skip: %s", dlib_err)
    else:
        print("  [FAST] Skipped heavy Dlib ResNet encoding (ArcFace updated)")

    # ── Summary ────────────────────────────────────────────────
    real_persons = [v for v in label_map.values() if v != UNKNOWN_CLASS_ID]
    print(f"\n  Training completed successfully!")
    print(f"  Model saved → {config.LBPH_MODEL}")
    print(f"  Total persons in model: {len(real_persons)}")

    # Quick self-test
    print(f"\n  Self-test...", end=" ", flush=True)
    imgs_for_test = [f for f in os.listdir(dataset_path)
                     if f.lower().endswith((".jpg",".jpeg",".png"))]
    if imgs_for_test:
        test_img = cv2.imread(
            os.path.join(dataset_path, imgs_for_test[0]),
            cv2.IMREAD_GRAYSCALE)
        if test_img is not None:
            p = _preprocess(test_img)
            lb, lr = rec.predict(p)
            pred   = label_map.get(lb, "?")
            if pred == UNKNOWN_CLASS_ID:
                print(f"WARN — predicted Unknown (dist={lr:.1f}) — "
                      f"re-enrol with more images in better lighting")
            elif lr < 20:
                print(f"EXCELLENT  pred={pred}  dist={lr:.1f}")
            elif lr < 40:
                print(f"GOOD       pred={pred}  dist={lr:.1f}")
            elif lr < 80:
                print(f"OK         pred={pred}  dist={lr:.1f}")
            else:
                print(f"PASS       pred={pred}  dist={lr:.1f}  "
                      f"(consider re-enrolling for better accuracy)")
    else:
        print("skipped (no test image found)")

    return True


# =============================================================
# Status display
# =============================================================

def _show_training_status(role: str, enrolled: list, trained: list):
    """Print a formatted Already-Trained / Not-Trained table."""
    not_trained = [pid for pid in enrolled if pid not in trained]

    width = 55
    print(f"\n{'═'*width}")
    rl = role.upper()
    print(f"  {rl} TRAINING STATUS")
    print(f"{'─'*width}")

    if trained:
        already = [pid for pid in enrolled if pid in trained]
        if already:
            print(f"  ✓ Already Trained  ({len(already)})")
            for pid in already:
                print(f"      {pid}")
    else:
        print(f"  ✓ Already Trained  (0)")
        print(f"      — none —")

    print(f"{'─'*width}")

    if not_trained:
        print(f"  ✗ Not Trained  ({len(not_trained)})")
        for pid in not_trained:
            dpath = _get_dataset_dir(role, pid)
            imgs  = [f for f in os.listdir(dpath)
                     if f.lower().endswith((".jpg",".jpeg",".png"))]
            print(f"      {pid}  ({len(imgs)} images)")
    else:
        print(f"  ✗ Not Trained  (0)")
        print(f"      — all enrolled persons are trained —")

    print(f"{'═'*width}")

    return not_trained



# =============================================================
# Interactive CLI  (called from main.py do_train)
# =============================================================

def selective_train_menu():
    """
    Interactive menu for selective training.
    - Shows a numbered list of ALL enrolled IDs (trained + untrained).
    - User picks a NUMBER or types the ID directly.
    - Students can type just the register number (STU_ auto-prefixed).
    - Trains ONLY that single person — all others stay untouched.
    """
    print(f"\n{'═'*55}")
    print(f"  Select Role For Training")
    print(f"{'═'*55}")
    print(f"  1  HOD")
    print(f"  2  Faculty")
    print(f"  3  Student")
    print(f"  0  Cancel")
    print(f"{'─'*55}")

    choice = input("  Enter choice: ").strip()

    if choice == "0" or choice.lower() == "cancel":
        print("  Training cancelled.")
        return

    if choice == "1" or choice.lower() == "hod":
        role       = "hod"
        role_key   = "hod"
        role_label = "HOD"
    elif choice == "2" or choice.lower() in ("faculty",):
        role       = "faculty"
        role_key   = "faculty"
        role_label = "Faculty"
    elif choice == "3" or choice.lower() == "student":
        role       = "student"
        role_key   = "students"
        role_label = "Student"
    else:
        print(f"  Invalid choice '{choice}'. Please enter 1, 2, or 3.")
        return

    # ── Gather enrolled & trained IDs ─────────────────────────
    enrolled = _get_enrolled_ids(role)

    if not enrolled:
        base = {
            "student": config.DATASET_DIR,
            "faculty": config.FACULTY_DATASET_DIR,
            "hod":     config.HOD_DATASET_DIR,
        }[role]
        print(f"\n  No enrolled {role_label}s found.")
        print(f"  Dataset directory: {base}")
        print(f"  Run option [1] to enrol a {role_label} first.")
        return

    registry = _load_trained_ids()
    trained  = registry.get(role_key, [])

    # ── Show numbered status table ─────────────────────────────
    number_map = _show_numbered_status(role, enrolled, trained, role_label)

    # ── Prompt ────────────────────────────────────────────────
    print(f"\n  Enter the NUMBER shown above, or type the ID directly.")
    if role == "student":
        print(f"  (Students: you can type just the register number, e.g. 912623104086)")
    print(f"  Press ENTER with no input to cancel.")
    raw = input("  → ").strip()

    if not raw:
        print("  No input. Training cancelled.")
        return

    # ── Resolve input → exact enrolled ID ─────────────────────
    exact_pid = _resolve_id(raw, role, enrolled, number_map, role_label)
    if exact_pid is None:
        return  # error already printed

    # ── Show what will happen ──────────────────────────────────
    dpath     = _get_dataset_dir(role, exact_pid)
    img_count = len([f for f in os.listdir(dpath)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))])
    is_update = exact_pid in trained

    print(f"\n{'─'*55}")
    print(f"  Ready to train:")
    print(f"    ID     : {exact_pid}")
    print(f"    Role   : {role_label}")
    print(f"    Images : {img_count}")
    print(f"    Action : {'UPDATE existing model entry' if is_update else 'ADD to model as new person'}")
    print(f"    Note   : Only THIS person is trained.")
    print(f"             All currently trained persons are untouched.")
    print(f"{'─'*55}")
    confirm = input("  Proceed? (Y/n): ").strip().lower()
    if confirm == "n":
        print("  Training cancelled.")
        return

    # ── Train only this person ─────────────────────────────────
    ok = train_one_person(role, exact_pid)

    if ok:
        print(f"\n  ✓ {role_label} '{exact_pid}' trained successfully.")
        print(f"  Registry: {TRAINED_IDS_PATH}")
    else:
        print(f"\n  ✗ Training failed for '{exact_pid}'. See messages above.")

    # ── Train another? ────────────────────────────────────────
    again = input(f"\n  Train another {role_label}? (y/N): ").strip().lower()
    if again == "y":
        selective_train_menu()


# =============================================================
# Numbered status display
# =============================================================

def _show_numbered_status(role: str, enrolled: list,
                          trained: list, role_label: str) -> dict:
    """
    Print all enrolled IDs as a numbered list.
    Trained ones are marked ✓, untrained ones ✗.
    Returns number_map {str_number: person_id}.
    """
    width = 55
    already     = [p for p in enrolled if p in trained]
    not_trained = [p for p in enrolled if p not in trained]

    print(f"\n{'═'*width}")
    print(f"  {role_label.upper()} TRAINING STATUS")
    print(f"{'─'*width}")

    idx = 1
    number_map = {}

    if already:
        print(f"  ✓ Already Trained ({len(already)}):")
        for pid in already:
            dpath = _get_dataset_dir(role, pid)
            imgs  = [f for f in os.listdir(dpath)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            print(f"    [{idx}] {pid}  ({len(imgs)} images)")
            number_map[str(idx)] = pid
            idx += 1
    else:
        print(f"  ✓ Already Trained (0)  — none —")

    print(f"{'─'*width}")

    if not_trained:
        print(f"  ✗ Not Yet Trained ({len(not_trained)}):")
        for pid in not_trained:
            dpath = _get_dataset_dir(role, pid)
            imgs  = [f for f in os.listdir(dpath)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            print(f"    [{idx}] {pid}  ({len(imgs)} images)  ← needs training")
            number_map[str(idx)] = pid
            idx += 1
    else:
        print(f"  ✗ Not Yet Trained (0)  — all enrolled persons are trained —")

    print(f"{'═'*width}")
    return number_map


# =============================================================
# ID resolver: number / full ID / register-only
# =============================================================

def _resolve_id(raw: str, role: str, enrolled: list,
                number_map: dict, role_label: str):
    """
    Try to match user input to an enrolled person_id:
      1. Match against the displayed number list
      2. Match exact ID (case-insensitive)
      3. For students: auto-prefix STU_ and retry
    Returns the exact ID string, or None on failure.
    """
    raw_stripped = raw.strip()

    # 1. Number from list
    if raw_stripped in number_map:
        return number_map[raw_stripped]

    # Build case-insensitive lookup
    enrolled_upper = {p.upper(): p for p in enrolled}
    raw_upper      = raw_stripped.upper()

    # 2. Exact ID (case-insensitive)
    if raw_upper in enrolled_upper:
        return enrolled_upper[raw_upper]

    # 3. Student shorthand: "912623104086" → try "STU_912623104086"
    if role == "student" and not raw_upper.startswith("STU_"):
        prefixed = f"STU_{raw_upper}"
        if prefixed in enrolled_upper:
            return enrolled_upper[prefixed]

    # 4. Partial match (last resort) — match if input is a suffix of an ID
    matches = [pid for uid, pid in enrolled_upper.items()
               if uid.endswith(raw_upper) or raw_upper in uid]
    if len(matches) == 1:
        print(f"  (Matched '{raw}' → '{matches[0]}')")
        return matches[0]
    if len(matches) > 1:
        print(f"\n  Ambiguous input '{raw}' matches multiple IDs:")
        for m in matches:
            print(f"    {m}")
        print(f"  Please be more specific.")
        return None

    # Not found
    print(f"\n  ERROR: '{raw}' not found in the enrolled {role_label} list.")
    if role == "student":
        print(f"  Accepted formats:")
        print(f"    • List number   (e.g.  1  or  2)")
        print(f"    • Full ID       (e.g.  STU_912623104086)")
        print(f"    • Register No   (e.g.  912623104086)")
    else:
        print(f"  Accepted formats:")
        print(f"    • List number   (e.g.  1  or  2)")
        print(f"    • Full ID       (e.g.  FAC001  or  HOD001)")
    print(f"\n  Enrolled {role_label}s:")
    for p in enrolled:
        print(f"    {p}")
    print(f"\n  Run option [1] to enrol this {role_label} first if they are missing.")
    return None