# RIDGEWATCH — Multi-Channel Emergency Communication Implementation Plan
**Document Version:** 1.0.0  
**Date:** September 2026  
**Status:** Implementation Blueprint & Phase Breakdown

---

## 1. Plan Overview & Safety Philosophy

This implementation plan governs the step-by-step creation, integration, verification, and deployment of the Resilient Multi-Channel Emergency Communication subsystem in RidgeWatch.

**Golden Safety Rule:**  
Do NOT break or modify existing RidgeWatch core functionality (`fusion_engine.py`, `wearable_gateway.py`, `rescue_dispatch.py`, `sensor_simulator.py`, etc.). The new module must be completely isolated, additive, and protected behind explicit feature flags.

---

## 2. File Change Manifest

### 2.1 Files to Create (NEW)

| File Path | Purpose |
|---|---|
| `backend/communication/__init__.py` | Package root, public surface exports, and router singleton accessor. |
| `backend/communication/models.py` | Enums (`ChannelType`, `MessagePriority`, `DeliveryStatus`), `EmergencyMessage`, `DeliveryResult`, and DTOs. |
| `backend/communication/config.py` | Configuration settings, timeouts, backoff intervals, and environment flag readers. |
| `backend/communication/channel_health.py` | Proactive health probing, circuit breaker states (`CLOSED`, `OPEN`, `HALF_OPEN`), and bearer status reporting. |
| `backend/communication/message_queue.py` | Priority-based, delay-tolerant queue with TTL expiration checks and thread-safe operations. |
| `backend/communication/delivery_tracker.py` | Delivery ledger SQLite persistence, idempotency verification, and state transitions. |
| `backend/communication/retry_manager.py` | Truncated exponential backoff retry scheduler with jitter and ACK processor. |
| `backend/communication/communication_router.py` | Authoritative multi-channel failover router and dispatch orchestrator. |
| `backend/communication/adapters/__init__.py` | Adapter registry and factory functions. |
| `backend/communication/adapters/base.py` | `BaseCommunicationAdapter` abstract base class defining `send(message) -> DeliveryResult` and `health_check()`. |
| `backend/communication/adapters/whatsapp_adapter.py` | Twilio / Cloud WhatsApp and HTTP Webhook communication adapter. |
| `backend/communication/adapters/sms_gateway_adapter.py` | SMSGate Android Local Server adapter (wrapping existing tested endpoints). |
| `backend/communication/adapters/native_sms_adapter.py` | Native Android companion SMS bridge adapter. |
| `backend/communication/adapters/lora_adapter.py` | Sub-GHz LoRa RF adapter with compact frame formatting and simulation engine. |
| `tests/test_communication_router.py` | Comprehensive test suite covering all 15 required test scenarios (unit, failover, idempotency, retries, 90-recipient queue). |
| `docs/COMMUNICATION_EXISTING_SYSTEM_ANALYSIS.md` | Baseline analysis of existing system. |
| `docs/COMMUNICATION_RESEARCH_ANALYSIS.md` | 10-topic IEEE research and literature synthesis. |
| `docs/COMMUNICATION_ARCHITECTURE.md` | Detailed architectural specification with diagrams and schemas. |
| `docs/COMMUNICATION_IMPLEMENTATION_PLAN.md` | This implementation roadmap and execution guide. |
| `docs/COMMUNICATION_TEST_REPORT.md` | Final post-implementation test execution report. |
| `docs/COMMUNICATION_DEPLOYMENT_GUIDE.md` | Production deployment, configuration, and runbook guide. |

### 2.2 Files to Modify (ADDITIVE & MINIMAL)

| File Path | Scope of Modification | Rationale |
|---|---|---|
| `backend/db.py` | Add `CREATE TABLE IF NOT EXISTS communication_delivery` and helper functions (`log_communication_delivery`, `get_communication_delivery`, `update_communication_delivery_status`, `list_communication_deliveries`). | Provides persistence for the delivery ledger without modifying any existing tables or rows. |
| `backend/notification_dispatch.py` | Add optional failover check: if `COMMUNICATION_FAILOVER_ENABLED=true`, delegate outbound dispatch to `communication_router`. Otherwise, preserve existing direct call. | Seamlessly hooks failover capability while keeping default behavior unchanged when flag is false. |
| `backend/api.py` | Add read-only observability endpoints: `GET /api/v1/communication/status`, `GET /api/v1/communication/deliveries`, and `POST /api/v1/communication/ack`. | Enables frontend UI and monitoring tools to inspect channel health and delivery states. |
| `backend/.env.example` | Add template entries for new feature flags (`COMMUNICATION_FAILOVER_ENABLED`, `LORA_ENABLED`, etc.). | Documents configuration options for operators. |

### 2.3 Files Explicitly NOT Modified

