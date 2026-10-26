"""
app/services/vision/preprocessor.py
===================================
Unified Face Preprocessing & Lighting Normalization Engine.
Single Source of Truth for:
  - Multi-stage CLAHE & adaptive histogram stretching (dark skin optimization)
  - Gamma correction lookup tables
  - Preprocessing variants for robust LBPH distance reduction
"""
import cv2
import numpy as np


class FacePreprocessor:
    """Enterprise-grade Face Preprocessor handling diverse lighting & skin tones."""

    _GAMMA_TABLES = {
        g: np.array([min(255, int(((i / 255.0) ** (1.0 / g)) * 255)) for i in range(256)], dtype=np.uint8)
        for g in [1.3, 1.4, 1.7, 1.8, 2.0, 2.2, 0.65]
    }

    @staticmethod
    def gamma_correct(img: np.ndarray, gamma: float) -> np.ndarray:
        """Apply gamma correction using cached lookup tables."""
        table = FacePreprocessor._GAMMA_TABLES.get(gamma)
        if table is None:
            table = np.array([min(255, int(((i / 255.0) ** (1.0 / gamma)) * 255)) for i in range(256)], dtype=np.uint8)
        return cv2.LUT(img, table)

    @staticmethod
    def stretch_histogram(gray: np.ndarray) -> np.ndarray:
        """
        Stretch histogram to full 0-255 range.
        Critical for dark-skinned faces whose pixel intensities cluster between 30-120.
        """
        mn, mx = float(gray.min()), float(gray.max())
        if mx - mn < 10:
            return gray
        stretched = np.clip((gray.astype(np.float32) - mn) / (mx - mn) * 255, 0, 255)
        return stretched.astype(np.uint8)

    @staticmethod
    def preprocess_frame(frame: np.ndarray) -> np.ndarray:
        """Auto-correct full frame brightness before face detection."""
        if frame is None or frame.size == 0:
            return frame
        out = frame.copy()
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY) if len(out.shape) == 3 else out
        mean = float(np.mean(gray))

        if mean < 60:
            out = FacePreprocessor.gamma_correct(out, 2.0)
        elif mean < 90:
            out = FacePreprocessor.gamma_correct(out, 1.7)
        elif mean < 120:
            out = FacePreprocessor.gamma_correct(out, 1.3)
        elif mean > 210:
            out = FacePreprocessor.gamma_correct(out, 0.65)
        return out

    @staticmethod
    def normalize_face(gray: np.ndarray, target_size=(160, 160)) -> np.ndarray:
        """
        Primary normalization pipeline: Resize + Parameter-free equalizeHist.
        Must strictly match the training pipeline to produce minimal LBPH distances.
        """
        if gray is None or gray.size == 0:
            return gray
        if len(gray.shape) == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, target_size)
        return cv2.equalizeHist(resized)

    @staticmethod
    def make_variants(gray: np.ndarray, target_size=(160, 160)) -> list[np.ndarray]:
        """
        Generate multiple preprocessing variants to match across adverse lighting,
        shadows, motion blur, and varied Indian classroom lighting.
        """
        if gray is None or gray.size == 0:
            return []
        if len(gray.shape) == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        base = cv2.resize(gray, target_size)
        variants = []

        # 0. Primary: equalizeHist (training match)
        eq = cv2.equalizeHist(base)
        variants.append(eq)

        # 1. Light CLAHE (clip 2.0)
        clahe_light = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        variants.append(clahe_light.apply(base))

        # 2. Strong CLAHE (clip 4.0 - dark skin enhancement)
        clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        variants.append(clahe_strong.apply(base))

        # 3-5. Gamma-brightened equalized
        for g in [1.4, 1.8, 2.2]:
            variants.append(FacePreprocessor.gamma_correct(eq, g))

        # 6. Histogram stretched then equalized
        stretched = FacePreprocessor.stretch_histogram(base)
        variants.append(cv2.equalizeHist(stretched))

        # 7. Sharpened
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
        variants.append(np.clip(cv2.filter2D(eq, -1, kernel), 0, 255).astype(np.uint8))

        # 8. Gaussian blurred (motion tolerance)
        variants.append(cv2.GaussianBlur(eq, (3, 3), 0))

        # 9. Raw crop
        variants.append(base)

        return variants
