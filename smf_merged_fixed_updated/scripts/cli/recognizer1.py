import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import app  # noqa: F401

"""
recognizer1.py — Compatibility Facade.
Routes directly to app.services.vision.SmartRecognizer.
"""
from app.services.vision import SmartRecognizer, FacePreprocessor

__all__ = ["SmartRecognizer", "FacePreprocessor"]
