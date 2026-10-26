# app/schemas/copilot.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SituationCreate(BaseModel):
    location: str
    status: str  # NORMAL, ATTENTION_NEEDED, SUSPICIOUS, EMERGENCY
    notes: str | None = None
    recorded_by: str = "Main Gate Security"


class SituationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location: str
    status: str
    notes: str | None
    recorded_by: str
    recorded_at: datetime
    pattern_alert_triggered: bool
    alert_message: str | None


class PatternAlert(BaseModel):
    location: str
    count_today: int
    current_status: str
    alert_message: str
    last_updated: datetime


class VoiceIncidentRequest(BaseModel):
    transcript: str
    spoken_by: str = "Main Gate Watchman"
    location_hint: str | None = None


class VoiceIncidentResponse(BaseModel):
    ticket_number: str
    incident_type: str
    category: str
    location: str
    urgency: str
    detected_vehicle: str | None
    description: str
    raw_transcript: str
    automated_actions: list[str]


class PrioritizedTask(BaseModel):
    id: str
    title: str
    task_type: str  # EMERGENCY, OVERDUE_OUTPASS, BARRIER_DEFECT, PATROL_DUE, PARCEL_WAITING
    priority_bucket: str  # DO_FIRST, DO_NEXT, ROUTINE
    location: str
    urgency_level: str
    suggested_action: str
    created_at: str


class PrioritizedQueueResponse(BaseModel):
    do_first: list[PrioritizedTask]
    do_next: list[PrioritizedTask]
    routine: list[PrioritizedTask]
    total_active_count: int


class CarryForwardTask(BaseModel):
    id: int | str
    task_name: str
    category: str  # MAINTENANCE, VISITORS, PARCELS, SECURITY
    shift_origin: str
    urgency: str
    status: str
    description: str


class CarryForwardResponse(BaseModel):
    has_carry_forward: bool
    total_pending: int
    previous_shift_guard: str
    pending_tasks: list[CarryForwardTask]


class SectorProfile(BaseModel):
    sector_id: str
    name: str
    icon: str
    description: str
    primary_entity: str
    gate_pass_name: str
    key_workflows: list[str]
    compliance_rules: list[str]
    stat_labels: dict[str, str]
    sample_pass_preview: dict[str, str]


class HourlyTraffic(BaseModel):
    hour: str
    inflow: int
    outflow: int
    avg_clearance_seconds: float


class GateCongestionAnalytics(BaseModel):
    current_ingress_rate_per_hour: int
    current_egress_rate_per_hour: int
    peak_hours: list[str]
    congestion_level: str  # LOW, MODERATE, HIGH
    active_lanes: int
    recommended_lanes: int
    staffing_forecast: str
    automation_efficiency_boost: str
    avg_processing_time_anpr_sec: float
    avg_processing_time_manual_sec: float
    hourly_distribution: list[HourlyTraffic]

