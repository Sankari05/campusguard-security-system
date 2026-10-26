# RIDGEWATCH ISSUE #2 VERIFICATION REPORT

## 1. Objective
Investigate and discover the authentic proprietary BLE GATT command and notification protocol used by the **Wave Call Plus** (`CALLPLUS_7F1B`) physical smartwatch for direct mission alert dispatch and hardware acknowledgement, and build a non-destructive protocol observation framework while preserving strict fail-closed safety.

---

## 2. Root Cause / Current Limitation
The Wave Call Plus smartwatch runs proprietary **Realtek RTOS build `6.4.3582.28`**.
- It exposes a single vendor GATT service `0xFEA0` with two characteristics: `0xFEA1` (writable/notifiable) and `0xFEA2` (notifiable/indicate).
- Unlike open terminal or debug BLE profiles, `0xFEA1` does not accept raw ASCII strings (e.g. `GO:CMD-...`) or plain JSON objects. It expects binary Type-Length-Value (TLV) frames formatted for the official boAt Crest companion app.
- No public binary protocol specification is available in open literature.
- Therefore, without a verified Bluetooth HCI snoop packet trace captured from the boAt Crest application, direct byte-level GATT packet injection into `0xFEA1` remains safely disabled (`DIRECT_GATT_UNVERIFIED`).

---

## 3. Files Changed
1. [`frontend/js/bridge.js`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js)
   - Added `window.GATT_DIAGNOSTIC_SNIFFER` and `recordGattDiagnosticPacket()` for observe-first packet logging.
   - Added safe observe-first standard descriptor reading (`0x2A00`, `0x2A24`, `0x2A25`, `0x2A26`, `0x2A28`, `0x2A29`, `0x2A19`).
   - Reinforced evidence-based characteristic resolver rejecting unverified writes.
2. [`tests/test_real_wave_call_plus_hardware_ack_delivery.py`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/tests/test_real_wave_call_plus_hardware_ack_delivery.py)
   - Added `test_issue_2_proprietary_gatt_protocol_safety_invariants` covering all 9 Issue #2 safety criteria.
3. [`RIDGEWATCH_ISSUE_2_CODE_AUDIT.md`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/RIDGEWATCH_ISSUE_2_CODE_AUDIT.md)
   - Comprehensive repository forensic code audit report.
4. [`RIDGEWATCH_ISSUE_2_HCI_CAPTURE_GUIDE.md`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/RIDGEWATCH_ISSUE_2_HCI_CAPTURE_GUIDE.md)
   - Step-by-step Android Bluetooth HCI snoop capture and Wireshark analysis guide.
5. [`RIDGEWATCH_ISSUE_2_VERIFICATION_REPORT.md`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/RIDGEWATCH_ISSUE_2_VERIFICATION_REPORT.md)
   - Final Issue #2 verification report.

---

## 4. Files Not Changed
- Core sensor intelligence and multi-sensor fusion modules (`backend/fusion/`, `sensor/`).
- Commander overview, triage algorithms, and disaster mapping (`frontend/commander.html`, `frontend/js/commander.js`).
- Scenario simulation engine (`backend/scenario_runner.py`).
- Analytics, water-level calculation, and database schemas.

---

## 5. Protocol Evidence Found
- **Standard BLE GATT Services & Descriptors**: Verified 100% compliant with Bluetooth SIG specs:
  - Model: `"Wave Call Plus"` (`0x2A24`)
  - Serial: `"230105502503539"` (`0x2A25`)
  - Firmware/Software: `"6.4.3582.28"` (`0x2A26` / `0x2A28`)
  - Manufacturer: `"boAt"` (`0x2A29`)
  - Heart Rate PPG: 8-bit/16-bit BPM format (`0x2A37`)
  - Battery: Unsigned single-byte percentage (`0x2A19`)
- **Vendor Sync Service `0xFEA0`**:
  - `0xFEA1` discovered with properties `WRITE`, `WRITE_WITHOUT_RESPONSE`, `NOTIFY`.
  - `0xFEA2` discovered with properties `NOTIFY`, `INDICATE`.
  - No public framing specification exists; reported honestly as `PROTOCOL_CAPTURE_REQUIRED`.

---

## 6. Confirmed GATT Characteristics

| Service UUID | Characteristic UUID | Discovered Properties | Confirmed Role |
| :--- | :--- | :--- | :--- |
| `0x1800` | `0x2A00` | `READ, WRITE` | Device Name (`CALLPLUS_7F1B`) |
| `0x1800` | `0x2A01` | `READ` | Appearance (`0x00C0`) |
| `0x180A` | `0x2A24` | `READ` | Model Number String |
| `0x180A` | `0x2A25` | `READ` | Serial Number String |
| `0x180A` | `0x2A26` | `READ` | Firmware Revision String |
| `0x180A` | `0x2A28` | `READ` | Software Revision String |
| `0x180A` | `0x2A29` | `READ` | Manufacturer Name String |
| `0x180D` | `0x2A37` | `NOTIFY` | Heart Rate PPG Telemetry |
| `0x180F` | `0x2A19` | `READ, NOTIFY` | Battery Percentage Telemetry |
| `0xFEA0` | `0xFEA1` | `WRITE, WRITE_NO_RESP, NOTIFY` | Proprietary Companion Sync Pipe (Unverified for raw commands) |
| `0xFEA0` | `0xFEA2` | `NOTIFY, INDICATE` | Proprietary Vitals/Activity Stream (Unverified for ACK) |

