"""
rescue_dispatch.py
-------------------
Simulated rescue-team dispatch agent.

Consumes the ranked priority queue produced by fusion_engine.rank_victims()
(the same ordering served over GET /queue) and walks a single simulated
rescue team through the victims in that exact order, one at a time.
Movement between victim coordinates is modeled with a simple distance-based
ETA (great-circle distance / walking speed over the debris field), and each
victim is flipped to status "reached" with a UTC timestamp the moment the
team's simulated position arrives at that victim's GPS coordinate.

This module is intentionally independent of the multi-team auto-dispatch
already used by /rescue-team/status (which assigns ALPHA/BRAVO teams to
victims for ETA display) - it represents a single "boots on the ground" SAR
team physically working the priority queue end-to-end, which is what
produces a clean arrival order + timestamp trace for a scenario replay or
test run.

Public surface
--------------
RescueDispatchAgent
    .load_queue(ranked_queue)   - (re)load ordered targets from a /queue-style list
    .advance(seconds=...)       - step the simulation forward by simulated time
    .status_dict()              - JSON-serializable snapshot of agent state
    .is_complete()               - True once every queued victim has been reached
    .set_target(victim_id)      - (Step 18) pin the team to a specific victim, ahead
                                   of auto-priority order; persists across load_queue()
    .clear_override()           - (Step 18) drop the pinned target, resume auto-priority
    .move_manual(bearing, dist) - (Step 18) nudge simulated position along a compass
                                   bearing, ignoring the current auto-walk target

haversine_distance_m(a, b)
    Great-circle distance in meters between two GPSCoordinate points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from models import GPSCoordinate, HIMALAYA_SITE_ORIGIN


# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #

# Average SAR team travel speed over avalanche debris / broken snowpack.
# Deliberately slow relative to open ground - rope work, probing, and
# digging near a target site eat into simple "walking" time far more than
# flat trail travel would.
DEFAULT_TEAM_SPEED_MPS = 0.6

# Each POST /rescue-team/advance steps the simulated clock forward by this
# many seconds of simulated travel, by default.
SECONDS_PER_ADVANCE_STEP = 60.0

EARTH_RADIUS_M = 6371000.0


def haversine_distance_m(a: GPSCoordinate, b: GPSCoordinate) -> float:
    """Great-circle distance in meters between two GPS coordinates."""
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


# --------------------------------------------------------------------------- #
# Dispatch log entry
# --------------------------------------------------------------------------- #

@dataclass
class DispatchLogEntry:
    victim_id: str
    reached_at: str          # ISO-8601 UTC timestamp (simulated clock)
    order: int                # 1-based arrival order
    travel_seconds: float     # simulated seconds spent covering that leg

    def to_dict(self) -> dict:
        return {
            "victim_id": self.victim_id,
            "order": self.order,
            "reached_at": self.reached_at,
            "travel_seconds": round(self.travel_seconds, 1),
        }


# --------------------------------------------------------------------------- #
# Dispatch agent
# --------------------------------------------------------------------------- #

@dataclass
class RescueDispatchAgent:
    """
    A single simulated rescue team that walks an ordered list of victim
    coordinates (the triage priority queue) one leg at a time, using a
    simple constant-speed, straight-line (great-circle) travel model.
    """
    team_id: str = "RESCUE-1"
    speed_mps: float = DEFAULT_TEAM_SPEED_MPS
    position: GPSCoordinate = field(default_factory=lambda: HIMALAYA_SITE_ORIGIN)
    queue: list = field(default_factory=list)         # ordered [{"victim_id", "location"}]
    queue_index: int = 0                                # cursor into `queue`
    sim_clock: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    log: list = field(default_factory=list)             # list[DispatchLogEntry], arrival order
    reached_ids: set = field(default_factory=set)
    reached_at: dict = field(default_factory=dict)      # victim_id -> ISO timestamp, "reached" status
    started: bool = False
    manual_override_victim_id: Optional[str] = None   # Step 18: pinned target, survives auto-poll load_queue() calls

    # ----------------------------------------------------------------- #
    # Setup
    # ----------------------------------------------------------------- #

    def load_queue(self, ranked_queue: list) -> None:
        """
        (Re)load the ordered target list from a ranked /queue-style priority
        order (list of dicts with 'victim_id' + 'location', or FusionResult
        objects with the same attributes). Victims already reached keep
        their place in history; the walk resumes with whichever queued
        victim hasn't been reached yet, in the *current* priority order
        (so if priorities shift between calls, the still-pending leg of the
        walk re-targets accordingly - matching how a real team would
        re-triage on the move).

        If a manual override is pinned (Step 18 - a team head redirected the
        team to a specific victim via set_target()), that victim is kept at
        the front of the pending list even though this rebuild would
        otherwise re-sort everything back to auto-priority order - this is
        what makes the redirect survive the automatic /rescue-team/advance
        poll that dashboard.js fires every ~4 seconds. The override clears
        itself automatically once that victim is reached (see advance()).
        """
        targets = []
        for item in ranked_queue:
            if isinstance(item, dict):
                vid = item.get("victim_id")
                loc = item.get("location")
            else:
                vid = getattr(item, "victim_id", None)
                loc = getattr(item, "location", None)
            if vid is None or loc is None:
                continue
            if isinstance(loc, dict):
                loc = GPSCoordinate(
                    latitude=loc["latitude"],
                    longitude=loc["longitude"],
                    altitude_m=loc.get("altitude_m"),
                )
            targets.append({"victim_id": vid, "location": loc})

        if self.manual_override_victim_id is not None:
            idx = next(
                (i for i, t in enumerate(targets) if t["victim_id"] == self.manual_override_victim_id),
                None,
            )
            if idx is not None and self.manual_override_victim_id not in self.reached_ids:
                pinned = targets.pop(idx)
                targets.insert(0, pinned)
            else:
                # override target no longer exists or already reached - drop it
                self.manual_override_victim_id = None

        self.queue = targets
        self.started = True
        # re-sync the cursor to the current queue order, skipping anything
        # already marked reached
        self.queue_index = 0

    def _current_target(self) -> Optional[dict]:
        while self.queue_index < len(self.queue):
            candidate = self.queue[self.queue_index]
            if candidate["victim_id"] in self.reached_ids:
                self.queue_index += 1
                continue
            return candidate
        return None

    def current_target(self) -> Optional[dict]:
        """Return the dict for the victim currently being walked toward, or None."""
        return self._current_target()

    def current_target_id(self) -> Optional[str]:
        """Return the ID of the victim currently being walked toward, or None."""
        target = self._current_target()
        return target["victim_id"] if target else None

    # ----------------------------------------------------------------- #
    # Simulation step
    # ----------------------------------------------------------------- #

    def advance(self, seconds: float = SECONDS_PER_ADVANCE_STEP) -> Optional[DispatchLogEntry]:
        """
        Step the simulation forward by `seconds` of simulated travel time,
        moving the team along the great-circle leg toward its current
        target. If the leg completes on this step, the target victim is
        marked "reached" with a timestamp and a DispatchLogEntry is
        returned; otherwise the team's position moves partway there and
        None is returned. Returns None (no-op) once the queue is empty or
        fully worked.
        """
        target = self._current_target()
        if target is None:
            return None

        self.sim_clock += timedelta(seconds=seconds)
        distance_to_target = haversine_distance_m(self.position, target["location"])
        step_distance = self.speed_mps * seconds

        if step_distance >= distance_to_target:
            # arrival this step - snap to the victim's exact coordinates
            self.position = target["location"]
            travel_seconds = distance_to_target / self.speed_mps if self.speed_mps else 0.0
            timestamp = self.sim_clock.isoformat()

            self.reached_ids.add(target["victim_id"])
            self.reached_at[target["victim_id"]] = timestamp
            if self.manual_override_victim_id == target["victim_id"]:
                self.manual_override_victim_id = None   # reached - resume auto-priority walk

            entry = DispatchLogEntry(
                victim_id=target["victim_id"],
                reached_at=timestamp,
                order=len(self.log) + 1,
                travel_seconds=travel_seconds,
            )
            self.log.append(entry)
            self.queue_index += 1
            return entry

        # still en route - move the simulated position a fraction of the way there
        frac = (step_distance / distance_to_target) if distance_to_target else 1.0
        self.position = GPSCoordinate(
            latitude=self.position.latitude + frac * (target["location"].latitude - self.position.latitude),
            longitude=self.position.longitude + frac * (target["location"].longitude - self.position.longitude),
            altitude_m=target["location"].altitude_m,
        )
        return None

    # ----------------------------------------------------------------- #
    # Read-only helpers
    # ----------------------------------------------------------------- #

    def eta_seconds_to_current_target(self) -> Optional[float]:
        target = self._current_target()
        if target is None or not self.speed_mps:
            return None
        return haversine_distance_m(self.position, target["location"]) / self.speed_mps

    def is_complete(self) -> bool:
        return self.started and self._current_target() is None

    def victim_status(self, victim_id: str) -> str:
        return "reached" if victim_id in self.reached_ids else "pending"

    # ----------------------------------------------------------------- #
    # Manual overrides (Step 18)
    # ----------------------------------------------------------------- #

    def set_target(self, victim_id: str) -> bool:
        """
        Manual override (Step 18): pin the team's target to `victim_id`,
        ahead of auto-priority order. Persists across auto-poll calls via
        manual_override_victim_id (see load_queue()) until reached or
        explicitly cleared with clear_override(). Returns False if the
        victim isn't in the loaded queue or is already reached.
        """
        if victim_id in self.reached_ids:
            return False
        if not any(t["victim_id"] == victim_id for t in self.queue):
            return False
        self.manual_override_victim_id = victim_id
        idx = next(i for i, t in enumerate(self.queue) if t["victim_id"] == victim_id)
        pinned = self.queue.pop(idx)
        self.queue.insert(0, pinned)
        self.queue_index = 0
        return True

    def clear_override(self) -> None:
        """Manual override (Step 18): drop the pinned target, resume normal auto-priority walking."""
        self.manual_override_victim_id = None

    def move_manual(self, bearing_deg: float, distance_m: float) -> None:
        """
        Manual override (Step 18): move the team's simulated position
        `distance_m` meters along compass bearing `bearing_deg`
        (0=N, 90=E, 180=S, 270=W), ignoring the current auto-walk target.
        Uses the standard spherical "destination point given distance and
        bearing" formula - consistent with haversine_distance_m's spherical
        model, so distance-remaining stays accurate after a manual nudge.
        Does not mark any victim reached and does not touch
        manual_override_victim_id - only set_target()/advance() manage that.
        """
        lat1 = math.radians(self.position.latitude)
        lon1 = math.radians(self.position.longitude)
        brng = math.radians(bearing_deg)
        d_r = distance_m / EARTH_RADIUS_M

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_r) + math.cos(lat1) * math.sin(d_r) * math.cos(brng)
        )
        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d_r) * math.cos(lat1),
            math.cos(d_r) - math.sin(lat1) * math.sin(lat2),
        )

        self.sim_clock += timedelta(seconds=(distance_m / self.speed_mps) if self.speed_mps else 0.0)
        self.position = GPSCoordinate(
            latitude=math.degrees(lat2),
            longitude=math.degrees(lon2),
            altitude_m=self.position.altitude_m,
        )

    def status_dict(self) -> dict:
        target = self._current_target()
        eta_s = self.eta_seconds_to_current_target()
        distance_m = (
            haversine_distance_m(self.position, target["location"]) if target else None
        )
        return {
            "team_id": self.team_id,
            "started": self.started,
            "sim_time": self.sim_clock.isoformat(),
            "speed_mps": self.speed_mps,
            "position": {
                "latitude": self.position.latitude,
                "longitude": self.position.longitude,
                "altitude_m": self.position.altitude_m,
            },
            "current_target": target["victim_id"] if target else None,
            "eta_seconds_to_target": round(eta_s, 1) if eta_s is not None else None,
            "eta_minutes_to_target": round(eta_s / 60.0, 2) if eta_s is not None else None,
            "distance_remaining_m": round(distance_m, 1) if distance_m is not None else None,
            "manual_override_active": self.manual_override_victim_id is not None,
            "queue_order": [t["victim_id"] for t in self.queue],
            "reached": [e.to_dict() for e in self.log],
            "victim_status": {
                t["victim_id"]: {
                    "status": self.victim_status(t["victim_id"]),
                    "reached_at": self.reached_at.get(t["victim_id"]),
                }
                for t in self.queue
            },
            "remaining": [t["victim_id"] for t in self.queue if t["victim_id"] not in self.reached_ids],
            "complete": self.is_complete(),
        }
