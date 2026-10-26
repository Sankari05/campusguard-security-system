"""
message_queue.py
----------------
Delay-Tolerant Networking (DTN) priority message queue for RidgeWatch.
Enforces message priority preemption (CRITICAL first) and TTL expiration.
"""

from __future__ import annotations

import heapq
import threading
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .models import EmergencyMessage, MessagePriority, DeliveryStatus

logger = logging.getLogger("ridgewatch.communication.queue")


class PriorityQueueEntry:
    """Heap wrapper providing deterministic priority ordering."""
    
    PRIORITY_WEIGHTS = {
        MessagePriority.CRITICAL: 0,
        MessagePriority.HIGH: 1,
        MessagePriority.MEDIUM: 2,
        MessagePriority.LOW: 3,
    }

    def __init__(self, message: EmergencyMessage, sequence: int):
        self.message = message
        self.sequence = sequence
        self.weight = self.PRIORITY_WEIGHTS.get(message.priority, 2)

    def __lt__(self, other: PriorityQueueEntry) -> bool:
        if self.weight != other.weight:
            return self.weight < other.weight
        return self.sequence < other.sequence


class MessageQueueManager:
    """Thread-safe delay-tolerant priority queue."""

    def __init__(self, max_size: int = 1000):
        self._heap: List[PriorityQueueEntry] = []
        self._lock = threading.RLock()
        self._counter = 0
        self._max_size = max_size

    def enqueue(self, message: EmergencyMessage) -> bool:
        """Enqueues message according to priority."""
        with self._lock:
            # Clean expired messages first
            self.purge_expired()

            if len(self._heap) >= self._max_size:
                logger.warning(f"[QUEUE] Message queue full ({self._max_size}), dropping lowest priority item.")
                # If CRITICAL, evict a lower priority item
                if message.priority == MessagePriority.CRITICAL and len(self._heap) > 0:
                    # Pop lowest priority (heaviest weight)
                    # Sort temporarily to remove worst item
                    self._heap.sort(key=lambda e: (e.weight, e.sequence))
                    self._heap.pop()  # remove lowest
                    heapq.heapify(self._heap)
                else:
                    return False

            self._counter += 1
            entry = PriorityQueueEntry(message, self._counter)
            heapq.heappush(self._heap, entry)
            logger.info(
                f"[QUEUE] Enqueued {message.priority.value} message {message.message_id} "
                f"for {message.recipient_masked} (Queue depth: {len(self._heap)})"
            )
            return True

    def dequeue(self) -> Optional[EmergencyMessage]:
        """Pops highest priority non-expired message."""
        with self._lock:
            while self._heap:
                entry = heapq.heappop(self._heap)
                msg = entry.message
                if msg.is_expired():
                    msg.status = DeliveryStatus.EXPIRED
                    logger.info(f"[QUEUE] Message {msg.message_id} expired in queue (TTL exceeded).")
                    continue
                return msg
            return None

    def peek(self) -> Optional[EmergencyMessage]:
        with self._lock:
            while self._heap:
                top = self._heap[0].message
                if top.is_expired():
                    heapq.heappop(self._heap)
                    continue
                return top
            return None

    def purge_expired(self) -> int:
        """Removes all expired messages from the queue and returns count."""
        with self._lock:
            valid_entries = []
            expired_count = 0
            for entry in self._heap:
                if entry.message.is_expired():
                    entry.message.status = DeliveryStatus.EXPIRED
                    expired_count += 1
                else:
                    valid_entries.append(entry)
            if expired_count > 0:
                self._heap = valid_entries
                heapq.heapify(self._heap)
                logger.info(f"[QUEUE] Purged {expired_count} expired messages from offline queue.")
            return expired_count

    def size(self) -> int:
        with self._lock:
            return len(self._heap)

    def list_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            sorted_entries = sorted(self._heap, key=lambda e: (e.weight, e.sequence))
            return [e.message.to_dict() for e in sorted_entries[:limit]]

    def clear(self) -> None:
        with self._lock:
            self._heap.clear()
            self._counter = 0
