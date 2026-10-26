"""
config.py
---------
Configuration management and feature flag loader for RidgeWatch Communication Subsystem.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Ensure environment is loaded
for _env_path in [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / "backend" / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path("backend/.env"),
    Path(".env"),
]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break


@dataclass
class CommunicationConfig:
    """Subsystem configuration properties and operational tuning parameters."""
    
    # Master Feature Flags
    failover_enabled: bool = False
    retry_enabled: bool = True
    
    # Retry & Backoff Configuration
    max_retries: int = 3
    backoff_base_sec: float = 5.0
    backoff_schedule: tuple = (5.0, 15.0, 30.0)
    timeout_sec: float = 5.0
    ttl_minutes: int = 120
    
    # Channel Availability Flags
    whatsapp_enabled: bool = True
    smsgate_enabled: bool = True
    native_sms_enabled: bool = False
    lora_enabled: bool = False
    
    # LoRa Hardware / Protocol Configuration
    lora_frequency_mhz: float = 868.0
    lora_spreading_factor: int = 8
    lora_bandwidth_khz: float = 125.0
    lora_coding_rate: str = "4/5"
    lora_max_payload_bytes: int = 64
    
    # Rate Limiting (Bulk 90 Recipient Queue)
    sms_rate_limit_per_sec: float = 5.0
    lora_rate_limit_per_sec: float = 0.33  # 1 packet per 3 seconds
    
    # Circuit Breaker Tuning
    circuit_failure_threshold: int = 3
    circuit_recovery_timeout_sec: float = 30.0

    @classmethod
    def from_env(cls) -> CommunicationConfig:
        def _bool(key: str, default: bool) -> bool:
            val = os.getenv(key, str(default)).strip().lower()
            return val in ("true", "1", "yes", "on")

        def _float(key: str, default: float) -> float:
            try:
                return float(os.getenv(key, str(default)))
            except (ValueError, TypeError):
                return default

        def _int(key: str, default: int) -> int:
            try:
                return int(os.getenv(key, str(default)))
            except (ValueError, TypeError):
                return default

        return cls(
            failover_enabled=_bool("COMMUNICATION_FAILOVER_ENABLED", False),
            retry_enabled=_bool("COMMUNICATION_RETRY_ENABLED", True),
            max_retries=_int("COMMUNICATION_MAX_RETRIES", 3),
            backoff_base_sec=_float("COMMUNICATION_BACKOFF_BASE_SEC", 5.0),
            ttl_minutes=_int("COMMUNICATION_TTL_MINUTES", 120),
            whatsapp_enabled=_bool("WHATSAPP_ENABLED", True),
            smsgate_enabled=_bool("SMSGATE_ENABLED", True),
            native_sms_enabled=_bool("NATIVE_SMS_ENABLED", False),
            lora_enabled=_bool("LORA_ENABLED", False),
            lora_frequency_mhz=_float("LORA_FREQUENCY_MHZ", 868.0),
            lora_spreading_factor=_int("LORA_SPREADING_FACTOR", 8),
        )


# Global Config Singleton
_CONFIG: Optional[CommunicationConfig] = None


def get_config() -> CommunicationConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = CommunicationConfig.from_env()
    return _CONFIG


def reload_config() -> CommunicationConfig:
    global _CONFIG
    _CONFIG = CommunicationConfig.from_env()
    return _CONFIG
