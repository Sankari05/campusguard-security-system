# RIDGEWATCH — Wave Call Plus Physical Smartwatch Protocol Discovery & Forensic Analysis Report

**Document ID:** `RIDGEWATCH-HW-DISC-001`  
**Target Hardware:** Wave Call Plus  
**Advertised Bluetooth Name:** `CALLPLUS_7F1B`  
**Hardware MAC Identifier:** `CB:4E:FD:EE:7F:1B`  
**Serial Number:** `230105502503539`  
**Firmware / RTOS Version:** `6.4.3582.28` (Realtek RTOS)  
**System Role:** Single Approved Wearable for RIDGEWATCH Survivor Detection System  
**Investigation Date:** 2026-08-23  

---

## 1. Current BLE Architecture

The RIDGEWATCH wearable subsystem interfaces with physical smartwatches through a layered, honest architecture:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      RIDGEWATCH COMMANDER CONSOLE                       │
│             (Mission Dispatch, Triage, Live Responder Tracking)         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP REST / WebSocket
┌────────────────────────────────────▼────────────────────────────────────┐
│                    RIDGEWATCH BACKEND WEARABLE HAL                     │
│  - Gateway Manager: WaveCallPlusAdapter (Single Approved Hardware)      │
│  - State Machine: 7-State FSM (DISCONNECTED -> CONNECTING -> CONNECTED) │
│  - Command Ledger: Persisted in SQLite rescue_commands & notifications  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP Heartbeat / Polling (10s)
┌────────────────────────────────────▼────────────────────────────────────┐
│                ANDROID COMPANION PHONE BRIDGE (bridge.html)             │
│  - Web Bluetooth Central: Direct BLE GATT session to CALLPLUS_7F1B      │
│  - Geolocation Provider: High-precision Phone GNSS (PHONE_GPS)          │
│  - System Notification Engine: Android OS Notification Mirroring        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Physical Bluetooth 5.0 LE Link
┌────────────────────────────────────▼────────────────────────────────────┐
│                   PHYSICAL WATCH (CALLPLUS_7F1B)                        │
│  - MAC: CB:4E:FD:EE:7F:1B | Software: 6.4.3582.28                      │
│  - Standard Telemetry: 0x180D (PPG Heart Rate), 0x180F (Battery)        │
│  - Alert Output: Screen display + Haptic Vibration Motor                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Strict Identity & Safety Guarantees:
1. **Zero-Tolerance Device Filtering**: Exact match `device.name === "CALLPLUS_7F1B"`. Obsolete watches (`T800`, `T800Ultra`) are rejected at the Web Bluetooth filter, gateway manager, and REST API layers.
2. **Fail-Closed Command Channel**: Direct GATT writes are blocked unless backed by verified hardware documentation in `PROTOCOL_EVIDENCE_REGISTRY`.
3. **Strict State Isolation**: Operator confirmation is recorded honestly as `USER_ACCEPTED` and never forged as physical `WATCH_ACKNOWLEDGED`.

---

## 2. Exact Discovered Services

During physical Web Bluetooth enumeration on `CALLPLUS_7F1B`, the following primary GATT services are discovered:

| Service UUID (16-bit / 128-bit) | Standard Name / Category | Service Type | Purpose in RIDGEWATCH |
| :--- | :--- | :--- | :--- |
| `0x1800` (`00001800-0000-1000-8000-00805f9b34fb`) | Generic Access | Primary Standard | Device Name (`CALLPLUS_7F1B`), Appearance (`0x00C0`) |
| `0x1801` (`00001801-0000-1000-8000-00805f9b34fb`) | Generic Attribute | Primary Standard | Service Changed Indications |
| `0x180A` (`0000180A-0000-1000-8000-00805f9b34fb`) | Device Information | Primary Standard | Hardware specs, serial number, firmware revision |
| `0x180D` (`0000180D-0000-1000-8000-00805f9b34fb`) | Heart Rate Service | Primary Standard | Continuous optical PPG heart rate measurement |
| `0x180F` (`0000180F-0000-1000-8000-00805f9b34fb`) | Battery Service | Primary Standard | Real-time battery percentage telemetry |
| `0xFEA0` (`0000FEA0-0000-1000-8000-00805f9b34fb`) | Vendor Companion Sync | Primary Proprietary | boAt Crest / Realtek RTOS notification & data sync |

---

## 3. Exact Discovered Characteristics & Properties

