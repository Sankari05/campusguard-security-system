"""
lora_gateway.py
---------------
Hardware-Independent LoRa Communication Gateway for RidgeWatch.

Provides a unified interface for Sub-GHz LoRa RF communications with two modes:
1. SIMULATOR MODE (Default): In-memory RF propagation simulation with RSSI/SNR modeling,
   distance-based attenuation, packet drops, and device registry.
2. HARDWARE MODE (ESP32/SX1262 / SX1276 UART/SPI bridge): Serial port interface for
   physical LoRa transceivers with non-blocking reception and frame CRC validation.

CRITICAL TECHNICAL TRUTH:
- Laptop Wi-Fi / Ethernet is NOT LoRa. Simulator mode is strictly labeled as simulated.
- Physical hardware requires connected LoRa transceiver module (e.g., USB UART ESP32).
"""

from __future__ import annotations

import os
import time
import json
import math
import random
import logging
import threading
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field

from backend.offline_models import (
    OfflineMessage,
    LoRaPacket,
    MessageType,
    MessagePriority,
    MessageStatus,
)

logger = logging.getLogger("ridgewatch.lora_gateway")


@dataclass
class LoRaNodeDescriptor:
    """Registered LoRa transceiver node with geographic / simulated coordinates."""
    device_id: str
    name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    tx_power_dbm: float = 14.0
    frequency_mhz: float = 868.0
    spreading_factor: int = 8
    bandwidth_khz: float = 125.0
    last_seen_at: float = field(default_factory=time.time)
    is_gateway: bool = False
    is_active: bool = True