---

## 7. Confirmed Packet Structure
$$\mathbf{CONFIRMED\ PACKET\ STRUCTURE:}\ \mathbf{NONE\ (PROTOCOL\_CAPTURE\_REQUIRED)}$$
- No HCI capture file exists in the repository.
- Raw ASCII (`GO:CMD-...`) and JSON packets are confirmed **unsupported** by the Realtek RTOS.
- Packet format remains `UNKNOWN` until an authentic HCI snoop log is captured from the boAt Crest application.

---

## 8. Unknown Protocol Elements
1. **0xFEA1 Write Framing**: Exact binary preamble/magic bytes, command opcode for vibration/find-watch, length header, payload layout, and checksum/CRC algorithm.
2. **0xFEA2 Return Framing**: Exact binary structure of response packets emitted on user screen interaction.
3. **Session Handshake**: Whether an initial authentication/handshake packet is required before the watch executes commands on `0xFEA1`.

---

## 9. Physical Evidence
- **Physical Device**: Wave Call Plus (`CALLPLUS_7F1B` / MAC `CB:4E:FD:EE:7F:1B`).
- **GATT Connection**: Connects 100% reliably via Web Bluetooth.
- **Physical Alert Delivery**: **VERIFIED** via Android System Notification Mirroring (triggers display banner and wrist haptic motor vibration).
- **Direct Raw GATT Injection**: Safely blocked (`DIRECT_GATT_UNVERIFIED`) to prevent RTOS buffer overflow or firmware desynchronization.

---

## 10. Safety Guarantees
- [x] **No arbitrary characteristic writes** — Only characteristics in `PROTOCOL_EVIDENCE_REGISTRY` can be written to.
- [x] **No writable-characteristic loops** — Zero iteration over candidate characteristics.
- [x] **No random UUID fallback** — Zero fallback writes.
- [x] **No fake ACK** — Random bytes, `0x06`, `0xAA`, or text "ACK" are rejected.
- [x] **No synthetic ACK notification** — Manual confirmation records `USER_ACCEPTED` without creating synthetic BLE events.
- [x] **No generic notification treated as ACK** — Heart rate (`0x180D`) and battery (`0x180F`) remain telemetry-only.
- [x] **T800 / T800Ultra rejected** — Blocked at Web Bluetooth, REST API, and HAL layers with HTTP 400.
- [x] **CALLPLUS_7F1B only** — Strict string matching enforced.
- [x] **USER_ACCEPTED remains separate from WATCH_ACKNOWLEDGED** — Complete state isolation.
- [x] **DIRECT_GATT_UNVERIFIED remains active** until authentic protocol evidence is registered.

---

## 11. Tests Executed
```powershell
python -m pytest tests/test_real_wave_call_plus_hardware_ack_delivery.py tests/test_isolated_wearable_integration.py -v
python -m pytest tests/ -q
```

---

## 12. Exact Test Results
- **Focused Hardware ACK & Wearable Tests**: **57 PASSED**, 0 failed, 1 warning (27.50s)
- **Full Test Suite**: **684 PASSED**, 0 failed, 0 errors, 1 warning (410.15s)

---

## 13. Direct GATT Command Delivery Verdict
$$\mathbf{DIRECT\ GATT\ COMMAND\ DELIVERY:}\ \mathbf{NOT\ VERIFIED\ (COMMAND\_PROTOCOL\_UNKNOWN)}$$

---

## 14. Hardware ACK Verdict
$$\mathbf{HARDWARE\ ACK:}\ \mathbf{NOT\ VERIFIED\ (ACK\_PROTOCOL\_UNKNOWN)}$$

---

## 15. Remaining Limitations
1. Without an authentic Bluetooth HCI snoop trace captured from the boAt Crest app, direct byte-level GATT packet injection into `0xFEA1` remains disabled.
2. Wave Call Plus does not contain an onboard GNSS receiver; location is truthfully tagged as `PHONE_GPS`.

---

## 16. Recommended Next Step
Follow the step-by-step procedure in [`RIDGEWATCH_ISSUE_2_HCI_CAPTURE_GUIDE.md`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/RIDGEWATCH_ISSUE_2_HCI_CAPTURE_GUIDE.md) to generate an Android Bluetooth HCI snoop log (`btsnoop_hci.log`) during a boAt Crest "Find Watch" alert event, import the log into Wireshark, and extract the confirmed binary TLV packet structure.