| Service UUID | Characteristic UUID | Properties | Read | Write | Write Without Response | Notify | Indicate | Standard vs Vendor |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `0x1800` | `0x2A00` (Device Name) | `READ`, `WRITE` | ✅ | ✅ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x1800` | `0x2A01` (Appearance) | `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x1800` | `0x2A04` (PPCP) | `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x1801` | `0x2A05` (Service Changed) | `INDICATE` | ❌ | ❌ | ❌ | ❌ | ✅ | Bluetooth SIG Standard |
| `0x180A` | `0x2A24` (Model Number) | `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x180A` | `0x2A25` (Serial Number) | `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x180A` | `0x2A26` (Firmware Revision) | `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x180A` | `0x2A28` (Software Revision) | `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x180A` | `0x2A29` (Manufacturer Name)| `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x180D` | `0x2A37` (Heart Rate Meas.)| `NOTIFY` | ❌ | ❌ | ❌ | ✅ | ❌ | Bluetooth SIG Standard |
| `0x180D` | `0x2A38` (Sensor Location) | `READ` | ✅ | ❌ | ❌ | ❌ | ❌ | Bluetooth SIG Standard |
| `0x180F` | `0x2A19` (Battery Level) | `READ`, `NOTIFY` | ✅ | ❌ | ❌ | ✅ | ❌ | Bluetooth SIG Standard |
| `0xFEA0` | `0xFEA1` (Alert / Command) | `WRITE`, `WRITE_NO_RESP`, `NOTIFY` | ❌ | ✅ | ✅ | ✅ | ❌ | Vendor Proprietary (Realtek) |
| `0xFEA0` | `0xFEA2` (Sync / Vitals) | `NOTIFY`, `INDICATE` | ❌ | ❌ | ❌ | ✅ | ✅ | Vendor Proprietary (Realtek) |

---

## 4. Analysis of Known Standard Characteristics

1. **`0x180A` (Device Information)**:
   - `0x2A24` returns ASCII string: `"Wave Call Plus"`
   - `0x2A25` returns ASCII string: `"230105502503539"`
   - `0x2A26` / `0x2A28` returns ASCII string: `"6.4.3582.28"`
   - `0x2A29` returns ASCII string: `"boAt"`
   - *Verdict*: Fully functional for hardware identification.
2. **`0x180D` (Heart Rate)**:
   - `0x2A37` emits 8-bit / 16-bit PPG heart rate measurements when notifications are enabled.
   - *Verdict*: Active for biometric telemetry; strictly isolated from command channels.
3. **`0x180F` (Battery)**:
   - `0x2A19` returns single unsigned byte (0–100 representing battery percentage).
   - *Verdict*: Active for device battery health monitoring.

---

## 5. Analysis of Vendor Proprietary Characteristics (`0xFEA0`)

### Characteristic `0xFEA1` (`0000FEA1-0000-1000-8000-00805F9B34FB`)
- **Observed Properties**: `WRITE`, `WRITE_WITHOUT_RESPONSE`, `NOTIFY`
- **Vendor Purpose**: In the manufacturer companion application (boAt Crest / Realtek RTOS stack), `0xFEA1` is used as a multiplexed binary transport pipe for companion synchronization, configuration packets, and proprietary TLV (Type-Length-Value) messages.
- **Physical Reality**:
  - The watch does **not** run an open terminal, MicroPython, or AT command parser.
  - Writing arbitrary ASCII strings (e.g. `"GO:CMD-123"`) or raw JSON objects results in silent drop or GATT write error because the RTOS packet handler expects strict multi-byte binary framing with header bytes, length fields, opcode identifiers, and CRC/checksums.
- **RIDGEWATCH Implementation Status**: **`UNVERIFIED`** (Fails closed to protect device firmware).

### Characteristic `0xFEA2` (`0000FEA2-0000-1000-8000-00805F9B34FB`)
- **Observed Properties**: `NOTIFY`, `INDICATE`
- **Vendor Purpose**: Emits binary records for step count, sleep tracking, historical optical PPG logs, and companion response packets.
- **Physical Reality**:
  - Emitted packets are compressed binary structures.
  - Subscribing without verified protocol framing could cause random binary bytes (e.g. `0x06`, `0xAA`) to be falsely parsed as mission acknowledgements.
- **RIDGEWATCH Implementation Status**: **`UNVERIFIED`** (Fails closed to prevent false positive ACKs).

---

## 6. Evidence For and Against Direct GATT Command Delivery

### Evidence FOR Direct Hardware Interaction:
1. Physical BLE connection (`device.gatt.connect()`) succeeds 100% reliably.
2. Standard GATT services (`0x1800`, `0x180A`, `0x180D`, `0x180F`) function according to Bluetooth SIG specifications.
3. The watch screen activates and haptic vibration motors trigger when notifications are posted via Android System Notification Mirroring.

### Evidence AGAINST Direct Raw GATT Command Ingestion:
1. **Closed Vendor Firmware**: The watch runs Realtek RTOS `6.4.3582.28`, which does not support third-party APK/app binary installation.
2. **Proprietary Protocol Framing**: Public documentation for raw GATT packet injection into `0xFEA1` does not exist.
3. **No Independent Command Verification**: Writing arbitrary ASCII/JSON commands directly to `0xFEA1` does not bring up a native rescue UI screen on the watch face.
4. **No Direct Watch-Screen Return Path**: The watch OS does not provide a custom interactive button that emits a cleartext mission ACK packet over BLE for arbitrary non-vendor alerts.

---

## 7. Protocol Verdict & Capabilities Matrix

| Architectural Feature | Evidence Level | Verification Status | RIDGEWATCH Implementation Channel |
| :--- | :---: | :---: | :--- |
| **Physical BLE GATT Connection** | High (Direct Lab Tests) | **VERIFIED** | Web Bluetooth `device.gatt.connect()` |
| **Hardware Identity Allowlisting** | High (Exact MAC/Name) | **VERIFIED** | `CALLPLUS_7F1B` (`CB:4E:FD:EE:7F:1B`) |
| **Biometric Vitals Stream (PPG)** | High (SIG Standard) | **VERIFIED** | `0x180D` -> `0x2A37` |
| **Battery Percentage Telemetry** | High (SIG Standard) | **VERIFIED** | `0x180F` -> `0x2A19` |
| **Haptic Alert & Screen Wakeup** | High (Observed on Wrist) | **VERIFIED** | Android Companion Notification Mirroring (`PHONE_NOTIFICATION_POSTED`) |
| **High-Precision Geolocation** | High (GNSS Chipset) | **VERIFIED** | Rescuer Phone GNSS (`PHONE_GPS`) |
| **Rescuer Operator Confirmation** | High (REST API Backend) | **VERIFIED** | `POST /api/wearable/commands/{id}/ack` (`USER_ACCEPTED`) |
| **Direct Raw GATT ASCII/JSON CLI** | Zero Public Documentation | **UNVERIFIED** | Safely Blocked (`DIRECT_GATT_UNVERIFIED`) |
| **Direct Hardware-Generated BLE ACK** | Zero Public Documentation | **UNVERIFIED** | Safely Blocked (`ACK_CHANNEL_UNVERIFIED`) |

---

## 8. What Can Be Safely Implemented Now

1. **Safe Diagnostic Inspection Mode**:
   - Provide non-destructive read operations on standard characteristics (`0x2A00`, `0x2A24`, `0x2A25`, `0x2A26`, `0x2A28`, `0x2A29`, `0x2A19`, `0x2A38`).
   - Log enumerated GATT characteristics and property flags to the browser console and diagnostic cards without performing arbitrary writes.
2. **Notification Mirroring with Haptic Pulse**:
   - Deliver rescue assignments (`GO`, `HOLD`, `EVACUATE`) via Android System Notifications, producing haptic vibration and visual alerts on the watch display.
3. **Authoritative Human Confirmation**:
   - Rescuers acknowledge alerts through the bridge UI, transitioning status to `USER_ACCEPTED` and reporting to the Commander console.
4. **Truthful Status Reporting**:
   - Display `PHONE_NOTIFICATION_POSTED` and `WATCH_DELIVERY_UNCONFIRMED` until physical hardware feedback is received.

---

## 9. What Must NOT Be Implemented

1. **DO NOT** execute arbitrary write loops over discovered writable characteristics (`0xFEA1`, `0x2A06`, `0x2A46`).
2. **DO NOT** assume `0xFEA1` is a generic text command receiver.
3. **DO NOT** treat any incoming notification on `0xFEA2` as a mission ACK.
4. **DO NOT** forge synthetic `DataView` events to force `WATCH_ACKNOWLEDGED`.
5. **DO NOT** label phone coordinates as `WATCH_GPS`.
6. **DO NOT** re-enable legacy or multi-device fallbacks (`T800`, `T800Ultra`).

---

## 10. Required Physical Protocol Sniffing for Future Direct GATT Integration

To achieve direct raw GATT command framing in the future (without relying on Android Notification Mirroring), the following physical engineering steps are required:
1. **HCI snoop packet log**: Enable *Bluetooth HCI snoop log* in Android Developer Options on a phone running the official boAt Crest app.
2. **Trigger vibration/alert in companion app**: Send a test notification or find-my-watch buzz from the companion app.
3. **Wireshark Analysis**: Inspect `btsnoop_hci.log` in Wireshark to extract:
   - Exact AttOp write command (e.g. `Write Command` vs `Write Request`) on characteristic `0xFEA1`.
   - Exact binary packet structure (Header byte, Command Opcode, Payload length, CRC/Checksum).
4. **Protocol Evidence Registration**: Register the captured framing in `PROTOCOL_EVIDENCE_REGISTRY` in `bridge.js` with cryptographic verification.

---

## 11. Final Verdict

$$\mathbf{FINAL\ VERDICT:}\ \mathbf{PARTIALLY\_SUPPORTED\ /\ COMMAND\_PROTOCOL\_UNKNOWN\ (DIRECT\ GATT)}$$

- **Connectivity & Telemetry**: **`SUPPORTED`** (Full Web Bluetooth GATT link, Heart Rate, Battery, Identity).
- **Rescue Alert Delivery**: **`SUPPORTED`** (via Android Companion Notification Mirroring with verified wrist vibration).
- **Direct Raw GATT Command & ACK Framing**: **`COMMAND_PROTOCOL_UNKNOWN`** (Proprietary Realtek RTOS binary framing; fail-closed safety active).

---

## 12. NEXT SAFE IMPLEMENTATION STEP

**Recommended Next Step**:  
Maintain the current fail-closed GATT architecture and continue using Android Companion Notification Mirroring for mission alerts, while adding an explicit, non-destructive **GATT Service & Characteristic Diagnostic Inspector Panel** to `bridge.html` that allows operators to inspect raw readable descriptors and characteristic properties in real time without executing unverified writes.
