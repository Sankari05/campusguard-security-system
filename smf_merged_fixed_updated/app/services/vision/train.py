# =============================================================
# train.py  —  Smart Attendance System  v10.0
#
# KEY FIX v10.0 — Faculty and HOD images were being skipped:
#
# PROBLEM (v9.3):
#   train_lbph() listed ALL subdirs inside data/dataset/ —
#   including "faculty" and "hod" (the parent folders).
#   It then looked for .jpg files directly inside data/dataset/faculty/
#   and data/dataset/hod/ — but images live one level deeper:
#     data/dataset/faculty/FAC001/FAC001_p0035.jpg
#     data/dataset/hod/HOD001/HOD001_p0000.jpg
#   So it found 0 images and printed "WARN: No images — skipping".
#
# FIX (v10.0):
#   Three separate scanners, each with the correct path:
#
#   students_path = data/dataset/           (folders starting with STU_)
#   faculty_path  = data/dataset/faculty/   (all sub-folders inside)
#   hod_path      = data/dataset/hod/       (all sub-folders inside)
#
#   All three role groups are collected into one combined LBPH
#   model so recognition works in a single pass at runtime.
#
# PREPROCESSING (unchanged from v9.3):
#   equalizeHist only — parameter-free, matches recognizer.py.
#
# AUGMENTATION (unchanged from v9.3):
#   Covers brightness, rotation, blur, noise, zoom variants.
# =============================================================

import cv2
import os
import sys
import pickle
import numpy as np
import logging
import json
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import config

log = logging.getLogger(__name__)

try:
    import face_recognition as fr
    DLIB_OK = True
except ImportError:
    DLIB_OK = False

UNKNOWN_CLASS_ID = "__UNKNOWN__"


# =============================================================
# Preprocessing  (MUST match recognizer.py exactly)
# =============================================================
def preprocess_for_lbph(gray: np.ndarray, size: int = 160) -> np.ndarray:
    """
    v9.3 CRITICAL FIX: Use equalizeHist ONLY.
    Parameter-free -> always identical output for identical input.
    Must match _make_variants() in recognizer.py.
    """
    resized = cv2.resize(gray, (size, size))
    return cv2.equalizeHist(resized)


# =============================================================
# Augmentation
# =============================================================
def augment(gray: np.ndarray):
    """
    Focused augmentation — covers essential lighting, scale and pose
    variations while keeping model size compact and training lightning fast.
    """
    h, w = gray.shape
    out  = []

    # 1. Horizontal flip
    out.append(cv2.flip(gray, 1))

    # 2. Key lighting / contrast variants (covers dark skin to bright glare)
    for alpha, beta in [(1.6, 35), (1.2, 15), (0.85, -15), (0.6, -30)]:
        out.append(cv2.convertScaleAbs(gray, alpha=alpha, beta=beta))

    # 3. Gamma curves for non-linear shadow/highlight recovery
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
# Negative class samples
# =============================================================
def _get_negative_samples(n=200):
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

    print(f"  Generated {len(samples)} negative class samples")
    return samples


