# RIDGEWATCH — Native Android Companion Application Architecture & User Guide

**Document ID:** `RIDGEWATCH-ANDROID-001`  
**Application Name:** RidgeWatch Companion  
**Package ID:** `org.ridgewatch.rescuer`  
**Target Smartwatch:** boAt Wave Call Plus (`CALLPLUS_7F1B` / MAC: `CB:4E:FD:EE:7F:1B`)  
**Target OS:** Android 7.0+ (API 24 to 36)  
**Date:** 2026-08-25  

---

## 1. Executive Summary & Purpose

The **RidgeWatch Native Android Companion Application** (`org.ridgewatch.rescuer`) is a dedicated, native Android application built using Kotlin and Jetpack Compose. It serves as an edge IoT rescue relay between the **RIDGEWATCH Survivor Detection Backend** and the rescuer's mobile phone / physical smartwatch.

```
┌─────────────────────────────────────────────────────────────┐
│                 RIDGEWATCH FASTAPI BACKEND                  │
│       (http://192.168.43.17:8000 / SQLite rescue_commands)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP Polling / Heartbeat
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             NATIVE ANDROID RIDGEWATCH COMPANION             │
│                 (org.ridgewatch.rescuer)                    │
│  - Android Foreground Service: RescuerPollingService        │
│  - Idempotency Ledger: SharedPreferences (Processed IDs)   │
│  - Configurable Backend URL (default: 192.168.43.17:8000)   │
│  - Rescuer Team / Member Profile (e.g. ALPHA / ALPHA-M001)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ NotificationManager.notify()
                               ▼
┌─────────────────────────────────────────────────────────────┐
│            ANDROID SYSTEM NOTIFICATION SERVICE              │
│  - Channel: RIDGEWATCH_EMERGENCY (IMPORTANCE_HIGH)          │
│  - Vibration: [500, 200, 500, 200, 500]                     │
│  - Category: NotificationCompat.CATEGORY_ALARM              │
└──────────────────────────────┬──────────────────────────────┘
                               │ NotificationListenerService
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 boAt CREST COMPANION APP                    │
│   (App Alerts / Notifications -> Realtek 0xFEA1 Binary TLV) │
└──────────────────────────────┬──────────────────────────────┘
                               │ Physical Bluetooth 5.0 LE
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             boAt WAVE CALL PLUS (CALLPLUS_7F1B)             │
│               (Wrist Vibration + Alert Display)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Strict Delivery State Integrity Guarantees

The application adheres to strict delivery honesty:

$$\mathbf{ANDROID\_NOTIFICATION\_POSTED} \ne \mathbf{WATCH\_ACKNOWLEDGED}$$
$$\mathbf{ANDROID\_APP\_RUNNING} \ne \mathbf{WATCH\_CONNECTED}$$
$$\mathbf{boAt\_CREST\_INSTALLED} \ne \mathbf{WATCH\_DELIVERED}$$

1. **Zero Fake ACKs**: When an emergency command arrives, posting a notification only reports `PHONE_NOTIFICATION_POSTED` to the backend. It NEVER forges `WATCH_ACKNOWLEDGED`.
2. **Fail-Closed Direct GATT Safety**: Because the vendor Realtek RTOS protocol on `0xFEA1` is proprietary, direct raw byte injection remains disabled (`UNVERIFIED`).
3. **Idempotency Protection**: Every command ID (e.g. `CMD-A8E328FA`) is recorded in the companion's local `SharedPreferences` ledger. Repeated heartbeat syncs, network reconnects, or app restarts will never produce duplicate notifications.

---

## 3. Key Technical Components

| Component | File Path | Purpose |
| :--- | :--- | :--- |
| **Data Models** | [`org.ridgewatch.rescuer.model.CommandModels.kt`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/android-companion/app/src/main/java/org/ridgewatch/rescuer/model/CommandModels.kt) | Encapsulates `RescueCommand`, `BridgeSyncRequest`, `BridgeSyncResponse`, and `CommandStatusReport`. |
| **API Client** | [`org.ridgewatch.rescuer.network.RidgeWatchApiClient.kt`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/android-companion/app/src/main/java/org/ridgewatch/rescuer/network/RidgeWatchApiClient.kt) | Asynchronous Coroutine HTTP client for heartbeat sync, active command polling, and status reporting with timeout guards. |
| **Notification Engine** | [`org.ridgewatch.rescuer.notification.EmergencyNotificationManager.kt`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/android-companion/app/src/main/java/org/ridgewatch/rescuer/notification/EmergencyNotificationManager.kt) | Configures the `RIDGEWATCH_EMERGENCY` high-importance notification channel with vibration patterns and builds emergency alerts. |
| **Background Service** | [`org.ridgewatch.rescuer.service.RescuerPollingService.kt`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/android-companion/app/src/main/java/org/ridgewatch/rescuer/service/RescuerPollingService.kt) | Persistent Android Foreground Service holding partial wake locks, polling the backend every 4 seconds, deduplicating alerts, and managing live state. |
| **Main Activity & UI** | [`org.ridgewatch.rescuer.ui.MainActivity.kt`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/android-companion/app/src/main/java/org/ridgewatch/rescuer/ui/MainActivity.kt) & [`RidgeWatchDashboard.kt`](file:///c:/Users/MADHAVAN/Downloads/the%20prefinal/survivor-detection-system-main/android-companion/app/src/main/java/org/ridgewatch/rescuer/ui/RidgeWatchDashboard.kt) | Jetpack Compose dashboard providing live connection status, active mission cards, notification permission requests, settings, and manual test alert triggers. |

---

## 4. Required Android Permissions

The application requests the following permissions in `AndroidManifest.xml`:
* `android.permission.INTERNET`: Connect to RIDGEWATCH backend over local Wi-Fi.
* `android.permission.ACCESS_NETWORK_STATE`: Monitor network connectivity state.
* `android.permission.POST_NOTIFICATIONS`: Runtime permission on Android 13+ (API 33+) to post alerts.
* `android.permission.VIBRATE`: Trigger physical motor vibration for emergency alerts.
* `android.permission.WAKE_LOCK`: Ensure the CPU processes mission-critical alerts when screen is locked.
* `android.permission.FOREGROUND_SERVICE`: Keep the background sync loop active while the rescuer is navigating.
* `android.permission.FOREGROUND_SERVICE_DATA_SYNC`: Declare foreground service type on Android 14+.

---

## 5. Build & Installation Instructions

### Option 1: Direct Download on Mobile Phone (Easiest)
1. Ensure your phone is connected to the same Wi-Fi as your laptop.
2. Open **Google Chrome** on your mobile phone and browse to:
   ```
   http://192.168.43.17:8000/frontend/apk/ridgewatch-companion.apk
   ```
3. Tap **Download** and then **Install**.

### Option 2: Install via ADB
Connect your phone via USB with USB Debugging enabled:
```bash
adb install android-companion/app/build/outputs/apk/debug/app-debug.apk
```

### Option 3: Rebuilding the APK from Source
```powershell
cd android-companion
python build_apk.py
```

---

## 6. Physical boAt Wave Call Plus Verification Procedure

1. **Step 1 — Launch & Grant Permissions**:
   * Open **RidgeWatch Companion** on your phone.
   * Tap **Grant Permission** when prompted for notification access.
2. **Step 2 — Verify Backend Connection**:
   * Verify the top status badge shows **ONLINE** (Green) and the backend card shows `● CONNECTED (200 OK)`.
   * If your laptop IP changed, tap ⚙️ (Settings), enter the new URL (e.g. `http://192.168.43.17:8000`), and tap Save.
3. **Step 3 — Configure boAt Crest App Alerts**:
   * Open the **boAt Crest** app on your phone.
   * Go to: `Device` $\rightarrow$ `Notification Alerts` (or `App Alerts`).
   * Enable the toggle for **RidgeWatch Companion** (and **Other Apps**).
   * Ensure your watch (`CALLPLUS_7F1B`) is synced and connected in boAt Crest.
4. **Step 4 — Trigger Test Alert**:
   * In RidgeWatch Companion app, tap **"🚨 Send Test RidgeWatch Notification"**.
   * Observe:
     * Phone vibrates and displays high-priority emergency notification.
     * boAt Wave Call Plus watch on wrist **vibrates** and **displays** the emergency alert!
5. **Step 5 — Real Mission Commander Dispatch**:
   * On your laptop Commander console, assign a mission to your team member.
   * The phone immediately displays the official `🚨 RIDGEWATCH — GO` mission alert.
