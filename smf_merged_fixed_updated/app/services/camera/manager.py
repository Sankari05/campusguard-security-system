# =============================================================
# app/services/camera/manager.py
# Enterprise Fault-Tolerant Camera Capture & Auto-Reconnect Manager
# =============================================================
import os
import time
import logging
import platform
import threading
from typing import Optional, Tuple
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

log = logging.getLogger(__name__)


class CameraStreamManager:
    """
    Thread-safe camera capture manager with automatic reconnection loop,
    multi-backend discovery, and graceful HUD fallback rendering.
    """

    def __init__(self, primary_index: int = 0, target_width: int = 640, target_height: int = 480, fps: int = 30):
        self.primary_index = primary_index
        self.target_width = target_width
        self.target_height = target_height
        self.fps = fps

        self._cap: Optional[object] = None
        self._lock = threading.Lock()
        self._is_connected = False
        self._reconnecting = False
        self._reconnect_attempts = 0
        self._last_reconnect_time = 0.0
        self._active_index = primary_index
        self._stall_count = 0
        self._frame_count = 0

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._cap is not None and self._cap.isOpened()

    def _get_backends(self):
        if not CV2_AVAILABLE:
            return []
        if platform.system() == "Windows":
            return [cv2.CAP_DSHOW, cv2.CAP_ANY]
        return [cv2.CAP_ANY, cv2.CAP_V4L2]

    def open(self) -> bool:
        """Attempt to open camera using primary index with optimized backend priority."""
        with self._lock:
            if not CV2_AVAILABLE:
                log.error("[CAMERA] OpenCV not installed — camera capture disabled.")
                return False

            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None

            backends = self._get_backends()
            idx = self.primary_index
            for bk in backends:
                try:
                    cap = cv2.VideoCapture(idx, bk)
                    if not cap.isOpened():
                        cap.release()
                        continue

                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
                    cap.set(cv2.CAP_PROP_FPS, self.fps)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

                    # Flush warm-up frames
                    for _ in range(6):
                        cap.grab()
                        time.sleep(0.015)

                    ret, test_frame = cap.read()
                    if ret and test_frame is not None and test_frame.size > 0:
                        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        log.info("[CAMERA] Connected successfully on index=%d backend=%s (%dx%d)", idx, bk, actual_w, actual_h)
                        self._cap = cap
                        self._active_index = idx
                        self._is_connected = True
                        self._reconnecting = False
                        self._reconnect_attempts = 0
                        self._stall_count = 0
                        return True
                    cap.release()
                except Exception as err:
                    log.debug("[CAMERA] Index %d backend %s failed: %s", idx, bk, err)

            self._is_connected = False
            return False

    def read_frame(self) -> Tuple[bool, np.ndarray, bool]:
        """
        Reads a frame from the camera.
        Returns:
            (success: bool, frame: np.ndarray, is_fallback: bool)
        If camera is disconnected or stalled, triggers auto-reconnect loop
        and returns a dynamic HUD fallback frame.
        """
        with self._lock:
            # If not connected or in reconnecting state, handle auto-reconnect
            if not self._is_connected or self._cap is None:
                self._handle_reconnect_loop()
                fallback_frame = self.generate_fallback_frame(
                    status="RECONNECTING",
                    message=f"Attempt {self._reconnect_attempts} - Searching for video device (Index {self._active_index})"
                )
                return True, fallback_frame, True

            grabbed = False
            try:
                grabbed = self._cap.grab()
            except Exception as e:
                log.warning("[CAMERA] Grab exception: %s", e)

            if grabbed:
                try:
                    ret, frame = self._cap.retrieve()
                except Exception as e:
                    ret, frame = False, None
            else:
                ret, frame = False, None

            # Frame validation
            if not ret or frame is None or frame.size == 0:
                self._stall_count += 1
                # If stalled for more than ~15 consecutive attempts (0.5s), mark disconnected
                if self._stall_count > 15:
                    log.warning("[CAMERA] Camera stream stalled/lost. Triggering auto-reconnect loop.")
                    self._is_connected = False
                    self._reconnecting = True
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                    self._cap = None
                    self._stall_count = 0

                fallback_frame = self.generate_fallback_frame(
                    status="STREAM INTERRUPTED",
                    message="Signal lost. Re-synchronizing hardware feed..."
                )
                return True, fallback_frame, True

            self._stall_count = 0
            self._frame_count += 1
            return True, frame, False

    def _handle_reconnect_loop(self):
        """Non-blocking periodic reconnection cycle with exponential backoff."""
        now = time.time()
        # Backoff: 1.0s, 2.0s, max 3.5s
        backoff = min(1.0 + (self._reconnect_attempts * 0.5), 3.5)
        if now - self._last_reconnect_time < backoff:
            return

        self._last_reconnect_time = now
        self._reconnect_attempts += 1
        log.info("[CAMERA] Auto-reconnect attempt #%d...", self._reconnect_attempts)

        # Attempt recovery
        if self.open():
            log.info("[CAMERA] Auto-reconnect succeeded on attempt #%d!", self._reconnect_attempts)

    def generate_fallback_frame(self, status: str = "OFFLINE", message: str = "Camera Unavailable") -> np.ndarray:
        """
        Renders a dynamic modern HUD fallback frame to preserve MJPEG streaming
        without black screens or dropped HTTP connections.
        """
        frame = np.zeros((self.target_height, self.target_width, 3), dtype=np.uint8)
        if not CV2_AVAILABLE:
            return frame

        # Elegant gradient background
        for y in range(self.target_height):
            c = int(18 + (y / self.target_height) * 15)
            frame[y, :] = (c, c + 2, c + 6)

        # Draw subtle grid lines
        for x in range(0, self.target_width, 40):
            cv2.line(frame, (x, 0), (x, self.target_height), (30, 35, 45), 1)
        for y in range(0, self.target_height, 40):
            cv2.line(frame, (0, y), (self.target_width, y), (30, 35, 45), 1)

        # Draw tech corner brackets
        bracket_len = 30
        color_bracket = (70, 90, 120)
        # Top-left
        cv2.line(frame, (20, 20), (20 + bracket_len, 20), color_bracket, 2)
        cv2.line(frame, (20, 20), (20, 20 + bracket_len), color_bracket, 2)
        # Top-right
        cv2.line(frame, (self.target_width - 20, 20), (self.target_width - 20 - bracket_len, 20), color_bracket, 2)
        cv2.line(frame, (self.target_width - 20, 20), (self.target_width - 20, 20 + bracket_len), color_bracket, 2)
        # Bottom-left
        cv2.line(frame, (20, self.target_height - 20), (20 + bracket_len, self.target_height - 20), color_bracket, 2)
        cv2.line(frame, (20, self.target_height - 20), (20, self.target_height - 20 - bracket_len), color_bracket, 2)
        # Bottom-right
        cv2.line(frame, (self.target_width - 20, self.target_height - 20), (self.target_width - 20 - bracket_len, self.target_height - 20), color_bracket, 2)
        cv2.line(frame, (self.target_width - 20, self.target_height - 20), (self.target_width - 20, self.target_height - 20 - bracket_len), color_bracket, 2)

        # Pulsing indicator dot
        pulse_val = int(abs(np.sin(time.time() * 3.0)) * 180 + 75)
        indicator_color = (0, pulse_val, 255) if "RECONNECT" in status else (60, 60, 240)
        cv2.circle(frame, (self.target_width // 2 - 140, self.target_height // 2 - 35), 8, indicator_color, -1)

        # Status text
        cv2.putText(
            frame,
            f"SMF VISION: {status}",
            (self.target_width // 2 - 115, self.target_height // 2 - 28),
            cv2.FONT_HERSHEY_DUPLEX,
            0.75,
            (230, 235, 245),
            1,
            cv2.LINE_AA
        )

        # Detailed message
        cv2.putText(
            frame,
            message,
            (self.target_width // 2 - 200, self.target_height // 2 + 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (160, 175, 195),
            1,
            cv2.LINE_AA
        )

        # Help hint
        cv2.putText(
            frame,
            "Please verify webcam connection or close other video apps.",
            (self.target_width // 2 - 210, self.target_height // 2 + 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (110, 125, 140),
            1,
            cv2.LINE_AA
        )

        # Live timestamp
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            f"SYS TIME: {ts}",
            (30, self.target_height - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (90, 105, 120),
            1,
            cv2.LINE_AA
        )

        return frame

    def release(self):
        """Thread-safe release of camera resources."""
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self._is_connected = False
            self._reconnecting = False
            log.info("[CAMERA] Camera resources released cleanly.")
