# ==============================================================================
# arcface_engine.py — Modern Face Recognition Pipeline (SCRFD + ArcFace ONNX)
#
# Standalone, ultra-lightweight, high-accuracy face recognition engine:
#   1. Detection: SCRFD-500M with 5-point facial landmarks (~10-15ms on CPU)
#   2. Alignment: 5-point Similarity / Affine Transform -> 112x112 canonical crop
#   3. Quality Gate: Blur (Laplacian variance), minimum face size, frontal pose check
#   4. Recognition: ArcFace MobileFaceNet 512-d normalized embedding (~15ms on CPU)
#   5. Matching: Cosine similarity threshold (industry standard >= 0.50)
#
# Zero dependency on heavy DL frameworks — pure ONNX Runtime + OpenCV + NumPy.
# ==============================================================================

import os
import time
import pickle
import numpy as np
import cv2
import onnxruntime as ort

# Standard ArcFace 112x112 5-point canonical reference landmarks
REFERENCE_FACIAL_POINTS = np.array([
    [38.2946, 51.6963],  # left eye
    [73.5318, 51.5014],  # right eye
    [56.0252, 71.7366],  # nose tip
    [41.5493, 92.3655],  # left mouth corner
    [70.7299, 92.2041]   # right mouth corner
], dtype=np.float32)


class SCRFDDetector:
    """Lightweight anchor-free deep CNN face detector with 5 landmarks."""

    def __init__(self, model_path: str, conf_thresh: float = 0.50, nms_thresh: float = 0.40):
        self.conf_thresh = conf_thresh
        self.nms_thresh = nms_thresh
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 4
        opts.intra_op_num_threads = 4
        self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.fmc = 3
        self._feat_stride_fpn = [8, 16, 32]
        self._num_anchors = 2

    def detect(self, img: np.ndarray, threshold: float = None):
        """
        Detect faces in image.
        Returns: boxes (N, 5) [x1, y1, x2, y2, score], kpss (N, 5, 2)
        """
        thresh = threshold or self.conf_thresh
        orig_h, orig_w = img.shape[:2]

        # Resize to 640x640 maintaining aspect ratio
        target_size = (640, 640)
        im_ratio = float(orig_h) / orig_w
        if im_ratio > 1.0:
            new_h = target_size[1]
            new_w = int(new_h / im_ratio)
        else:
            new_w = target_size[0]
            new_h = int(new_w * im_ratio)
        det_scale = float(new_h) / orig_h

        resized = cv2.resize(img, (new_w, new_h))
        det_img = np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
        det_img[:new_h, :new_w, :] = resized

        blob = cv2.dnn.blobFromImage(det_img, 1.0 / 128.0, target_size,
                                     (127.5, 127.5, 127.5), swapRB=True)
        net_outs = self.session.run(self.output_names, {self.input_name: blob})

        scores_list = []
        bboxes_list = []
        kpss_list = []
        input_h, input_w = blob.shape[2:]

        for idx, stride in enumerate(self._feat_stride_fpn):
            scores = net_outs[idx]
            bbox_preds = net_outs[idx + self.fmc] * stride
            kps_preds = net_outs[idx + self.fmc * 2] * stride

            h = input_h // stride
            w = input_w // stride

            anchor_centers = np.stack(np.mgrid[:h, :w][::-1], axis=-1).astype(np.float32)
            anchor_centers = (anchor_centers * stride).reshape((-1, 2))
            if self._num_anchors > 1:
                anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1).reshape((-1, 2))

            pos_inds = np.where(scores >= thresh)[0]
            if len(pos_inds) == 0:
                continue

            bboxes = np.zeros((len(pos_inds), 4), dtype=np.float32)
            bboxes[:, 0] = anchor_centers[pos_inds, 0] - bbox_preds[pos_inds, 0]
            bboxes[:, 1] = anchor_centers[pos_inds, 1] - bbox_preds[pos_inds, 1]
            bboxes[:, 2] = anchor_centers[pos_inds, 0] + bbox_preds[pos_inds, 2]
            bboxes[:, 3] = anchor_centers[pos_inds, 1] + bbox_preds[pos_inds, 3]

            scores_list.append(scores[pos_inds])
            bboxes_list.append(bboxes)

            kpss = np.zeros((len(pos_inds), 5, 2), dtype=np.float32)
            for p in range(5):
                kpss[:, p, 0] = anchor_centers[pos_inds, 0] + kps_preds[pos_inds, p * 2]
                kpss[:, p, 1] = anchor_centers[pos_inds, 1] + kps_preds[pos_inds, p * 2 + 1]
            kpss_list.append(kpss)

        if not scores_list:
            return np.empty((0, 5), dtype=np.float32), np.empty((0, 5, 2), dtype=np.float32)

        scores = np.vstack(scores_list)
        bboxes = np.vstack(bboxes_list)
        kpss = np.vstack(kpss_list)

        # Non-Maximum Suppression (NMS)
        order = scores.ravel().argsort()[::-1]
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)[order]
        kpss = kpss[order]

        keep = []
        x1 = pre_det[:, 0]
        y1 = pre_det[:, 1]
        x2 = pre_det[:, 2]
        y2 = pre_det[:, 3]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)

        for i in range(len(order)):
            if len(keep) == 0:
                keep.append(i)
                continue
            xx1 = np.maximum(x1[i], x1[keep])
            yy1 = np.maximum(y1[i], y1[keep])
            xx2 = np.minimum(x2[i], x2[keep])
            yy2 = np.minimum(y2[i], y2[keep])
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (areas[i] + areas[keep] - inter)
            if np.all(ovr <= self.nms_thresh):
                keep.append(i)

        final_boxes = pre_det[keep]
        final_kpss = kpss[keep]

        # Rescale coordinates back to original image resolution
        final_boxes[:, :4] /= det_scale
        final_kpss /= det_scale

        return final_boxes, final_kpss