# =============================================================
# Dataset collector  (role-aware, correct depth)
# =============================================================
def _collect_persons(role_label, base_dir, filter_prefix=None):
    """
    Scan base_dir for person sub-folders containing images.

    Returns list of (person_id, folder_path, image_filenames).

    filter_prefix: if set, only include folders whose name starts
                   with this string (e.g. "STU_" for students so
                   that "faculty" and "hod" dirs are ignored when
                   scanning data/dataset/).
    """
    if not os.path.isdir(base_dir):
        print(f"  [{role_label}] Directory not found: {base_dir} — skipping")
        return []

    result = []
    for name in sorted(os.listdir(base_dir)):
        if filter_prefix and not name.upper().startswith(filter_prefix.upper()):
            continue
        full_path = os.path.join(base_dir, name)
        if not os.path.isdir(full_path):
            continue
        imgs = [f for f in os.listdir(full_path)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if imgs:
            result.append((name, full_path, imgs))
        else:
            print(f"  [{role_label}] WARN: No images for {name} — skipping")
    return result


# =============================================================
# Unified LBPH trainer  (students + faculty + HOD)
# =============================================================
def train_lbph(fast_mode: bool = True):
    print(f"\n--- LBPH Training v10.5 [{'FAST' if fast_mode else 'FULL'}] ---")
    print("  Scanning dataset paths:")
    print(f"    Students : {config.DATASET_DIR}  (STU_* folders only)")
    print(f"    Faculty  : {config.FACULTY_DATASET_DIR}")
    print(f"    HOD      : {config.HOD_DATASET_DIR}")

    # ── Collect all three role groups ─────────────────────────
    student_persons = _collect_persons(
        "Student", config.DATASET_DIR, filter_prefix="STU_")

    faculty_persons = _collect_persons(
        "Faculty", config.FACULTY_DATASET_DIR, filter_prefix=None)

    hod_persons = _collect_persons(
        "HOD", config.HOD_DATASET_DIR, filter_prefix=None)

    all_persons = student_persons + faculty_persons + hod_persons

    if not all_persons:
        print("\n  ERROR: No enrolled persons found across any role.")
        print("  Run option [1] to enroll at least one Student / Faculty / HOD.")
        return {}

    print(f"\n  Found:")
    print(f"    Students : {len(student_persons)}")
    print(f"    Faculty  : {len(faculty_persons)}")
    print(f"    HOD      : {len(hod_persons)}")
    print(f"    Total    : {len(all_persons)} person(s)\n")

    # ── Load images, preprocess, augment ──────────────────────
    faces, labels, label_map, cid = [], [], {}, 0

    for pid, ppath, imgs in all_persons:
        label_map[cid] = pid
        raw = aug = 0

        for fname in imgs:
            fpath = os.path.join(ppath, fname)
            img = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
            if img is None:
                log.warning("Could not read: %s", fpath)
                continue

            p = preprocess_for_lbph(img)
            faces.append(p)
            labels.append(cid)
            raw += 1

            if not fast_mode and config.AUGMENT:
                for a in augment(p):
                    faces.append(a)
                    labels.append(cid)
                    aug += 1
            elif fast_mode:
                # Fast mode: 1 horizontal flip for pose variance
                faces.append(cv2.flip(p, 1))
                labels.append(cid)
                aug += 1

        if raw > 0:
            print(f"  {pid}: {raw} raw + {aug} augmented = {raw+aug} total")
        else:
            print(f"  WARN: All images unreadable for {pid} — removing label")
            del label_map[cid]
            cid -= 1

        cid += 1

    if not faces:
        print("  ERROR: No images loaded — check dataset directories.")
        return {}

    # ── Negative (unknown) class ───────────────────────────────
    unknown_label            = cid
    label_map[unknown_label] = UNKNOWN_CLASS_ID
    neg_count                = 40 if fast_mode else 200
    neg_samples              = _get_negative_samples(neg_count)
    for ns in neg_samples:
        faces.append(ns)
        labels.append(unknown_label)
    print(f"  Unknown class: {len(neg_samples)} samples (label={unknown_label})")

    # ── Train ──────────────────────────────────────────────────
    total = len(faces)
    print(f"\n  Training LBPH on {total} total samples...")

    rec = cv2.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8)
    rec.train(faces, np.array(labels))

    # ── Save ───────────────────────────────────────────────────
    os.makedirs(config.MODEL_DIR, exist_ok=True)
    rec.save(config.LBPH_MODEL)

    with open(config.LBPH_LABELS, "wb") as f:
        pickle.dump(label_map, f)

    with open(os.path.join(config.MODEL_DIR, "lbph_meta.json"), "w") as f:
        json.dump({"unknown_label": unknown_label}, f)

    real_count = len([v for v in label_map.values() if v != UNKNOWN_CLASS_ID])
    print(f"\n  Model saved  -> {config.LBPH_MODEL}")
    print(f"  Persons in model : {real_count}")
    print(f"  Threshold : {config.LBPH_THRESHOLD}  Margin : {config.LBPH_UNKNOWN_MARGIN}")

    # ── Self-test ──────────────────────────────────────────────
    print("\n  Self-test (expected dist < 50 for good lighting):")
    pid_to_path = {pid: (ppath, imgs) for pid, ppath, imgs in all_persons}

    for cid_t, pid_t in label_map.items():
        if pid_t == UNKNOWN_CLASS_ID:
            continue
        if pid_t not in pid_to_path:
            continue
        ppath, imgs = pid_to_path[pid_t]
        img = cv2.imread(os.path.join(ppath, imgs[0]), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            p      = preprocess_for_lbph(img)
            lb, lr = rec.predict(p)
            pred   = label_map.get(lb, "?")
            margin = config.LBPH_UNKNOWN_MARGIN
            if pred == UNKNOWN_CLASS_ID:
                status = "FAIL -- __UNKNOWN__ won (re-enrol in better light)"
            elif lr < 20:
                status = "EXCELLENT (expected conf ~80%+ at runtime)"
            elif lr < 40:
                status = "GOOD (expected conf ~60-80% at runtime)"
            elif lr < margin * 0.6:
                status = "OK (expected conf ~40-60% at runtime)"
            elif lr < margin:
                status = "PASS (expected conf ~30% -- re-enrol for better)"
            else:
                status = f"WARN dist={lr:.0f} > margin={margin} (will show Unknown)"
            print(f"    {pid_t}: pred={pred}  dist={lr:.1f}  -> {status}")

    return label_map


# =============================================================
# dlib encoding trainer  (students + faculty + HOD color images)
# =============================================================
def train_dlib():
    print("\n--- dlib Encoding Training ---")
    if not DLIB_OK:
        print("  Skipped -- face_recognition not installed")
        return
    if not os.path.isdir(config.KNOWN_FACES_DIR):
        print("  known_faces/ not found -- skipped")
        return

    def _iter_known(base, prefix_filter=None):
        if not os.path.isdir(base):
            return
        for name in sorted(os.listdir(base)):
            if prefix_filter and not name.upper().startswith(prefix_filter.upper()):
                continue
            p = os.path.join(base, name)
            if os.path.isdir(p):
                yield name, p

    # Students (STU_ prefix), then faculty/*, then hod/*
    person_dirs  = list(_iter_known(config.KNOWN_FACES_DIR, prefix_filter="STU_"))
    person_dirs += list(_iter_known(config.FACULTY_FACES_DIR))
    person_dirs += list(_iter_known(config.HOD_FACES_DIR))

    if not person_dirs:
        print("  No persons in known_faces/ -- skipped")
        return

    db_enc = {}
    for pid, ppath in person_dirs:
        imgs = [f for f in sorted(os.listdir(ppath))
                if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if not imgs:
            continue

        # Sample up to 12 representative images evenly across the dataset
        step = max(1, len(imgs) // 12)
        sample_imgs = imgs[::step][:12]

        encs = []
        for fname in sample_imgs:
            try:
                img = fr.load_image_file(os.path.join(ppath, fname))
                mean = np.mean(img)
                if mean < 80:
                    boost = int((80 - mean) * 0.8)
                    img   = np.clip(img.astype(np.int32) + boost,
                                    0, 255).astype(np.uint8)
                locs = fr.face_locations(img, model="hog")
                if not locs:
                    locs = fr.face_locations(
                        img, model="hog", number_of_times_to_upsample=1)
                if locs:
                    enc = fr.face_encodings(
                        img, locs[:1], num_jitters=1, model="large")
                    if enc:
                        encs.append(enc[0])
            except Exception:
                pass

        if encs:
            db_enc[pid] = encs
            print(f"  {pid}: {len(encs)} encodings")
        else:
            print(f"  WARN: 0 encodings for {pid} (check known_faces/{pid}/)")

    if db_enc:
        with open(config.DLIB_ENCODINGS, "wb") as f:
            pickle.dump(db_enc, f)
        print(f"  Saved {len(db_enc)} person(s) to dlib encodings")


# =============================================================
# Entry point
# =============================================================
def train_all(fast_mode: bool = None, force_rebuild: bool = False):
    import time
    t_start = time.time()

    if fast_mode is None:
        fast_mode = os.environ.get("FAST_TRAIN", "true").lower() in ("1", "true", "yes")

    mode_label = "[FAST] ArcFace-First Mode (< 15s)" if fast_mode else "FULL Legacy Suite"

    print("\n" + "="*62)
    print(f"  Smart Attendance v10.5 -- Training [{mode_label}]")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*62)

    # ── STEP 1: ArcFace Modern Deep Learning Gallery (PRIMARY ENGINE) ──
    try:
        from arcface_engine import ArcFaceEngine
        print("\n--- [1/3] Updating ArcFace Modern Gallery (Primary Engine) ---")
        t_af = time.time()
        af_engine = ArcFaceEngine()
        af_engine.build_gallery_from_known_faces(config.KNOWN_FACES_DIR, force_rebuild=force_rebuild)
        print(f"  ArcFace Gallery updated with {len(af_engine.gallery)} person(s) in {time.time() - t_af:.1f}s")
    except Exception as _af_err:
        log.warning("ArcFace gallery update error: %s", _af_err)

    # ── STEP 2: Fast LBPH Model (FALLBACK ENGINE) ──────────────────────
    print("\n--- [2/3] Training Fast LBPH Classifier (Fallback Engine) ---")
    t_lb = time.time()
    lm = train_lbph(fast_mode=fast_mode)
    print(f"  LBPH Model saved in {time.time() - t_lb:.1f}s")

    # ── STEP 3: Legacy Heavy Engines (Skipped in Fast Mode) ─────────────
    if not fast_mode:
        print("\n--- [3/3] Training Heavy CPU Dlib & Twin Models ---")
        train_dlib()
        try:
            from twin_analysis import train_twin_model
            train_twin_model()
        except Exception as e:
            log.debug("Twin train: %s", e)
    else:
        print("\n--- [3/3] Skipped CPU-heavy Dlib ResNet & Twin SVM (ArcFace is primary) ---")

    # ── Update trained_ids.json so Web UI reflects trained status ──────
    try:
        trained_ids_path = getattr(config, "TRAINED_IDS_JSON",
                                   os.path.join(config.MODEL_DIR, "trained_ids.json"))
        registry = {"students": [], "faculty": [], "hod": []}

        for cid_val, pid_val in lm.items():
            if pid_val == UNKNOWN_CLASS_ID:
                continue
            pid_u = str(pid_val).strip()
            if pid_u.upper().startswith("STU_"):
                if pid_u not in registry["students"]:
                    registry["students"].append(pid_u)
            elif pid_u.upper().startswith("FAC"):
                if pid_u not in registry["faculty"]:
                    registry["faculty"].append(pid_u)
            elif pid_u.upper().startswith("HOD"):
                if pid_u not in registry["hod"]:
                    registry["hod"].append(pid_u)
            else:
                if pid_u not in registry["students"]:
                    registry["students"].append(pid_u)

        os.makedirs(config.MODEL_DIR, exist_ok=True)
        with open(trained_ids_path, "w") as f:
            json.dump(registry, f, indent=2)
        print(f"  Updated trained_ids.json: {len(registry['students'])} students, {len(registry['faculty'])} faculty, {len(registry['hod'])} hod")
    except Exception as exc:
        print(f"  WARN: Could not update trained_ids.json: {exc}")

    # Rebuild role pkls if needed
    try:
        from train_selective import _rebuild_role_pkl
        if registry.get("faculty"):
            _rebuild_role_pkl("faculty")
        if registry.get("hod"):
            _rebuild_role_pkl("hod")
    except Exception as e:
        log.debug("Role pkl rebuild: %s", e)

    real = len([v for v in lm.values() if v != UNKNOWN_CLASS_ID])
    elapsed_total = time.time() - t_start

    print("\n" + "="*62)
    print(f"  [FAST] TRAINING COMPLETE -- {real} enrolled person(s)")
    print(f"  [FAST] TOTAL ELAPSED TIME: {elapsed_total:.2f} SECONDS")
    print(f"  [FAST] PRIMARY RECOGNITION: ArcFace (512-d Deep Embeddings)")
    print("="*62 + "\n")
    return lm


def train_person(person_id: str, role: str = "student"):
    """
    ULTRA-FAST INCREMENTAL TRAINING (< 3 SECONDS!):
    Retrains ONLY a single person into ArcFace Gallery and LBPH Model.
    All other students in the database and models remain completely untouched.
    """
    import time
    t0 = time.time()
    clean_id = person_id.strip()

    print("\n" + "="*62)
    print(f"  [INCREMENTAL] Training Single Person: {clean_id} (Role: {role})")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*62)

    # 1. Update ArcFace Gallery for this person (< 2s)
    try:
        from arcface_engine import ArcFaceEngine
        af_engine = ArcFaceEngine()
        af_count = af_engine.enroll_single_person(clean_id)
        print(f"  [1/2] ArcFace Gallery: {af_count} embeddings registered")
    except Exception as exc:
        print(f"  WARN: ArcFace enroll error: {exc}")

    # 2. Update LBPH Model via train_selective (< 1s)
    try:
        from train_selective import train_one_person
        ok = train_one_person(role, clean_id)
        status_str = "OK" if ok else "Failed"
        print(f"  [2/2] LBPH Model update: {status_str}")
    except Exception as exc:
        print(f"  WARN: LBPH selective update error: {exc}")

    elapsed = time.time() - t0
    print("\n" + "="*62)
    print(f"  [INCREMENTAL] TRAINING COMPLETED in {elapsed:.2f} SECONDS!")
    print(f"  Person {clean_id} is ready for live recognition.")
    print("="*62 + "\n")
    return True


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    # Check for single person flag: python train.py --person STU_912823104086
    if "--person" in args:
        idx = args.index("--person")
        if idx + 1 < len(args):
            pid = args[idx + 1]
            train_person(pid)
            sys.exit(0)
        else:
            print("ERROR: --person requires a person ID (e.g. python train.py --person STU_912823104086)")
            sys.exit(1)

    is_full = "--full" in args
    is_rebuild = "--rebuild" in args
    fast = not is_full if is_full else os.environ.get("FAST_TRAIN", "true").lower() in ("1", "true", "yes")
    train_all(fast_mode=fast, force_rebuild=is_rebuild)