The following files are strictly out of scope and must remain unmodified:
- `backend/fusion_engine.py` (Core sensor fusion algorithms)
- `backend/wearable_gateway.py` (Wave Call Plus BLE GATT protocol)
- `backend/rescue_dispatch.py` (Vehicle routing and auto-dispatch heuristics)
- `backend/sensor_simulator.py` (18 sensor modalities simulation)
- `backend/subsurface_dsp.py` (Bioradar signal processing)
- `backend/debris_flow_detector.py` & `backend/landslide_detector.py` (Geohazard detectors)
- `backend/road_network.py` & `backend/evacuation_engine.py` (Evacuation path calculations)
- `android-companion/app/src/main/java/org/ridgewatch/rescuer/bridge/WearableBleBridge.kt` (Android BLE Bridge)

---

## 3. Environment Variables & Feature Flags

New flags configured in `backend/.env` with safe defaults:

```bash
# Multi-Channel Communication Failover Subsystem
COMMUNICATION_FAILOVER_ENABLED=false     # Master feature flag (default: false for backward compatibility)
COMMUNICATION_RETRY_ENABLED=true         # Enables exponential backoff retries
COMMUNICATION_MAX_RETRIES=3              # Max retry attempts before failover / offline queue
COMMUNICATION_BACKOFF_BASE_SEC=5.0       # Base backoff in seconds (5s, 15s, 30s)
COMMUNICATION_TTL_MINUTES=120            # Message Time-To-Live in minutes

# Channel Specific Flags
WHATSAPP_ENABLED=true                    # Enables WhatsApp internet channel
NATIVE_SMS_ENABLED=false                 # Enables Native Android SMS bridge
LORA_ENABLED=false                       # Enables LoRa RF adapter (simulated if no physical modem)
LORA_FREQUENCY_MHZ=868.0                 # Sub-GHz frequency band
LORA_SPREADING_FACTOR=8                  # SF7-SF12
```

---

## 4. Step-by-Step Implementation Sequence

```
Phase 1: Analysis & System Inspection (COMPLETE)
Phase 2: Academic & IEEE Research Analysis (COMPLETE)
Phase 3: Architecture Specification (COMPLETE)
Phase 4: Implementation Planning & Antigravity Plan (CURRENT STEP)
           │
           ▼
Phase 5: Implement `backend/communication/` Package
           ├── models.py & config.py
           ├── adapters/ (base, whatsapp, sms_gateway, native_sms, lora)
           ├── channel_health.py
           ├── message_queue.py
           ├── delivery_tracker.py
           ├── retry_manager.py
           └── communication_router.py
           │
           ▼
Phase 6: Database Additive Schema Update (`backend/db.py`)
           └── communication_delivery table & CRUD functions
           │
           ▼
Phase 7: Test-First Unit & Integration Testing (`tests/test_communication_router.py`)
           ├── Test 1: Internet available -> WhatsApp selected
           ├── Test 2: Internet down, Cellular up -> SMSGate selected
           ├── Test 3: Internet & Cellular down, LoRa up -> LoRa selected
           ├── Test 4: All down -> OFFLINE_QUEUED locally
           ├── Test 5: Duplicate message rejection (Idempotency)
           ├── Test 6: CRITICAL priority queue preemption
           ├── Test 7: Exponential backoff retries terminate at max
           ├── Test 8: Expired messages purged
           ├── Test 9: Backward compatibility with failover disabled
           ├── Test 10: 90-recipient non-blocking queue simulation
           └── Verification that all 972 existing tests continue passing
           │
           ▼
Phase 8: Additive Integration in `notification_dispatch.py` & `api.py`
Phase 9: Documentation Finalization & Walkthrough
```

---

## 5. Rollback & Disaster Recovery Plan

If any unforeseen issue occurs in production:
1. **Instant Feature Flag Rollback:** Set `COMMUNICATION_FAILOVER_ENABLED=false` in `backend/.env` and restart the backend. The system immediately reverts to standard direct SMSGate/wearable dispatching without code changes.
2. **Database Isolation:** The `communication_delivery` table is purely additive and does not hold foreign key locks on `rescue_commands` or `notification_center`. It can be dropped or truncated without affecting existing alert histories.

---

## 6. Testing & Quality Assurance Plan

Automated test execution matrix:
1. **New Communication Suite:** `pytest tests/test_communication_router.py -v` (15+ focused scenarios).
2. **Existing Full Test Suite:** `pytest` (verifying all 972 existing tests pass with 0 failures).
3. **Android Companion Build Verification:** `.\gradlew.bat clean assembleDebug` (verifying `BUILD SUCCESSFUL`).
4. **Static Linting & Syntax Check:** `python -m py_compile backend/communication/*.py`.

---

## 7. Next Actions

Present the completed implementation plan and architecture to the user for formal approval before initiating code creation in `backend/communication/`.