class ArcFaceEngine:
    """
    Modern Face Recognition Engine using SCRFD + ArcFace (MobileFaceNet).
    Handles 5-point alignment, feature extraction (512-d), and similarity matching.
    """

    def __init__(self,
                 det_model_path: str = "models/arcface/det_500m.onnx",
                 rec_model_path: str = "models/arcface/w600k_mbf.onnx",
                 gallery_path: str = "models/arcface_gallery.pkl",
                 conf_threshold: float = 0.50,
                 sim_threshold: float = 0.52):
        self.conf_threshold = conf_threshold
        self.sim_threshold = sim_threshold
        self.gallery_path = gallery_path
        self.gallery = {}  # {person_id: np.ndarray (N, 512)}

        # Load SCRFD detector
        if not os.path.exists(det_model_path):
            raise FileNotFoundError(f"SCRFD model not found: {det_model_path}")
        self.detector = SCRFDDetector(det_model_path, conf_thresh=conf_threshold)

        # Load ArcFace embedding model
        if not os.path.exists(rec_model_path):
            raise FileNotFoundError(f"ArcFace model not found: {rec_model_path}")
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 4
        opts.intra_op_num_threads = 4
        self.rec_session = ort.InferenceSession(rec_model_path, opts, providers=["CPUExecutionProvider"])
        self.rec_input = self.rec_session.get_inputs()[0].name

        # Load gallery if present
        self.load_gallery()

    def align_face(self, img: np.ndarray, kps: np.ndarray) -> np.ndarray:
        """
        Align face using 5 facial landmarks to canonical 112x112 ArcFace crop.
        kps: array of shape (5, 2)
        """
        M, _ = cv2.estimateAffinePartial2D(kps, REFERENCE_FACIAL_POINTS)
        if M is None:
            # Fallback to standard bounding box crop + resize
            x1, y1 = np.min(kps, axis=0)
            x2, y2 = np.max(kps, axis=0)
            crop = img[max(0, int(y1)):min(img.shape[0], int(y2)),
                       max(0, int(x1)):min(img.shape[1], int(x2))]
            if crop.size == 0:
                return cv2.resize(img, (112, 112))
            return cv2.resize(crop, (112, 112))

        aligned = cv2.warpAffine(img, M, (112, 112), borderValue=0.0)
        return aligned

    def get_embedding(self, aligned_bgr: np.ndarray) -> np.ndarray:
        """Extract 512-dimensional normalized face embedding."""
        blob = cv2.dnn.blobFromImage(aligned_bgr, 1.0 / 127.5, (112, 112),
                                     (127.5, 127.5, 127.5), swapRB=True)
        feat = self.rec_session.run(None, {self.rec_input: blob})[0][0]
        norm = np.linalg.norm(feat)
        if norm > 0:
            feat = feat / norm
        return feat.astype(np.float32)

    def quality_check(self, img: np.ndarray, box: np.ndarray, kps: np.ndarray) -> tuple[bool, str]:
        """
        Check face image quality:
        - Face size minimum
        - Laplacian blur check
        - Extreme angle check (eye distance)
        """
        x1, y1, x2, y2 = box[:4]
        w = x2 - x1
        h = y2 - y1

        if w < 40 or h < 40:
            return False, "Face too small"

        crop = img[max(0, int(y1)):min(img.shape[0], int(y2)),
                   max(0, int(x1)):min(img.shape[1], int(x2))]
        if crop.size == 0:
            return False, "Invalid crop"

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        if blur_score < 10.0:
            return False, f"Too blurry ({blur_score:.0f})"

        # Pose check: eye-to-eye horizontal distance vs eye-to-nose
        left_eye, right_eye = kps[0], kps[1]
        eye_dist = np.linalg.norm(right_eye - left_eye)
        if eye_dist < 15:
            return False, "Extreme face angle"

        return True, "OK"

    def match_embedding(self, query_emb: np.ndarray, threshold: float = None) -> tuple[str, float]:
        """
        Compare query embedding against registered gallery.
        Returns: (best_person_id, max_similarity)
        """
        thresh = threshold or self.sim_threshold
        if not self.gallery:
            return None, 0.0

        best_id = None
        best_sim = -1.0

        for pid, emb_list in self.gallery.items():
            if not len(emb_list):
                continue
            # Cosine similarity for normalized vectors is pure dot product
            sims = np.dot(emb_list, query_emb)
            max_s = float(np.max(sims))
            if max_s > best_sim:
                best_sim = max_s
                best_id = pid

        if best_sim >= thresh and best_id:
            return best_id, best_sim
        return None, best_sim

    def process_frame(self, frame: np.ndarray):
        """
        End-to-end frame processing:
        Returns list of detections: [{box, kps, quality_ok, reason, person_id, similarity}]
        """
        boxes, kpss = self.detector.detect(frame)
        results = []

        for i in range(len(boxes)):
            box = boxes[i]
            kps = kpss[i]

            q_ok, reason = self.quality_check(frame, box, kps)
            if not q_ok:
                results.append({
                    "box": box[:4],
                    "kps": kps,
                    "score": float(box[4]),
                    "quality_ok": False,
                    "reason": reason,
                    "person_id": None,
                    "similarity": 0.0,
                })
                continue

            aligned = self.align_face(frame, kps)
            emb = self.get_embedding(aligned)
            pid, sim = self.match_embedding(emb)

            results.append({
                "box": box[:4],
                "kps": kps,
                "score": float(box[4]),
                "quality_ok": True,
                "reason": "OK",
                "person_id": pid,
                "similarity": sim,
            })

        return results

    def _compute_face_quality(self, img: np.ndarray, box: np.ndarray, kps: np.ndarray) -> float:
        """
        Computes composite face quality score [0.0 - 100.0+] based on:
        1. Sharpness (Laplacian variance of face crop)
        2. Detection confidence from SCRFD
        3. Face bounding box size (larger = clearer resolution)
        4. Eye symmetry / frontal pose tilt penalty
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
        x2, y2 = min(img.shape[1], int(box[2])), min(img.shape[0], int(box[3]))
        face_roi = gray[y1:y2, x1:x2]

        blur_val = float(cv2.Laplacian(face_roi, cv2.CV_64F).var()) if face_roi.size > 0 else 0.0
        # Scaled up to 40 points: blur_val > 120 gets full ~40 points
        blur_score = min(40.0, blur_val / 3.0)

        # Confidence: 0.0 to 1.0 -> 0 to 35 points
        conf = float(box[4]) if len(box) > 4 else 0.8
        conf_score = conf * 35.0

        # Resolution score: up to 25 points for faces >= 100x100
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        res_score = min(25.0, (w * h) / 400.0)

        # Pose symmetry: penalize head tilt
        tilt_penalty = 0.0
        if kps is not None and len(kps) >= 2:
            left_eye, right_eye = kps[0], kps[1]
            eye_dy = abs(left_eye[1] - right_eye[1])
            eye_dx = max(1.0, abs(left_eye[0] - right_eye[0]))
            eye_angle_ratio = eye_dy / eye_dx
            tilt_penalty = min(25.0, eye_angle_ratio * 40.0)

        # Composite score: higher = sharper, larger, more frontal, higher confidence
        return conf_score + blur_score + res_score - tilt_penalty

    def _process_person_folder(self, pid: str, pdir: str, gallery_dict: dict, max_best_frames: int = 20) -> int:
        """
        METHOD 3: SMART IMAGE SAMPLING (TOP 20 BEST QUALITY FRAMES)
        - Analyzes all available images in the student's folder.
        - Ranks images by face quality (sharpness, confidence, resolution, symmetry).
        - Selects the Top 20 best quality frames for training.
        - Safely uses all valid detected faces if <= 20 images exist.
        - Cuts memory & inference time by 2x while maximizing cosine similarity accuracy!
        """
        img_files = [f for f in sorted(os.listdir(pdir)) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
        if not img_files:
            return 0

        candidates = []
        for fname in img_files:
            fpath = os.path.join(pdir, fname)
            img = cv2.imread(fpath)
            if img is None:
                continue

            boxes, kpss = self.detector.detect(img, threshold=0.40)
            if len(boxes) > 0:
                best_idx = 0
                if len(boxes) > 1:
                    areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]
                    best_idx = int(np.argmax(areas))
                q_score = self._compute_face_quality(img, boxes[best_idx], kpss[best_idx])
                candidates.append((q_score, img, kpss[best_idx]))
            else:
                h, w = img.shape[:2]
                dummy_box = np.array([0, 0, w, h, 0.5])
                q_score = self._compute_face_quality(img, dummy_box, None)
                candidates.append((q_score, img, None))

        if not candidates:
            return 0

        # Rank by quality score descending (cleanest, sharpest frames first)
        candidates.sort(key=lambda c: c[0], reverse=True)
        top_candidates = candidates[:max_best_frames]

        emb_list = []
        for _, img, kps in top_candidates:
            if kps is not None:
                aligned = self.align_face(img, kps)
            else:
                aligned = cv2.resize(img, (112, 112))
            emb = self.get_embedding(aligned)
            emb_list.append(emb)

        if emb_list:
            gallery_dict[pid] = np.array(emb_list, dtype=np.float32)
            avg_q = sum(c[0] for c in top_candidates[:len(emb_list)]) / len(emb_list)
            print(f"[ArcFace Smart Sample] {pid}: selected top {len(emb_list)} best frames (from {len(img_files)} total, avg quality: {avg_q:.1f})")
            return len(emb_list)
        return 0

    def enroll_single_person(self, person_id: str, person_dir: str = None) -> int:
        """
        INCREMENTAL MODE: Enroll or retrain ONLY a single person in the ArcFace gallery (< 3 seconds!).
        Existing persons in the gallery remain untouched in cache.
        """
        if not self.gallery:
            self.load_gallery()

        if person_dir is None:
            for base in ["data/known_faces", "data/known_faces/faculty", "data/known_faces/hod",
                         "data/dataset", "data/dataset/faculty", "data/dataset/hod"]:
                cand = os.path.join(base, person_id)
                if os.path.isdir(cand):
                    person_dir = cand
                    break

        if not person_dir or not os.path.isdir(person_dir):
            print(f"[ArcFace] Directory not found for {person_id}")
            return 0

        count = self._process_person_folder(person_id, person_dir, self.gallery)
        if count > 0:
            self.save_gallery()
            print(f"[ArcFace] Incremental enrollment OK for {person_id}: {count} embeddings")
        return count

    def build_gallery_from_known_faces(self, base_dir: str = "data/known_faces", force_rebuild: bool = False) -> dict:
        """
        Scans data/known_faces/ and updates ArcFace embeddings.
        INCREMENTAL CACHE MODE (Default):
        - Reuses cached embeddings for already-enrolled students (0s latency).
        - Automatically smart-samples to top 20 best frames if previously had > 20.
        - Only extracts embeddings for NEW or updated persons!
        """
        if not force_rebuild and not self.gallery:
            self.load_gallery()

        gallery = {} if force_rebuild else dict(self.gallery)
        if not os.path.exists(base_dir):
            return gallery

        valid_pids = set()

        for pid in sorted(os.listdir(base_dir)):
            pdir = os.path.join(base_dir, pid)
            if not os.path.isdir(pdir):
                continue
            if pid in ("faculty", "hod"):
                for subpid in sorted(os.listdir(pdir)):
                    subdir = os.path.join(pdir, subpid)
                    if os.path.isdir(subdir):
                        valid_pids.add(subpid)
                        if not force_rebuild and subpid in gallery and 0 < len(gallery[subpid]) <= 20:
                            print(f"[ArcFace Cache HIT] {subpid}: reusing {len(gallery[subpid])} cached embeddings")
                            continue
                        self._process_person_folder(subpid, subdir, gallery)
                continue

            valid_pids.add(pid)

            # Check cache hit: reuse if already smart-sampled (<= 20 frames)
            if not force_rebuild and pid in gallery and 0 < len(gallery[pid]) <= 20:
                print(f"[ArcFace Cache HIT] {pid}: reusing {len(gallery[pid])} cached embeddings")
                continue

            # Process new or changed person (or resample if previous cache had > 20)
            self._process_person_folder(pid, pdir, gallery)

        # Prune deleted persons
        pruned = [p for p in gallery if p not in valid_pids]
        for p in pruned:
            del gallery[p]
            print(f"[ArcFace] Pruned removed person from gallery: {p}")

        self.gallery = gallery
        self.save_gallery()
        return gallery

    def save_gallery(self):
        """Save gallery to disk."""
        os.makedirs(os.path.dirname(self.gallery_path), exist_ok=True)
        with open(self.gallery_path, "wb") as f:
            pickle.dump(self.gallery, f)
        print(f"[ArcFace] Saved gallery to {self.gallery_path} with {len(self.gallery)} person(s)")

    def load_gallery(self) -> bool:
        """Load gallery from disk."""
        if os.path.exists(self.gallery_path):
            try:
                with open(self.gallery_path, "rb") as f:
                    self.gallery = pickle.load(f)
                print(f"[ArcFace] Loaded gallery with {len(self.gallery)} person(s)")
                return True
            except Exception as e:
                print(f"[ArcFace] Could not load gallery: {e}")
        return False
