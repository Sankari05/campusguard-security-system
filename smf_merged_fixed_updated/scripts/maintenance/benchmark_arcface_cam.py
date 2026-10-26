import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import app  # noqa: F401

# ==============================================================================
# benchmark_arcface_cam.py — Real-time Live Camera Benchmark (SCRFD + ArcFace)
#
# Tests the modern face recognition pipeline directly against your webcam:
#   - SCRFD face detection with 5-point alignment
#   - ArcFace 512-d normalized embeddings
#   - Quality check (blur, size, angle)
#   - Real-time FPS and latency counter
#   - Non-destructive test script (does NOT modify database or API)
#
# Usage:
#   .\venv311\Scripts\python.exe benchmark_arcface_cam.py
#
# Controls:
#   Q  — Exit
# ==============================================================================

import time
import sqlite3
import cv2
import numpy as np
from arcface_engine import ArcFaceEngine

# Load student name dictionary from database for pretty display
student_names = {}
try:
    conn = sqlite3.connect("data/attendance.db")
    cur = conn.cursor()
    for row in cur.execute("SELECT student_id, name, department, section FROM students").fetchall():
        student_names[row[0]] = {
            "name": row[1],
            "dept": row[2],
            "sec": row[3]
        }
    conn.close()
    print(f"[OK] Loaded {len(student_names)} student names from database.")
except Exception as e:
    print(f"[WARN] DB lookup failed: {e}")

print("\n--- Initializing SCRFD + ArcFace Engine on Intel CPU ---")
t0 = time.time()
engine = ArcFaceEngine(
    det_model_path="models/arcface/det_500m.onnx",
    rec_model_path="models/arcface/w600k_mbf.onnx",
    gallery_path="models/arcface_gallery.pkl",
    conf_threshold=0.50,
    sim_threshold=0.52
)

# If gallery not built or empty, build it
if not engine.gallery:
    print("[INFO] Building gallery from data/known_faces/...")
    engine.build_gallery_from_known_faces("data/known_faces")

print(f"[OK] Engine ready in {(time.time() - t0)*1000:.1f}ms with {len(engine.gallery)} enrolled person(s).")

# Open Webcam
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Cannot open webcam index 0. Try closing other camera apps.")
    exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

print("\nCamera started! Press 'Q' in the window to quit.\n")

fps_history = []

while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        time.sleep(0.01)
        continue

    display = frame.copy()
    t_start = time.time()

    # Process frame through modern pipeline
    detections = engine.process_frame(frame)

    t_end = time.time()
    latency_ms = (t_end - t_start) * 1000.0
    fps = 1.0 / max(t_end - t_start, 0.001)
    fps_history.append(fps)
    if len(fps_history) > 30:
        fps_history.pop(0)
    avg_fps = np.mean(fps_history)

    for det in detections:
        box = det["box"].astype(int)
        x1, y1, x2, y3_h = box[0], box[1], box[2], box[3]
        kps = det["kps"]
        q_ok = det["quality_ok"]
        pid = det["person_id"]
        sim = det["similarity"]

        # Draw 5 landmark points
        for pt in kps:
            px, py = int(pt[0]), int(pt[1])
            cv2.circle(display, (px, py), 2, (0, 255, 255), -1)

        if not q_ok:
            # Low quality / blurry
            color = (0, 165, 255)  # Orange
            cv2.rectangle(display, (x1, y1), (x2, y3_h), color, 2)
            cv2.putText(display, f"Poor Quality: {det['reason']}", (x1, max(18, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        elif pid is not None:
            # Recognized student
            color = (0, 220, 60)  # Bright Green
            st_info = student_names.get(pid, {})
            name = st_info.get("name", pid)
            sec = st_info.get("sec", "")
            label = f"{name} ({int(sim * 100)}%)"

            cv2.rectangle(display, (x1, y1), (x2, y3_h), color, 2)
            cv2.rectangle(display, (x1, max(0, y1 - 28)), (x2, y1), color, -1)
            cv2.putText(display, label, (x1 + 4, max(14, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        else:
            # Unknown stranger
            color = (0, 0, 220)  # Red
            label = f"Unknown ({int(sim * 100)}%)"
            cv2.rectangle(display, (x1, y1), (x2, y3_h), color, 2)
            cv2.putText(display, label, (x1 + 4, max(18, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    # Top stats banner
    cv2.rectangle(display, (0, 0), (display.shape[1], 36), (20, 20, 25), -1)
    status_text = f"ArcFace + SCRFD (CPU)  |  {latency_ms:.1f}ms  |  {avg_fps:.1f} FPS  |  Faces: {len(detections)}"
    cv2.putText(display, status_text, (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 180), 1)

    cv2.imshow("EduTrack - ArcFace Live Camera Benchmark (Press Q to quit)", display)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == ord('Q') or key == 27:
        break

cap.release()
cv2.destroyAllWindows()
print("[OK] Benchmark closed cleanly.")
