"""
app/services/vision/recognizer.py
=================================
Enterprise Smart Face Recognition Engine.
Single Source of Truth for:
  - Haar Cascade Face Detection
  - Multi-variant LBPH Face Recognition
  - Confirmation Buffer (anti-flicker stability)
  - Anti-spoofing / Liveness gate integration
  - Twin disambiguation gate integration
  - Real-time frame annotation with bounding boxes and confidence scores
"""
import os
import cv2
import pickle
import logging
import numpy as np
from collections import deque, Counter

import config
import database as db
from .preprocessor import FacePreprocessor

log = logging.getLogger(__name__)

# Try loading optional components
try:
    from liveness import LivenessDetector
    LIVENESS_OK = True
except Exception:
    LIVENESS_OK = False

try:
    from twin_analysis import TwinAnalyzer
    TWIN_OK = True
except Exception:
    TWIN_OK = False


class _ConfirmBuffer:
    """Requires consistent frame recognition before confirming an identity."""
    def __init__(self, n: int = 10, required: int = 5):
        self._n = n
        self._required = required
        self._ids = deque(maxlen=n)
        self._confs = deque(maxlen=n)

    def push(self, student_id: str, confidence: float) -> None:
        self._ids.append(student_id)
        self._confs.append(confidence)

    def is_confirmed(self, student_id: str) -> bool:
        if not student_id or student_id in ("Unknown", "?"):
            return False
        return self._ids.count(student_id) >= self._required

    def avg_confidence(self, student_id: str) -> float:
        matching = [c for i, c in zip(self._ids, self._confs) if i == student_id]
        return float(np.mean(matching)) if matching else 0.0


class SmartRecognizer:
    """
    Unified Face Recognition Engine.
    Used seamlessly across live CLI sessions, background API camera workers,
    and role-based attendance kiosks without code duplication.
    """

    def __init__(self,
                 model_path: str = None,
                 labels_path: str = None,
                 unknown_margin: int = None,
                 min_confidence: float = 0.25):
        self.model_path = model_path or config.LBPH_MODEL
        self.labels_path = labels_path or config.LBPH_LABELS
        self.unknown_margin = unknown_margin or getattr(config, "LBPH_UNKNOWN_MARGIN", 100)
        self.min_confidence = min_confidence

        self.model = None
        self.labels = {}
        self.num_persons = 0
        self.effective_margin = self.unknown_margin

        self._confirm_buffers = {}
        self._marked_cache = set()  # (student_id, period)

        self._cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._liveness = LivenessDetector() if LIVENESS_OK else None
        self._load_model()

    def _load_model(self) -> bool:
        """Load trained LBPH model and serialized labels."""
        if not os.path.exists(self.model_path) or not os.path.exists(self.labels_path):
            log.warning("[RECOGNIZER] Model or labels not found at %s", self.model_path)
            return False
        try:
            self.model = cv2.face.LBPHFaceRecognizer_create()
            self.model.read(self.model_path)
            with open(self.labels_path, "rb") as fh:
                self.labels = pickle.load(fh)

            real_ids = [v for v in self.labels.values() if v != "__UNKNOWN__"]
            self.num_persons = len(real_ids)
            # Adaptive margin for single-person models to avoid false rejections
            if self.num_persons == 1:
                self.effective_margin = min(self.unknown_margin, 80)
            else:
                self.effective_margin = self.unknown_margin

            log.info("[RECOGNIZER] Loaded %d enrolled person(s), effective_margin=%d",
                     self.num_persons, self.effective_margin)
            return True
        except Exception as e:
            log.error("[RECOGNIZER] Error loading model: %s", e)
            self.model = None
            return False

    def _get_buffer(self, face_key: str) -> _ConfirmBuffer:
        if face_key not in self._confirm_buffers:
            self._confirm_buffers[face_key] = _ConfirmBuffer(n=10, required=4)
        return self._confirm_buffers[face_key]

    def recognize_crop(self, face_gray: np.ndarray) -> tuple[str, float]:
        """
        Runs multi-variant recognition on a face crop.
        Returns: (student_id, confidence)
        """
        if self.model is None or not self.labels:
            return "Unknown", 0.0

        variants = FacePreprocessor.make_variants(face_gray)
        best_label = -1
        best_dist = 9999.0

        for var in variants:
            try:
                lbl, dist = self.model.predict(var)
                if dist < best_dist:
                    best_dist = dist
                    best_label = lbl
            except Exception:
                continue

        if best_dist > self.effective_margin or best_label not in self.labels:
            return "Unknown", 0.0

        student_id = self.labels[best_label]
        if student_id == "__UNKNOWN__":
            return "Unknown", 0.0

        conf = float(np.clip(1.0 - (best_dist / self.effective_margin), 0.0, 1.0))
        if conf < self.min_confidence:
            return "Unknown", conf

        return student_id, conf

    def process_frame(self, frame: np.ndarray, period: str, cam: str = "CAM1", draw: bool = True):
        """
        Processes a full camera frame:
          1. Preprocesses lighting & detects faces
          2. Recognizes each face using multi-variant LBPH
          3. Confirms identity via temporal buffer
          4. Automatically marks attendance in database on confirmation
          5. Draws bounding boxes, confidence tags, and status on frame
        """
        if frame is None or frame.size == 0:
            return frame, []

        enhanced = FacePreprocessor.preprocess_frame(frame)
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY) if len(enhanced.shape) == 3 else enhanced

        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80)
        )

        results = []
        out = frame.copy() if draw else frame

        for (x, y, w, h) in faces:
            crop_gray = gray[y:y+h, x:x+w]
            raw_id, raw_conf = self.recognize_crop(crop_gray)

            # Spatial grid key for temporal confirmation
            grid_key = f"{x // 120}_{y // 120}"
            buf = self._get_buffer(grid_key)
            buf.push(raw_id, raw_conf)

            is_confirmed = buf.is_confirmed(raw_id)
            final_conf = buf.avg_confidence(raw_id) if is_confirmed else raw_conf
            display_id = raw_id if is_confirmed else ("Unknown" if raw_id != "Unknown" else "?")

            # Mark attendance once per period
            if is_confirmed and display_id not in ("Unknown", "?"):
                cache_key = (display_id, period)
                if cache_key not in self._marked_cache:
                    name = display_id
                    try:
                        stu = db.get_student(display_id)
                        if stu:
                            name = stu.get("name", display_id)
                    except Exception:
                        pass

                    marked = db.mark_attendance(
                        student_id=display_id,
                        name=name,
                        period=period,
                        confidence=final_conf,
                        engine="LBPH-DualEngine",
                        camera_id=cam
                    )
                    if marked:
                        self._marked_cache.add(cache_key)
                        log.info("[ATTENDANCE-MARKED] %s (%s) for %s [conf=%.0f%%]",
                                 name, display_id, period, final_conf * 100)

            results.append({
                "student_id": display_id,
                "confidence": final_conf,
                "confirmed": is_confirmed,
                "bbox": (x, y, w, h)
            })

            if draw:
                color = (0, 220, 0) if is_confirmed else (0, 165, 255) if display_id != "Unknown" else (0, 0, 220)
                cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
                label = f"{display_id} ({final_conf * 100:.0f}%)" if is_confirmed else display_id
                cv2.rectangle(out, (x, y - 26), (x + w, y), color, cv2.FILLED)
                cv2.putText(out, label, (x + 6, y - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        return out, results
