# RIDGEWATCH — Issue #2 Forensic Code Audit: Wave Call Plus Proprietary Protocol Analysis

**Document ID:** `RIDGEWATCH-AUDIT-ISSUE-2`  
**Date:** 2026-08-23  
**Target Device:** Wave Call Plus (`CALLPLUS_7F1B` / `CB:4E:FD:EE:7F:1B` / `6.4.3582.28`)  
**Scope:** Web Bluetooth, GATT Service/Characteristic Discovery, 0xFEA0/0xFEA1/0xFEA2 Handling, Protocol Evidence Registry, Command & ACK Flows  

---

## 1. Files Inspected

1. [`frontend/js/bridge.js`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js) — Web Bluetooth client, strict device validator, GATT enumerator, evidence registry resolver, diagnostic packet sniffer, and ACK listeners.
2. [`frontend/bridge.html`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/bridge.html) — Mobile companion edge UI, pairing modal, diagnostic cards, and notification center.
3. [`backend/api.py`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/backend/api.py) — REST endpoints for wearable connection state, active commands, test alerts, and authoritative ACK confirmation.
4. [`backend/wearable_gateway.py`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/backend/wearable_gateway.py) — Wearable Gateway HAL, `WaveCallPlusAdapter`, 7-state connection FSM, and capability reporting.
5. [`backend/db.py`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/backend/db.py) — Database schema (`wearable_devices`, `rescue_commands`, `notification_center`, `wearable_telemetry`).
6. [`scripts/android_companion_bridge.py`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/scripts/android_companion_bridge.py) — Python Android companion bridge for headless edge execution.
7. [`tests/test_real_wave_call_plus_hardware_ack_delivery.py`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/tests/test_real_wave_call_plus_hardware_ack_delivery.py) — Automated test suite for ACK separation, device validation, and lifecycle truth.

---

## 2. Functions Inspected

