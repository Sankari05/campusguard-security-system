# RIDGEWATCH — Wave Call Plus Bluetooth HCI Snoop Capture & Protocol Reverse-Engineering Guide

**Document ID:** `RIDGEWATCH-GUIDE-HCI-CAPTURE`  
**Target Hardware:** Wave Call Plus (`CALLPLUS_7F1B` / `CB:4E:FD:EE:7F:1B`)  
**Manufacturer App:** boAt Crest (Android / iOS)  
**Objective:** Non-destructively capture authentic Bluetooth HCI packet traces between an Android phone and the Wave Call Plus smartwatch during legitimate watch-control operations (e.g., Find Watch, Vibrate/Buzz, Notification Sync) to extract the proprietary binary packet framing for characteristic `0xFEA1` and response framing for `0xFEA2`.

---

## 1. Prerequisites & Safety Rules

- **Zero Risk to Hardware**: This process performs passive packet logging at the Android Bluetooth Host Controller Interface (HCI). It does **not** flash, modify, or stress the watch firmware.
- **Tools Required**:
  - Android Smartphone (Android 9.0+) with Developer Options enabled.
  - Official **boAt Crest** application installed and paired with `CALLPLUS_7F1B`.
  - USB Cable connecting the phone to a development PC with `adb` (Android Debug Bridge) installed.
  - **Wireshark** (v3.4+) on PC for packet analysis.

---

## 2. Step-by-Step Android HCI Snoop Logging Procedure

### Step 1: Enable Developer Options & USB Debugging
1. Open **Settings** on the Android phone.
2. Go to **About Phone** ➔ Tap **Build Number** 7 times until you see `"You are now a developer!"`.
3. Go back to **Settings** ➔ **System** ➔ **Developer Options**.
4. Enable **USB Debugging**.

### Step 2: Enable Bluetooth HCI Snoop Log
1. In **Developer Options**, scroll to the **Networking** section.
2. Locate **Enable Bluetooth HCI snoop log** (or *Bluetooth HCI snoop log*).
3. Toggle it to **Enabled** (or select *Enabled (all)* if a dropdown is present).
4. **Crucial**: Toggle **Bluetooth OFF and then ON again** (or restart the phone) for the logging daemon to initialize the capture buffer.

### Step 3: Execute Target Physical Watch Operations
1. Open the **boAt Crest** app and verify the watch is connected.
2. Note the exact timestamp (down to the second).
3. Execute the target actions in sequence with a 10-second gap between each:
   - **Action A: Find My Watch** (Triggers watch screen and vibration motor).
   - **Action B: Notification Test** (Send a test SMS notification to trigger watch alert banner).
   - **Action C: Sync Data** (Trigger pull-to-refresh sync for steps/heart rate).
4. Record the exact action and time (e.g., `14:22:15 - Tapped Find Watch in boAt Crest`).

### Step 4: Disable HCI Snoop Log
1. Return to **Developer Options** ➔ Turn **Bluetooth HCI snoop log** to **Disabled**.
2. This flushes the kernel log buffer to disk.

---

## 3. Extracting the Log to Development PC

Depending on the Android version and manufacturer (Samsung, Google Pixel, Xiaomi, OnePlus), the HCI log is stored in one of two ways:

### Method A: Direct ADB Pull (Rooted / Certain OEM Builds)
Run in PowerShell on your PC:
```powershell
# Standard AOSP path
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log ./btsnoop_hci.log

# Alternative paths on older/OEM builds
adb pull /sdcard/btsnoop_hci.log ./btsnoop_hci.log
adb pull /data/log/bt/btsnoop_hci.log ./btsnoop_hci.log
```

### Method B: Via Android Bug Report (Universal / Non-Rooted)
If direct pull returns `Permission Denied`, use the standard Android Bug Report mechanism:
```powershell
# 1. Generate full bugreport zip
adb bugreport ./bugreport.zip

# 2. Extract the zip and locate btsnoop_hci.log
# Location inside zip is typically:
# FS/data/misc/bluetooth/logs/btsnoop_hci.log
# or FS/data/log/bt/btsnoop_hci.log
```

---

## 4. Analyzing the Capture in Wireshark

1. Launch **Wireshark** on your PC.
2. Open `btsnoop_hci.log` (`File` ➔ `Open`).
3. Apply the display filter for the Wave Call Plus Bluetooth MAC address:
   ```text
   bluetooth.addr == cb:4e:fd:ee:7f:1b
   ```

### 4.1. Identifying Writes to Characteristic `0xFEA1`
1. Filter for ATT (Attribute Protocol) write operations:
   ```text
   btatt.opcode == 0x12 || btatt.opcode == 0x52
   ```
   *(Note: `0x12` = ATT Write Request; `0x52` = ATT Write Command / Write Without Response).*
2. Locate the **Attribute Handle** corresponding to UUID `0xFEA1` (discovered during the GATT primary service exchange in the capture).
3. Inspect the **Value** hex bytes payload.

### 4.2. Identifying Notifications from Characteristic `0xFEA2`
1. Filter for ATT notifications and indications:
   ```text
   btatt.opcode == 0x1b || btatt.opcode == 0x1d
   ```
   *(Note: `0x1B` = ATT Handle Value Notification; `0x1D` = ATT Handle Value Indication).*
2. Locate the Attribute Handle for UUID `0xFEA2`.
3. Inspect the emitted hex payload.

---

## 5. Packet Framing Classification Criteria

When analyzing captured hex bytes, classify each segment using strict evidence criteria:

| Packet Field | Evidence Requirement for CONFIRMED Status | Classification |
| :--- | :--- | :--- |
| **Preamble / Magic Byte** | Exact constant byte(s) (e.g. `0xAA`, `0x55`, `0xAB`) present at index 0 across multiple distinct operations. | `CONFIRMED` / `PROBABLE` |
| **Opcode / Command ID** | Specific byte varying predictably with action (e.g., `0x01` for Find Watch, `0x05` for Notification). | `CONFIRMED` / `PROBABLE` |
| **Length Byte** | Byte matching `(total_packet_length - header_offset)`. | `CONFIRMED` |
| **Payload Data** | Title, body, or vibration pattern parameters. | `CONFIRMED` |
| **Checksum / CRC** | Byte matching XOR / Sum8 / CRC16 of preceding bytes across multiple captures. | `CONFIRMED` / `PROBABLE` |

---

## 6. Registering Confirmed Evidence in RIDGEWATCH

Once packet framing is verified across $\ge 3$ distinct captures:
1. Update `PROTOCOL_EVIDENCE_REGISTRY` in [`frontend/js/bridge.js`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/frontend/js/bridge.js):
   ```javascript
   const PROTOCOL_EVIDENCE_REGISTRY = Object.freeze({
     commandChannels: [
       {
         serviceUuid: "0000fea0-0000-1000-8000-00805f9b34fb",
         characteristicUuid: "0000fea1-0000-1000-8000-00805f9b34fb",
         direction: "OUTGOING",
         operation: "FIND_WATCH_VIBRATION_ALERT",
         packetFormat: "BINARY_REALTEK_TLV",
         evidenceSource: "HCI_SNOOP_CAPTURE_BOAT_CREST_2026",
         confidence: "CONFIRMED"
       }
     ],
     ackChannels: [
       // Registered only if physical return packet is proven
     ]
   });
   ```
2. Run pytest verification:
   ```powershell
   python -m pytest tests/test_real_wave_call_plus_hardware_ack_delivery.py -v
   ```