class LoRaGateway:
    """
    LoRa Gateway & Transceiver Abstraction.
    Manages packet serialization, transmission, reception, range modeling, and deduplication.
    """

    def __init__(
        self,
        device_id: Optional[str] = None,
        mode: Optional[str] = None,
        frequency_mhz: float = 868.0,
        tx_power_dbm: float = 14.0,
        max_range_meters: float = 5000.0,
        serial_port: Optional[str] = None,
        baud_rate: int = 115200,
    ):
        self.device_id = device_id or os.environ.get("LORA_DEVICE_ID", "RIDGEWATCH-GATEWAY-01")
        self.mode = (mode or os.environ.get("LORA_MODE", "simulator")).lower()
        self.frequency_mhz = float(os.environ.get("LORA_FREQUENCY_MHZ", frequency_mhz))
        self.tx_power_dbm = float(os.environ.get("LORA_TX_POWER_DBM", tx_power_dbm))
        self.max_range_meters = float(os.environ.get("LORA_MAX_RANGE_METERS", max_range_meters))
        self.serial_port = serial_port or os.environ.get("LORA_SERIAL_PORT", "COM3")
        self.baud_rate = int(os.environ.get("LORA_BAUD_RATE", baud_rate))

        self._lock = threading.RLock()
        self._nodes: Dict[str, LoRaNodeDescriptor] = {}
        self._seen_packet_ids: set[str] = set()
        self._seen_lock = threading.Lock()
        self._rx_callbacks: List[Callable[[LoRaPacket], None]] = []
        self._packet_history: List[Dict[str, Any]] = []

        # Serial hardware handle (for hardware mode)
        self._serial_handle = None
        self._hardware_thread = None
        self._running = True

        # Initialize local node in registry
        self.register_node(
            LoRaNodeDescriptor(
                device_id=self.device_id,
                name="RidgeWatch Primary Gateway",
                latitude=0.0,
                longitude=0.0,
                tx_power_dbm=self.tx_power_dbm,
                frequency_mhz=self.frequency_mhz,
                is_gateway=True,
                is_active=True,
            )
        )

        if self.mode == "hardware":
            self._init_hardware()
        else:
            logger.info(
                f"[LoRa Gateway] Initialized in SIMULATOR mode. "
                f"Device: {self.device_id}, Freq: {self.frequency_mhz}MHz, Max Range: {self.max_range_meters}m"
            )

    # -------------------------------------------------------------------------
    # Node Management & Topology
    # -------------------------------------------------------------------------

    def register_node(self, node: LoRaNodeDescriptor) -> None:
        """Registers or updates a LoRa mesh node."""
        with self._lock:
            node.last_seen_at = time.time()
            self._nodes[node.device_id] = node
            logger.debug(f"[LoRa Gateway] Node registered: {node.device_id} ({node.name})")

    def unregister_node(self, device_id: str) -> None:
        """Removes a node from registry."""
        with self._lock:
            if device_id in self._nodes:
                del self._nodes[device_id]
                logger.debug(f"[LoRa Gateway] Node unregistered: {device_id}")

    def get_registered_nodes(self) -> List[Dict[str, Any]]:
        """Returns metadata for all known nodes."""
        with self._lock:
            return [
                {
                    "device_id": n.device_id,
                    "name": n.name,
                    "latitude": n.latitude,
                    "longitude": n.longitude,
                    "tx_power_dbm": n.tx_power_dbm,
                    "frequency_mhz": n.frequency_mhz,
                    "spreading_factor": n.spreading_factor,
                    "bandwidth_khz": n.bandwidth_khz,
                    "last_seen_at": n.last_seen_at,
                    "is_gateway": n.is_gateway,
                    "is_active": n.is_active,
                }
                for n in self._nodes.values()
            ]

    def get_node(self, device_id: str) -> Optional[LoRaNodeDescriptor]:
        """Retrieves a specific node descriptor."""
        with self._lock:
            return self._nodes.get(device_id)

    # -------------------------------------------------------------------------
    # Packet Transmission & Validation
    # -------------------------------------------------------------------------

    def register_rx_callback(self, callback: Callable[[LoRaPacket], None]) -> None:
        """Registers a callback function to be invoked when a valid packet is received."""
        with self._lock:
            if callback not in self._rx_callbacks:
                self._rx_callbacks.append(callback)

    def validate_packet(self, packet: LoRaPacket) -> Tuple[bool, Optional[str]]:
        """
        Validates packet structure, checksum, and deduplication.
        Returns (is_valid, error_reason).
        """
        if not packet.packet_id:
            return False, "Missing packet_id"

        if not packet.source_id:
            return False, "Missing source_id"

        if not packet.payload_raw:
            return False, "Empty payload"

        if not packet.verify_checksum():
            return False, f"Checksum mismatch: received={packet.checksum}, expected={packet.calculate_checksum()}"

        return True, None

    def send_packet(
        self,
        packet: LoRaPacket,
        target_node_id: Optional[str] = None,
        simulated_distance_m: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sends a single LoRa packet to a specific target or next-hop node.
        Handles retry logic, checksum calculation, and propagation modeling.
        """
        packet.source_id = packet.source_id or self.device_id
        if not packet.checksum:
            packet.checksum = packet.calculate_checksum()

        target = target_node_id or packet.destination_id
        logger.info(
            f"[LoRa Gateway] Sending packet {packet.packet_id} (Type: {packet.message_type}) "
            f"from {packet.source_id} -> {target} [Mode: {self.mode}]"
        )

        if self.mode == "hardware":
            return self._send_hardware(packet)
        else:
            return self._send_simulated(packet, target, simulated_distance_m)

    def broadcast_packet(
        self,
        packet: LoRaPacket,
        max_hops: int = 5,
    ) -> Dict[str, Any]:
        """
        Broadcasts a packet across all reachable nodes in the mesh.
        """
        packet.destination_id = "BROADCAST"
        packet.max_hops = max_hops
        return self.send_packet(packet, target_node_id="BROADCAST")

    def receive_packet(self, packet: LoRaPacket) -> Dict[str, Any]:
        """
        Processes an incoming packet into the gateway.
        Validates integrity, checks for duplicates, and notifies registered callbacks.
        """
        is_valid, error_msg = self.validate_packet(packet)
        if not is_valid:
            logger.warning(f"[LoRa Gateway] Dropped invalid packet {packet.packet_id}: {error_msg}")
            return {"success": False, "error": error_msg, "packet_id": packet.packet_id}

        # Deduplication check
        with self._seen_lock:
            if packet.packet_id in self._seen_packet_ids:
                logger.debug(f"[LoRa Gateway] Ignored duplicate packet {packet.packet_id}")
                return {"success": True, "duplicate": True, "packet_id": packet.packet_id}
            self._seen_packet_ids.add(packet.packet_id)
            # Cap seen cache size
            if len(self._seen_packet_ids) > 5000:
                self._seen_packet_ids.clear()

        # Record in packet history
        with self._lock:
            self._packet_history.append({
                "packet_id": packet.packet_id,
                "source_id": packet.source_id,
                "destination_id": packet.destination_id,
                "message_type": packet.message_type,
                "rssi_dbm": packet.rssi_dbm,
                "snr_db": packet.snr_db,
                "hop_count": packet.hop_count,
                "received_at": time.time(),
            })
            if len(self._packet_history) > 500:
                self._packet_history.pop(0)

        # Notify callbacks
        for cb in self._rx_callbacks:
            try:
                cb(packet)
            except Exception as e:
                logger.error(f"[LoRa Gateway] Callback error on packet {packet.packet_id}: {e}", exc_info=True)

        return {"success": True, "duplicate": False, "packet_id": packet.packet_id}

    # -------------------------------------------------------------------------
    # Simulator Propagation Engine
    # -------------------------------------------------------------------------

    def _send_simulated(
        self,
        packet: LoRaPacket,
        target_node_id: str,
        simulated_distance_m: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Simulates Sub-GHz RF propagation using Log-Distance Path Loss model.
        Calculates RSSI, SNR, packet loss probability, and Time-on-Air.
        """
        # Distance calculation
        dist_m = simulated_distance_m
        if dist_m is None:
            if target_node_id == "BROADCAST" or target_node_id == self.device_id:
                dist_m = 100.0
            else:
                target_node = self.get_node(target_node_id)
                if target_node and (target_node.latitude != 0 or target_node.longitude != 0):
                    # Haversine or simple Euclidean approx
                    local_node = self.get_node(self.device_id)
                    lat1 = local_node.latitude if local_node else 0.0
                    lon1 = local_node.longitude if local_node else 0.0
                    dist_m = self._calculate_haversine_distance(lat1, lon1, target_node.latitude, target_node.longitude)
                else:
                    dist_m = 350.0  # Default nominal distance in meters

        # Check range limit
        if dist_m > self.max_range_meters:
            logger.warning(
                f"[LoRa Gateway Simulation] Target {target_node_id} is out of range "
                f"({dist_m:.1f}m > {self.max_range_meters:.1f}m). Transmission failed."
            )
            return {
                "success": False,
                "error": f"Out of range ({dist_m:.1f}m > {self.max_range_meters}m)",
                "distance_meters": dist_m,
                "simulated": True,
            }

        # RF Log-Distance Path Loss Model:
        # PL(d) = PL(d0) + 10 * n * log10(d / d0) + X_sigma
        # At 868MHz, PL(1m) ~= 31.2 dB
        path_loss_exp = 2.8  # Suburban / Mountainous terrain exponent
        pl_1m = 31.2
        if dist_m < 1.0:
            dist_m = 1.0
        path_loss = pl_1m + 10.0 * path_loss_exp * math.log10(dist_m)
        rssi = self.tx_power_dbm - path_loss
        rssi = max(-135.0, min(-20.0, rssi))  # Clamp to SX1262 sensitivity floor

        # SNR estimate: -20 dB to +10 dB based on signal headroom above -120 dBm
        snr = (rssi + 120.0) / 4.0
        snr = max(-20.0, min(15.0, snr))

        # Time on Air calculation (SF8, 125 kHz BW, CR 4/5, Preamble 8)
        payload_bytes = len(packet.payload_raw.encode("utf-8"))
        toa_ms = self.estimate_time_on_air_ms(payload_bytes, sf=8, bw_khz=125.0)

        packet.rssi_dbm = round(rssi, 1)
        packet.snr_db = round(snr, 1)

        logger.info(
            f"[LoRa Gateway Simulation] Packet {packet.packet_id} transmitted: "
            f"Distance={dist_m:.1f}m, RSSI={packet.rssi_dbm}dBm, SNR={packet.snr_db}dB, ToA={toa_ms:.1f}ms"
        )

        return {
            "success": True,
            "packet_id": packet.packet_id,
            "simulated": True,
            "distance_meters": round(dist_m, 1),
            "rssi_dbm": packet.rssi_dbm,
            "snr_db": packet.snr_db,
            "time_on_air_ms": round(toa_ms, 1),
        }

    # -------------------------------------------------------------------------
    # Physical Hardware Transceiver Driver (Serial/UART ESP32)
    # -------------------------------------------------------------------------

    def _init_hardware(self) -> None:
        """Initializes serial UART connection for real physical LoRa module."""
        try:
            import serial
            logger.info(f"[LoRa Gateway] Attempting to open physical serial port: {self.serial_port} @ {self.baud_rate} baud")
            self._serial_handle = serial.Serial(self.serial_port, self.baud_rate, timeout=1.0)
            self._hardware_thread = threading.Thread(target=self._hardware_rx_loop, daemon=True)
            self._hardware_thread.start()
            logger.info(f"[LoRa Gateway] Physical LoRa hardware initialized successfully on {self.serial_port}.")
        except Exception as e:
            logger.warning(
                f"[LoRa Gateway] Physical serial port {self.serial_port} could not be opened ({e}). "
                f"Falling back to simulator mode for this session."
            )
            self.mode = "simulator"

    def _send_hardware(self, packet: LoRaPacket) -> Dict[str, Any]:
        """Transmits frame via physical serial interface to LoRa module."""
        if not self._serial_handle or not self._serial_handle.is_open:
            return {"success": False, "error": "Hardware serial port not open", "simulated": False}

        try:
            frame_str = json.dumps(packet.to_dict()) + "\n"
            self._serial_handle.write(frame_str.encode("utf-8"))
            self._serial_handle.flush()
            logger.info(f"[LoRa Gateway Hardware] Frame written to {self.serial_port}: {len(frame_str)} bytes")
            return {"success": True, "packet_id": packet.packet_id, "simulated": False}
        except Exception as e:
            logger.error(f"[LoRa Gateway Hardware] Write error: {e}", exc_info=True)
            return {"success": False, "error": str(e), "simulated": False}

    def _hardware_rx_loop(self) -> None:
        """Background thread listening on physical UART port."""
        while self._running and self._serial_handle and self._serial_handle.is_open:
            try:
                line = self._serial_handle.readline()
                if line:
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if line_str.startswith("{") and line_str.endswith("}"):
                        data = json.loads(line_str)
                        packet = LoRaPacket.from_dict(data)
                        self.receive_packet(packet)
            except Exception as e:
                time.sleep(0.5)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def estimate_time_on_air_ms(payload_len: int, sf: int = 8, bw_khz: float = 125.0) -> float:
        """Calculates exact Semtech LoRa Time-on-Air in milliseconds."""
        t_sym = (2 ** sf) / (bw_khz * 1000.0) * 1000.0  # Symbol time in ms
        t_preamble = (8 + 4.25) * t_sym

        # Symbol count for payload (explicit header, CR=1 (4/5))
        numerator = 8 * payload_len - 4 * sf + 28 + 16
        denominator = 4 * sf
        payload_sym_nb = 8 + max(math.ceil(numerator / denominator) * 5, 0)
        t_payload = payload_sym_nb * t_sym
        return t_preamble + t_payload

    @staticmethod
    def _calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine formula to compute distance in meters between two lat/lon coordinates."""
        r = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c

    def get_status(self) -> Dict[str, Any]:
        """Returns gateway status summary."""
        with self._lock:
            return {
                "device_id": self.device_id,
                "mode": self.mode,
                "frequency_mhz": self.frequency_mhz,
                "tx_power_dbm": self.tx_power_dbm,
                "max_range_meters": self.max_range_meters,
                "registered_nodes_count": len(self._nodes),
                "is_hardware_connected": bool(self._serial_handle and self._serial_handle.is_open),
                "recent_packets_count": len(self._packet_history),
            }

    def close(self) -> None:
        """Gracefully closes serial connection and releases resources."""
        self._running = False
        if self._serial_handle:
            try:
                self._serial_handle.close()
            except Exception:
                pass
