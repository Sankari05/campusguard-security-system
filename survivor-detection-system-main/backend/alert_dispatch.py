"""
alert_dispatch.py
------------------
Simulated GSM/LoRa network-alert dispatcher.

No physical modem exists in this system, so this module does not send a
real SMS or LoRa packet - it honestly *simulates* what that transmission
would look like: encoding a payload, incurring network latency, and
being subject to packet loss that gets worse as the originating sensor
node's battery degrades (reusing sensor_simulator.py's battery_pct model).
This turns "alert sent" from a cosmetic in-app badge into a modeled
network event with its own success/failure/retry history - the same
distinction `rescue_dispatch.py` draws for physical dispatch vs.
`rescue-team/status`'s multi-team auto-assignment.

Design notes
------------
- Packet loss probability has a channel-specific baseline (LoRa is faster
  and doesn't need cell coverage, but is less reliable than SMS over a
  GSM network) plus a battery-dependent penalty that ramps up below
  BATTERY_LOSS_THRESHOLD_PCT, mirroring the dropout model already used
  for raw sensor readings in sensor_simulator.py.
- A failed attempt is retried up to MAX_RETRIES times, each retry adding
  RETRY_BACKOFF_MS of latency - a real GSM/LoRa stack doesn't give up on
  the first lost packet, but it also doesn't retry forever.
- Duplicate suppression: the same (victim_id, triage_class) pair won't
  re-alert within DUPLICATE_SUPPRESSION_WINDOW_CYCLES cycles, so a HIGH
  victim doesn't spam a fresh alert every single cycle - a real GSM/SMS
  gateway would rate-limit exactly the same way.

Public surface
--------------
NetworkAlertDispatcher
    .send_alert(victim_id, triage_class, sps, battery_pct, current_cycle,
                channel=...)
        -> Optional[AlertRecord]   (None if suppressed as a duplicate)
    .should_suppress(victim_id, triage_class, current_cycle) -> bool
    .history()  -> list[AlertRecord]
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #

CHANNEL_SMS = "sms"
CHANNEL_LORA = "lora"

# Baseline network behavior (independent of battery)
BASE_LATENCY_MS = {"sms": 4500, "lora": 1200}
BASE_PACKET_LOSS_PROB = {"sms": 0.03, "lora": 0.08}   # LoRa less reliable but faster/local

# Battery-dependent extra packet loss - reuses sensor_simulator's battery_pct
# scale directly, so a node near dead battery is far more likely to fail
# to get its alert out, same as its sensor readings degrade/drop.
BATTERY_LOSS_THRESHOLD_PCT = 30.0
BATTERY_LOSS_MAX_EXTRA_PROB = 0.55   # added on top of base loss as battery -> 0

MAX_RETRIES = 2
RETRY_BACKOFF_MS = 2000

DUPLICATE_SUPPRESSION_WINDOW_CYCLES = 3  # don't re-alert same victim/class within N cycles


# --------------------------------------------------------------------------- #
# Alert record
# --------------------------------------------------------------------------- #

@dataclass
class AlertRecord:
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    victim_id: str = ""
    channel: str = CHANNEL_SMS
    triage_class: str = ""
    sps: float = 0.0
    status: str = "pending"       # pending | sent | failed
    attempts: int = 0
    latency_ms: float = 0.0
    battery_pct_at_send: float = 100.0
    reason: str = ""              # e.g. "packet loss (low battery)", "sent ok"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "victim_id": self.victim_id,
            "channel": self.channel,
            "triage_class": self.triage_class,
            "sps": round(self.sps, 2),
            "status": self.status,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "battery_pct_at_send": self.battery_pct_at_send,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #

class NetworkAlertDispatcher:
    """
    Simulates firing an out-of-band GSM/LoRa alert for urgent victims.
    Deterministic under a fixed seed, so runs are reproducible for testing.
    """

    def __init__(self, seed: Optional[int] = None, channel: str = CHANNEL_SMS):
        self.rng = random.Random(seed)
        self.channel = channel
        self._records: list[AlertRecord] = []
        self._recent_alerts: dict = {}   # (victim_id, triage_class) -> cycle sent

    def _loss_probability(self, battery_pct: float) -> float:
        base = BASE_PACKET_LOSS_PROB[self.channel]
        if battery_pct >= BATTERY_LOSS_THRESHOLD_PCT:
            return base
        severity = 1.0 - (battery_pct / BATTERY_LOSS_THRESHOLD_PCT)
        return min(0.95, base + severity * BATTERY_LOSS_MAX_EXTRA_PROB)

    def should_suppress(self, victim_id, triage_class, current_cycle) -> bool:
        key = (victim_id, triage_class)
        last_cycle = self._recent_alerts.get(key)
        return last_cycle is not None and (current_cycle - last_cycle) < DUPLICATE_SUPPRESSION_WINDOW_CYCLES

    def send_alert(
        self,
        victim_id,
        triage_class,
        sps,
        battery_pct,
        current_cycle,
        channel=None,
    ) -> Optional[AlertRecord]:
        """
        Simulate dispatching one network alert for `victim_id`. Returns the
        resulting AlertRecord (status "sent" or "failed" after exhausting
        retries), or None if this (victim_id, triage_class) pair was
        already alerted within the duplicate-suppression window - real
        GSM/SMS gateways rate-limit repeat alerts the same way.
        """
        channel = channel or self.channel
        if self.should_suppress(victim_id, triage_class, current_cycle):
            return None

        loss_prob = self._loss_probability(battery_pct)
        attempts = 0
        status = "failed"
        reason = ""
        while attempts <= MAX_RETRIES:
            attempts += 1
            if self.rng.random() >= loss_prob:
                status = "sent"
                reason = f"delivered on attempt {attempts}"
                break
            reason = f"packet loss on attempt {attempts}" + (
                " (low battery)" if battery_pct < BATTERY_LOSS_THRESHOLD_PCT else ""
            )

        latency = BASE_LATENCY_MS[channel] * (1 + 0.4 * self.rng.random()) + (attempts - 1) * RETRY_BACKOFF_MS

        record = AlertRecord(
            victim_id=victim_id,
            channel=channel,
            triage_class=triage_class,
            sps=sps,
            status=status,
            attempts=attempts,
            latency_ms=round(latency, 1),
            battery_pct_at_send=round(battery_pct, 1),
            reason=reason,
        )
        self._records.append(record)
        self._recent_alerts[(victim_id, triage_class)] = current_cycle
        return record

    def history(self) -> list:
        return list(self._records)
