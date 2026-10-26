"""
app.api.v1.training
FastAPI router for LBPH face model training, selective training, and progress monitoring.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from app.services.training_service import TrainingService
from auth_utils import get_current_user, admin_required
from app.core.logger import get_logger

log = get_logger("training_router")
router = APIRouter(prefix="/api/train", tags=["AI Training & Model Management"])


def admin_training_required(user: dict = Depends(get_current_user)) -> dict:
    """Strictly allow ONLY role=='admin'. HOD, faculty, teacher are rejected with 403."""
    if user.get("role") != "admin":
        log.warning("TRAINING ACCESS DENIED — role=%s sub=%s", user.get("role", "?"), user.get("sub", "?"))
        raise HTTPException(status_code=403, detail="Access denied: AI Training is restricted to Admin only.")
    return user


class SelectiveTrainReq(BaseModel):
    role: str
    id: str


@router.post("")
def api_train(background_tasks: BackgroundTasks, user: dict = Depends(admin_required)):
    """Kicks off LBPH + dlib training in a background thread."""
    if TrainingService._train_state["running"]:
        return {"status": "already_running", "message": "Training is already in progress"}
    background_tasks.add_task(TrainingService.run_training_bg)
    return {"status": "started", "message": "Training started in background. Poll /api/train/status"}


@router.get("/status")
def api_train_status(_: dict = Depends(get_current_user)):
    """Poll basic model training status and console tail."""
    return TrainingService.get_basic_status()


@router.get("/status/all")
def api_train_status_all(user: dict = Depends(admin_training_required)):
    """Scan dataset folders and compare with trained_ids.json (ADMIN ONLY)."""
    return TrainingService.get_dataset_training_status_all()


@router.post("/selective")
def api_train_selective(
    req: SelectiveTrainReq,
    background_tasks: BackgroundTasks,
    user: dict = Depends(admin_training_required),
):
    """Selectively train a single person and append to shared model (ADMIN ONLY)."""
    valid_roles = ("hod", "faculty", "student")
    if req.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role '{req.role}'. Must be one of: {valid_roles}")

    if TrainingService._selective_state.get("running"):
        return {"status": "already_running", "message": "A selective training job is already in progress"}
    if TrainingService._full_train_state.get("running"):
        return {"status": "conflict", "message": "Full retraining is in progress — wait for it to finish"}

    background_tasks.add_task(TrainingService.selective_train_bg, req.role, req.id)
    return {
        "status": "started",
        "role": req.role,
        "id": req.id,
        "message": f"Selective training started for {req.id} ({req.role}). Poll /api/train/progress",
    }


@router.get("/progress")
def api_train_progress(_: dict = Depends(admin_training_required)):
    """Poll endpoint for selective training progress."""
    return TrainingService.get_selective_status()


@router.post("/full")
def api_train_full(
    background_tasks: BackgroundTasks,
    user: dict = Depends(admin_training_required),
):
    """Full model retraining for all enrolled persons (ADMIN ONLY)."""
    if TrainingService._full_train_state.get("running"):
        return {"status": "already_running", "message": "Full retraining already in progress"}
    if TrainingService._selective_state.get("running"):
        return {"status": "conflict", "message": "Selective training in progress — wait for it to finish"}

    background_tasks.add_task(TrainingService.full_retrain_bg)
    return {"status": "started", "message": "Full retraining started. Poll /api/train/status for progress."}


@router.get("/full/status")
def api_train_full_status(_: dict = Depends(admin_training_required)):
    """Poll status for full model retraining (ADMIN ONLY)."""
    return TrainingService.get_full_status()
