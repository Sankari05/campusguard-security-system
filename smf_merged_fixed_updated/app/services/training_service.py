"""
app.services.training_service
Encapsulates face recognition model training workflows (full batch and selective single-entity).
Streams output real-time to memory logs and ensures thread-safe execution.
"""

import os
import json
import logging
from typing import Dict, Any, List

import config
from app.core.logger import get_logger

log = get_logger("training_service")


class RealtimeStreamLogger:
    """Streams stdout in real-time to both console and API state log lists."""

    def __init__(self, target_list: list):
        self.target_list = target_list
        self._buf = ""

    def write(self, s: str):
        import sys
        try:
            sys.__stdout__.write(s)
            sys.__stdout__.flush()
        except Exception:
            pass
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            clean = line.strip()
            if clean:
                self.target_list.append(clean)

    def flush(self):
        import sys
        try:
            sys.__stdout__.flush()
        except Exception:
            pass
        if self._buf.strip():
            self.target_list.append(self._buf.strip())
            self._buf = ""


class TrainingService:
    """Enterprise service managing AI/CV model training states and workers."""

    _train_state: Dict[str, Any] = {"running": False, "done": False, "error": "", "log": []}
    _full_train_state: Dict[str, Any] = {"running": False, "done": False, "error": "", "log": []}
    _selective_state: Dict[str, Any] = {
        "running": False, "done": False, "error": "",
        "stage": "", "stages_done": [], "person_id": "", "role": "",
        "log": []
    }

    TRAIN_STAGES = [
        "reading_images",
        "processing_dataset",
        "augmentation",
        "training_model",
        "saving_model",
        "updating_trained_ids",
        "completed",
    ]

    @classmethod
    def get_basic_status(cls) -> Dict[str, Any]:
        return {
            "running": cls._train_state["running"],
            "done": cls._train_state["done"],
            "error": cls._train_state["error"],
            "log": cls._train_state["log"][-20:],
        }

    @classmethod
    def get_selective_status(cls) -> Dict[str, Any]:
        return {
            "running": cls._selective_state["running"],
            "done": cls._selective_state["done"],
            "error": cls._selective_state["error"],
            "stage": cls._selective_state["stage"],
            "stages_done": cls._selective_state["stages_done"],
            "person_id": cls._selective_state["person_id"],
            "role": cls._selective_state["role"],
            "log": cls._selective_state["log"][-30:],
        }

    @classmethod
    def get_full_status(cls) -> Dict[str, Any]:
        return {
            "running": cls._full_train_state.get("running", False),
            "done": cls._full_train_state.get("done", False),
            "error": cls._full_train_state.get("error", ""),
            "log": cls._full_train_state.get("log", [])[-30:],
        }

    @classmethod
    def scan_dataset(cls, role: str) -> List[Dict[str, Any]]:
        role_base = {
            "student": config.DATASET_DIR,
            "faculty": config.FACULTY_DATASET_DIR,
            "hod": config.HOD_DATASET_DIR,
        }.get(role, "")

        if not role_base or not os.path.isdir(role_base):
            return []

        prefix = "STU_" if role == "student" else None
        result = []
        for name in sorted(os.listdir(role_base)):
            if prefix and not name.upper().startswith(prefix.upper()):
                continue
            full = os.path.join(role_base, name)
            if not os.path.isdir(full):
                continue
            imgs = [f for f in os.listdir(full) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            result.append({"id": name, "image_count": len(imgs)})
        return result

    @classmethod
    def load_trained_ids_safe(cls) -> Dict[str, Any]:
        try:
            if os.path.exists(config.TRAINED_IDS_JSON):
                with open(config.TRAINED_IDS_JSON, "r") as f:
                    data = json.load(f)
                for k in ("students", "faculty", "hod"):
                    if k not in data:
                        data[k] = []
                return data
        except Exception as e:
            log.warning("Could not read trained_ids.json: %s", e)
        return {"students": [], "faculty": [], "hod": []}

    @classmethod
    def get_dataset_training_status_all(cls) -> Dict[str, Any]:
        registry = cls.load_trained_ids_safe()
        result = {}
        role_key_map = {"hod": "hod", "faculty": "faculty", "student": "students"}

        for role in ("hod", "faculty", "student"):
            rkey = role_key_map[role]
            trained = registry.get(rkey, [])
            all_ids = cls.scan_dataset(role)

            trained_list = []
            not_trained_list = []
            for item in all_ids:
                pid = item["id"]
                icount = item["image_count"]
                entry = {"id": pid, "image_count": icount, "trained": pid in trained}
                if pid in trained:
                    trained_list.append(entry)
                else:
                    not_trained_list.append(entry)

            result[role] = {"trained": trained_list, "not_trained": not_trained_list}
        return result

    @classmethod
    def run_training_bg(cls):
        cls._train_state["running"] = True
        cls._train_state["done"] = False
        cls._train_state["error"] = ""
        cls._train_state["log"] = ["Starting model training..."]
        try:
            import contextlib
            stream = RealtimeStreamLogger(cls._train_state["log"])
            with contextlib.redirect_stdout(stream):
                from train import train_all
                train_all()
            stream.flush()
            cls._train_state["done"] = True
        except Exception as e:
            cls._train_state["error"] = str(e)
            cls._train_state["log"].append(f"ERROR: {e}")
            cls._train_state["done"] = True
        finally:
            cls._train_state["running"] = False

    @classmethod
    def selective_train_bg(cls, role: str, person_id: str):
        import contextlib
        cls._selective_state["running"] = True
        cls._selective_state["done"] = False
        cls._selective_state["error"] = ""
        cls._selective_state["stages_done"] = []
        cls._selective_state["stage"] = "reading_images"
        cls._selective_state["person_id"] = person_id
        cls._selective_state["role"] = role
        cls._selective_state["log"] = []

        def _advance(stage: str):
            if stage not in cls._selective_state["stages_done"]:
                cls._selective_state["stages_done"].append(stage)
            cls._selective_state["stage"] = stage
            cls._selective_state["log"].append(f"[{stage}] started")
            log.info("Selective training stage: %s — %s/%s", stage, person_id, role)

        try:
            from train_selective import train_one_person, _get_dataset_dir
            _advance("reading_images")
            dataset_path = _get_dataset_dir(role, person_id)

            if not os.path.isdir(dataset_path):
                raise ValueError(f"Dataset folder not found: data/dataset/{role}/{person_id}")

            imgs = [f for f in os.listdir(dataset_path) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            if not imgs:
                raise ValueError(f"No images found in dataset for {role}/{person_id}")

            cls._selective_state["log"].append(f"  Found {len(imgs)} raw images for {person_id}")
            _advance("processing_dataset")
            _advance("augmentation")
            _advance("training_model")

            stream = RealtimeStreamLogger(cls._selective_state["log"])
            with contextlib.redirect_stdout(stream):
                ok = train_one_person(role, person_id)
            stream.flush()

            if not ok:
                raise RuntimeError(f"train_one_person() returned False for {person_id}")

            _advance("saving_model")
            _advance("updating_trained_ids")
            _advance("completed")
            cls._selective_state["stages_done"] = cls.TRAIN_STAGES[:]
            cls._selective_state["done"] = True
        except Exception as exc:
            cls._selective_state["error"] = str(exc)
            cls._selective_state["done"] = True
            cls._selective_state["log"].append(f"  ERROR: {exc}")
            log.error("Selective training error for %s/%s: %s", role, person_id, exc)
        finally:
            cls._selective_state["running"] = False

    @classmethod
    def full_retrain_bg(cls):
        cls._full_train_state.update({
            "running": True, "done": False, "error": "", "log": ["Starting full model retraining..."]
        })
        try:
            import contextlib
            stream = RealtimeStreamLogger(cls._full_train_state["log"])
            with contextlib.redirect_stdout(stream):
                from train import train_all
                train_all()
            stream.flush()
            cls._full_train_state["done"] = True
        except Exception as e:
            cls._full_train_state["error"] = str(e)
            cls._full_train_state["log"].append(f"ERROR: {e}")
            cls._full_train_state["done"] = True
        finally:
            cls._full_train_state["running"] = False
