"""
app package
EduTrack Pro — Enterprise Smart Attendance & Biometric Face Recognition System.
Configures runtime package search paths to support clean modular subpackages.
"""

import os
import sys

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_APP_DIR)

_SUBDIRS = [
    _ROOT_DIR,
    _APP_DIR,
    os.path.join(_APP_DIR, "core"),
    os.path.join(_APP_DIR, "database"),
    os.path.join(_APP_DIR, "services"),
    os.path.join(_APP_DIR, "services", "vision"),
    os.path.join(_APP_DIR, "services", "notifications"),
    os.path.join(_APP_DIR, "services", "attendance"),
    os.path.join(_APP_DIR, "api"),
    os.path.join(_APP_DIR, "api", "v1"),
    os.path.join(_APP_DIR, "api", "v1", "features"),
    os.path.join(_ROOT_DIR, "scripts", "seeds"),
    os.path.join(_ROOT_DIR, "scripts", "cli"),
]

for _d in _SUBDIRS:
    if os.path.isdir(_d) and _d not in sys.path:
        sys.path.insert(0, _d)

__version__ = "9.6.0"
