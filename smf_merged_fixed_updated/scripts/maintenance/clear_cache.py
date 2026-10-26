import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import app  # noqa: F401

"""
clear_cache.py  —  Run this ONCE after replacing recognizer1.py
Usage:  python clear_cache.py

Deletes all .pyc files and __pycache__ folders in the project
directory so Python recompiles from the new source files.
"""
import os, shutil, pathlib

project_dir = pathlib.Path(__file__).parent

removed = []

# Delete all __pycache__ folders
for cache_dir in project_dir.rglob("__pycache__"):
    shutil.rmtree(cache_dir, ignore_errors=True)
    removed.append(str(cache_dir))

# Delete any stray .pyc files
for pyc in project_dir.rglob("*.pyc"):
    pyc.unlink(missing_ok=True)
    removed.append(str(pyc))

if removed:
    print(f"✓ Removed {len(removed)} cache files/folders:")
    for r in removed:
        print(f"    {r}")
else:
    print("✓ No cache files found — already clean.")

print("\nNow restart your server:  python main.py  or  uvicorn api:app --reload")