- **`isApprovedWearable(device)`** ([`frontend/js/bridge.js:261`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js#L261)): Strict exact allowlist validation on `device.name === "CALLPLUS_7F1B"`.
- **`resolveVerifiedCommandCharacteristic(discoveredCharacteristics, evidenceRegistry)`** ([`frontend/js/bridge.js:157`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js#L157)): Resolves command characteristic only if registered in `PROTOCOL_EVIDENCE_REGISTRY`. Returns `null` if unverified.
- **`resolveVerifiedAckCharacteristic(discoveredCharacteristics, evidenceRegistry)`** ([`frontend/js/bridge.js:195`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js#L195)): Resolves ACK characteristic only if registered in `PROTOCOL_EVIDENCE_REGISTRY`. Returns `null` if unverified.
- **`recordGattDiagnosticPacket(direction, serviceUuid, charUuid, dataBytes, note)`** ([`frontend/js/bridge.js:158`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js#L158)): Observe-first diagnostic sniffer recording raw hex dumps and ASCII interpretations into `window.GATT_DIAGNOSTIC_SNIFFER`.
- **`connectWebBluetooth()`** ([`frontend/js/bridge.js:940`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js#L940)): Primary connection flow, GATT service discovery, characteristic enumeration, and capability detection.
- **`sendRescueCommandThroughVerifiedGattChannel(cmd)`** ([`frontend/js/bridge.js:1400`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js#L1400)): Command dispatch handler. Fails closed safely (`DIRECT_GATT_UNVERIFIED`) when command channel is unverified.
- **`acceptEmergencyAlert(cmdId)`** ([`frontend/js/bridge.js:1300`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js#L1300)): Authoritative rescuer confirmation via `POST /api/wearable/commands/{cmdId}/ack?source=RESCUER_CONFIRMATION`.
- **`WaveCallPlusConnectionManager.connect(...)`** ([`backend/wearable_gateway.py:180`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/backend/wearable_gateway.py#L180)): Backend connection manager enforcing single-watch policy and 7-state FSM.

---

## 3. Current Data Flow

```text
┌───────────────────────────┐         HTTP Heartbeat (10s)         ┌───────────────────────────┐
│     RIDGEWATCH BACKEND    │ ◄──────────────────────────────────► │  ANDRIOD COMPANION PHONE  │
│  - rescue_commands (DB)   │                                      │  - bridge.html/bridge.js  │
│  - notification_center    │                                      │  - Phone GNSS (PHONE_GPS) │
└─────────────┬─────────────┘                                      └─────────────┬─────────────┘
              │                                                                  │
              │                                              Web Bluetooth Link  │ (0x180A, 0x180D,
              │                                                                  │  0x180F, 0xFEA0)
              │                                                                  ▼
              │                                                    ┌───────────────────────────┐
              │           Android OS Notification Mirroring        │   WAVE CALL PLUS WATCH    │
              └──────────────────────────────────────────────────► │     (CALLPLUS_7F1B)       │
                          (Visual Alert + Wrist Haptic)            │   CB:4E:FD:EE:7F:1B       │
                                                                   └───────────────────────────┘
```

---

## 4. Current Command Flow

1. **Mission Assignment**: Commander assigns a team to a victim via `POST /commander/assign`.
2. **Command Persisted**: Stored in SQLite `rescue_commands` with state `ASSIGNED`.
3. **Bridge Polling**: Rescuer phone polls `POST /api/wearable/bridge/heartbeat`, receiving the active command.
4. **Direct GATT Write Check**: `sendRescueCommandThroughVerifiedGattChannel(cmd)` checks `verifiedCommandCharacteristic`.
5. **Fail-Closed Safety**: Because `PROTOCOL_EVIDENCE_REGISTRY.commandChannels` is empty, direct write returns `DIRECT_GATT_UNVERIFIED`.
6. **Notification Mirroring**: The bridge triggers an Android System Notification (`Notification` API / Termux), which the phone OS mirrors over Bluetooth to the Wave Call Plus screen with haptic motor vibration.
7. **Delivery State**: Reported to backend as `PHONE_NOTIFICATION_POSTED` with `WATCH_DELIVERY_UNCONFIRMED`.

---

## 5. Current ACK Flow

1. **Physical Alert Display**: Watch displays mirrored notification banner and vibrates.
2. **Rescuer Action**: Rescuer taps **✅ ACCEPT MISSION** in the bridge UI.
3. **Authoritative ACK Request**: Browser dispatches `POST /api/wearable/commands/{command_id}/ack?source=RESCUER_CONFIRMATION`.
4. **Backend Validation**:
   - Validates command ID exists and is active.
   - Validates device is `DEV-WEARABLE-CALLPLUS`.
   - Records transition to `USER_ACCEPTED`.
   - Leaves physical hardware ACK separate (`watch_acknowledged = False`).
5. **Physical Hardware Return Path**: Awaiting real protocol framing evidence on `0xFEA2` to enable genuine `WATCH_ACKNOWLEDGED`.

---

## 6. Audit of Assumptions

| Area | Current System Handling | Verdict / Safety Status |
| :--- | :--- | :--- |
| **0xFEA0 Service Role** | Recognized as proprietary vendor sync service. Not assumed to be an open command terminal. | ✅ **SAFE** (Zero blind assumptions) |
| **0xFEA1 Characteristic** | Writable property noted, but direct raw ASCII/JSON injection is disabled. | ✅ **SAFE** (Fail-closed active) |
| **0xFEA2 Characteristic** | Notifiable property noted, but notifications are not assumed to be rescue ACKs. | ✅ **SAFE** (No synthetic ACKs) |
| **Device Identification** | Strict string match on `CALLPLUS_7F1B`. `T800`/`T800Ultra` rejected. | ✅ **SAFE** (Hardened allowlist) |
| **Telemetry vs Commands** | `0x180D` (PPG) and `0x180F` (Battery) treated strictly as read/notify telemetry. | ✅ **SAFE** (Zero cross-contamination) |
| **Location Tagging** | Tagged strictly as `PHONE_GPS`. Never claimed as `WATCH_GPS`. | ✅ **SAFE** (Honest sourcing) |

---

## 7. Confirmed Facts vs Unknown Facts

### Confirmed Facts:
1. **Device Identity**: Advertises as `CALLPLUS_7F1B` (MAC `CB:4E:FD:EE:7F:1B`, S/N `230105502503539`, Software `6.4.3582.28`, Manufacturer `boAt`).
2. **Standard GATT Services**: `0x1800` (Generic Access), `0x1801` (Generic Attribute), `0x180A` (Device Information), `0x180D` (Heart Rate PPG `0x2A37`), `0x180F` (Battery Level `0x2A19`) operate in full compliance with Bluetooth SIG standards.
3. **Notification Mirroring**: Android OS system notifications mirror to the watch screen and trigger wrist haptic motor vibration.
4. **State Separation**: `USER_ACCEPTED` (operator UI accept) and `WATCH_ACKNOWLEDGED` (physical BLE GATT return) are strictly decoupled.

### Unknown Facts (Requiring HCI Capture):
1. **Proprietary Packet Structure for `0xFEA1`**: The exact binary header bytes, opcode identifier, length field, and checksum algorithm expected by the Realtek RTOS binary parser.
2. **Proprietary Response Structure for `0xFEA2`**: The exact binary packet emitted when a user interacts with the watch display during an alert.
3. **Session Handshake / Encryption**: Whether the boAt Crest application negotiates an initial dynamic session key or auth challenge over `0xFEA1` prior to accepting alert packets.
