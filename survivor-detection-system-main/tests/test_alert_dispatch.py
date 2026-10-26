"""
test_alert_dispatch.py
------------------------
Unit tests for backend/alert_dispatch.py (Step 2: simulated GSM/LoRa
network-alert dispatch).

Run with:
    python -m pytest tests/test_alert_dispatch.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from alert_dispatch import (
    NetworkAlertDispatcher,
    CHANNEL_SMS,
    RETRY_BACKOFF_MS,
    DUPLICATE_SUPPRESSION_WINDOW_CYCLES,
)


class TestSuccessfulSend(unittest.TestCase):
    def test_successful_send_marks_status_sent(self):
        dispatcher = NetworkAlertDispatcher(seed=1, channel=CHANNEL_SMS)
        record = dispatcher.send_alert(
            victim_id="V2",
            triage_class="HIGH",
            sps=95.0,
            battery_pct=100.0,
            current_cycle=1,
        )
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "sent")
        self.assertGreaterEqual(record.attempts, 1)
        self.assertIn(record, dispatcher.history())


class TestLowBatteryFailureRate(unittest.TestCase):
    def test_low_battery_increases_failure_rate(self):
        low_battery_failures = 0
        high_battery_failures = 0
        trials = 200

        for i in range(trials):
            low_dispatcher = NetworkAlertDispatcher(seed=i, channel=CHANNEL_SMS)
            low_record = low_dispatcher.send_alert(
                victim_id="V2", triage_class="HIGH", sps=90.0,
                battery_pct=5.0, current_cycle=1,
            )
            if low_record.status == "failed":
                low_battery_failures += 1

            high_dispatcher = NetworkAlertDispatcher(seed=i, channel=CHANNEL_SMS)
            high_record = high_dispatcher.send_alert(
                victim_id="V2", triage_class="HIGH", sps=90.0,
                battery_pct=100.0, current_cycle=1,
            )
            if high_record.status == "failed":
                high_battery_failures += 1

        self.assertGreater(low_battery_failures, high_battery_failures)


class TestDuplicateSuppression(unittest.TestCase):
    def test_duplicate_suppression_within_window(self):
        dispatcher = NetworkAlertDispatcher(seed=2)
        first = dispatcher.send_alert(
            victim_id="V2", triage_class="HIGH", sps=90.0,
            battery_pct=100.0, current_cycle=1,
        )
        self.assertIsNotNone(first)

        second = dispatcher.send_alert(
            victim_id="V2", triage_class="HIGH", sps=91.0,
            battery_pct=99.0, current_cycle=2,
        )
        self.assertIsNone(second)

    def test_duplicate_not_suppressed_after_window(self):
        dispatcher = NetworkAlertDispatcher(seed=3)
        first = dispatcher.send_alert(
            victim_id="V2", triage_class="HIGH", sps=90.0,
            battery_pct=100.0, current_cycle=1,
        )
        self.assertIsNotNone(first)

        later_cycle = 1 + DUPLICATE_SUPPRESSION_WINDOW_CYCLES
        second = dispatcher.send_alert(
            victim_id="V2", triage_class="HIGH", sps=93.0,
            battery_pct=95.0, current_cycle=later_cycle,
        )
        self.assertIsNotNone(second)


class TestRetriesIncreaseLatency(unittest.TestCase):
    def test_retries_increase_latency(self):
        # Search for a seed where the first attempt is lost but a later
        # one succeeds - forces attempts > 1, then check the backoff shows
        # up in latency_ms.
        found = None
        for seed in range(500):
            dispatcher = NetworkAlertDispatcher(seed=seed, channel=CHANNEL_SMS)
            record = dispatcher.send_alert(
                victim_id="V2", triage_class="HIGH", sps=90.0,
                battery_pct=10.0,  # low battery -> higher loss prob, easier to find a retry case
                current_cycle=1,
            )
            if record.attempts > 1:
                found = record
                break

        self.assertIsNotNone(found, "expected at least one retry case in 500 seeds")
        self.assertGreater(found.attempts, 1)
        # latency_ms must include at least one RETRY_BACKOFF_MS on top of
        # the base per-channel latency.
        min_expected_latency = (found.attempts - 1) * RETRY_BACKOFF_MS
        self.assertGreaterEqual(found.latency_ms, min_expected_latency)


if __name__ == "__main__":
    unittest.main()
