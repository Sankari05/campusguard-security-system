package org.ridgewatch.rescuer.service

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.ServiceInfo
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.ServiceCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.ridgewatch.rescuer.location.RescuerLocationTracker
import org.ridgewatch.rescuer.model.BridgeSyncRequest
import org.ridgewatch.rescuer.model.RescueCommand
import org.ridgewatch.rescuer.network.RidgeWatchApiClient
import org.ridgewatch.rescuer.notification.EmergencyNotificationManager
import org.ridgewatch.rescuer.sms.EmergencySmsManager
import org.ridgewatch.rescuer.sms.SmsResult
import java.util.UUID

/**
 * Android Foreground Service maintaining live heartbeat with RIDGEWATCH backend.
 * Integrates Stage 3 Real GPS Tracking strictly for Alpha Member 1 upon Mission Acceptance.
 *
 * Strict Invariants:
 * - Real GPS activates ONLY for Alpha Member 1 after mission is ACCEPTED.
 * - Alpha Member 2, Bravo 1 & 2 remain simulation-only (no real GPS).
 * - Stale threshold: 15s preserves last fix, never generates fake coordinates.
 * - Non-forgery guarantee: physical watch ACK remains uncoupled from phone GPS.
 */
class RescuerPollingService : Service() {

    companion object {
        const val TAG = "RescuerService"
        const val PREFS_NAME = "ridgewatch_companion_prefs"
        const val KEY_POSTED_COMMANDS = "posted_command_ids"
        const val KEY_POSTED_JOBS = "posted_job_assignment_ids"
        const val KEY_SMS_POSTED_COMMANDS = "sms_posted_command_ids"
        const val KEY_BACKEND_URL = "backend_url"
        const val KEY_TEAM_ID = "team_id"
        const val KEY_MEMBER_ID = "member_id"
        const val KEY_SMS_ENABLED = "sms_emergency_enabled"
        const val KEY_EMERGENCY_CONTACT = "emergency_contact_phone"
        const val DEFAULT_BACKEND_URL = "http://192.168.43.17:8000"
        const val DEFAULT_TEAM_ID = "ALPHA"
        const val DEFAULT_MEMBER_ID = "ALPHA-M001"
        const val DEFAULT_SMS_ENABLED = false
        const val DEFAULT_EMERGENCY_CONTACT = ""
        const val POLL_INTERVAL_MS = 3500L

        private var instance: RescuerPollingService? = null
        private val _serviceState = MutableStateFlow(ServiceStatus())
        val serviceState: StateFlow<ServiceStatus> = _serviceState.asStateFlow()

        fun getInstance(): RescuerPollingService? = instance

        fun startService(context: Context) {
            try {
                val intent = Intent(context, RescuerPollingService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start RescuerPollingService: ${e.message}", e)
            }
        }

        fun stopService(context: Context) {
            try {
                val intent = Intent(context, RescuerPollingService::class.java)
                context.stopService(intent)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to stop RescuerPollingService: ${e.message}", e)
            }
        }

        fun updateServiceStateSms(enabled: Boolean, contact: String, smsStatus: String? = null) {
            _serviceState.value = _serviceState.value.copy(
                isSmsEnabled = enabled,
                emergencyContact = contact,
                smsStatus = smsStatus ?: if (!enabled) "DISABLED" else if (contact.isBlank()) "CONTACT_REQUIRED" else "READY"
            )
        }

        fun acceptMission(commandId: String) {
            instance?.acceptMission(commandId) ?: run {
                _serviceState.value = _serviceState.value.copy(
                    isMissionAccepted = true,
                    lastCommand = _serviceState.value.lastCommand?.copy(status = "ACCEPTED")
                )
            }
        }

        fun acceptWorkAssignment(assignmentId: String) {
            instance?.acceptWorkAssignment(assignmentId) ?: run {
                _serviceState.value = _serviceState.value.copy(
                    isJobAccepted = true,
                    lastJobAssignment = _serviceState.value.lastJobAssignment?.copy(status = "ACCEPTED")
                )
            }
        }

        fun notifyLocationPermissionResult(granted: Boolean) {
            instance?.onLocationPermissionResult(granted) ?: run {
                if (!granted) {
                    _serviceState.value = _serviceState.value.copy(gpsStatus = "PERMISSION_DENIED")
                }
            }
        }
    }

    data class ServiceStatus(
        val isRunning: Boolean = false,
        val isBackendConnected: Boolean = false,
        val lastSyncTimestamp: Long = 0,
        val lastCommand: RescueCommand? = null,
        val isMissionAccepted: Boolean = false,
        val lastJobAssignment: org.ridgewatch.rescuer.model.JobAssignment? = null,
        val isJobAccepted: Boolean = false,
        val backendUrl: String = DEFAULT_BACKEND_URL,
        val teamId: String = DEFAULT_TEAM_ID,
        val memberId: String = DEFAULT_MEMBER_ID,
        val totalNotificationsPosted: Int = 0,
        val isSmsEnabled: Boolean = DEFAULT_SMS_ENABLED,
        val emergencyContact: String = DEFAULT_EMERGENCY_CONTACT,
        val smsStatus: String = "DISABLED",
        val lastSmsTimestamp: Long = 0,
        val totalSmsSent: Int = 0,
        val lastError: String? = null,

        // Stage 3 Real GPS monitoring fields
        val gpsStatus: String = "STANDBY",
        val latitude: Double? = null,
        val longitude: Double? = null,
        val altitudeM: Double? = null,
        val accuracyM: Float? = null,
        val speedMps: Float? = null,
        val headingDeg: Float? = null,
        val gpsTimestamp: String? = null,
        val gpsUpdateCount: Int = 0,

        // Stage 4 Live Guidance & Arrival fields
        val navigationStatus: String = "STANDBY",
        val targetBearingDeg: Double? = null,
        val directionDeltaDeg: Double? = null,
        val distanceToTargetM: Double? = null,
        val directionGuidance: String? = null,
        val isArrived: Boolean = false,
        val missionStatus: String? = null
    )

    inner class LocalBinder : Binder() {
        fun getService(): RescuerPollingService = this@RescuerPollingService
    }

    private val binder = LocalBinder()
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var pollJob: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private lateinit var notificationManager: EmergencyNotificationManager
    private lateinit var smsManager: EmergencySmsManager
    private lateinit var apiClient: RidgeWatchApiClient
    private lateinit var prefs: SharedPreferences
    private lateinit var sessionId: String
    private lateinit var locationTracker: RescuerLocationTracker

    override fun onCreate() {
        super.onCreate()
        instance = this
        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        sessionId = "BRG-AND-" + UUID.randomUUID().toString().substring(0, 6).uppercase()

        val savedUrl = prefs.getString(KEY_BACKEND_URL, DEFAULT_BACKEND_URL) ?: DEFAULT_BACKEND_URL
        val smsEnabled = prefs.getBoolean(KEY_SMS_ENABLED, DEFAULT_SMS_ENABLED)
        val emergencyContact = prefs.getString(KEY_EMERGENCY_CONTACT, DEFAULT_EMERGENCY_CONTACT) ?: DEFAULT_EMERGENCY_CONTACT
        val teamId = prefs.getString(KEY_TEAM_ID, DEFAULT_TEAM_ID) ?: DEFAULT_TEAM_ID
        val memberId = prefs.getString(KEY_MEMBER_ID, DEFAULT_MEMBER_ID) ?: DEFAULT_MEMBER_ID

        apiClient = RidgeWatchApiClient(savedUrl)
        notificationManager = EmergencyNotificationManager(this)
        smsManager = EmergencySmsManager(this)

        locationTracker = RescuerLocationTracker(this) { gpsData ->
            _serviceState.value = _serviceState.value.copy(
                gpsStatus = gpsData.status.name,
                latitude = gpsData.latitude,
                longitude = gpsData.longitude,
                altitudeM = gpsData.altitudeM,
                accuracyM = gpsData.accuracyM,
                speedMps = gpsData.speedMps,
                headingDeg = gpsData.headingDeg,
                gpsTimestamp = gpsData.timestampIso,
                gpsUpdateCount = gpsData.updateCount
            )
        }

        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "RidgeWatch::RescuerPollingLock")

        // Start Foreground Service safely with dataSync initial type
        val notif = notificationManager.buildServiceNotification("Connecting to $savedUrl...")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(
                this,
                EmergencyNotificationManager.SERVICE_NOTIFICATION_ID,
                notif,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            startForeground(EmergencyNotificationManager.SERVICE_NOTIFICATION_ID, notif)
        }

        val initialSmsStatus = calculateSmsStatus(smsEnabled, emergencyContact)

        _serviceState.value = _serviceState.value.copy(
            isRunning = true,
            backendUrl = savedUrl,
            teamId = teamId,
            memberId = memberId,
            isSmsEnabled = smsEnabled,
            emergencyContact = emergencyContact,
            smsStatus = initialSmsStatus,
            gpsStatus = "STANDBY"
        )

        startPollingLoop()
        Log.i(
            TAG,
            "[ANDROID_COMPANION] Service started. Session: $sessionId | Backend: $savedUrl | Member: $memberId"
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        refreshSmsState()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onDestroy() {
        locationTracker.stopTracking()
        pollJob?.cancel()
        serviceScope.cancel()
        wakeLock?.let { if (it.isHeld) it.release() }
        if (instance == this) instance = null
        _serviceState.value = _serviceState.value.copy(isRunning = false, isBackendConnected = false)
        Log.i(TAG, "[ANDROID_COMPANION] Service stopped.")
        super.onDestroy()
    }

    fun getLocationTracker(): RescuerLocationTracker = locationTracker

    /**
     * Rescuer accepts the mission on the phone.
     * Triggers the Stage 3 transition: ASSIGNED -> ACCEPTED -> GPS Tracking.
     */
    fun acceptMission(commandId: String) {
        serviceScope.launch {
            Log.i(TAG, "[MISSION_ACCEPTANCE] Accepting mission command_id=$commandId")
            try {
                apiClient.reportCommandStatus(commandId, "USER_ACCEPTED")
            } catch (e: Exception) {
                Log.w(TAG, "Failed to report USER_ACCEPTED to backend: ${e.message}")
            }

            _serviceState.value = _serviceState.value.copy(
                isMissionAccepted = true,
                lastCommand = _serviceState.value.lastCommand?.copy(status = "ACCEPTED")
            )

            val currentMember = prefs.getString(KEY_MEMBER_ID, DEFAULT_MEMBER_ID) ?: DEFAULT_MEMBER_ID
            if (currentMember == "ALPHA-M001") {
                if (locationTracker.hasLocationPermission()) {
                    promoteForegroundServiceToLocation()
                    locationTracker.startTracking()
                } else {
                    _serviceState.value = _serviceState.value.copy(gpsStatus = "WAITING_FOR_PERMISSION")
                }
            } else {
                Log.i(TAG, "[REAL_GPS] Member $currentMember remains simulation-only.")
            }
        }
    }

    /**
     * Rescuer accepts the work assignment on the phone.
     * Transitions status to ACCEPTED and activates Real GPS for Alpha Member 1.
     */
    fun acceptWorkAssignment(assignmentId: String) {
        serviceScope.launch {
            Log.i(TAG, "[WORK_ACCEPTANCE] Accepting job assignment_id=$assignmentId")
            try {
                apiClient.reportJobStatus(assignmentId, "ACCEPTED", progressPct = 0, notes = "Accepted by field rescuer")
            } catch (e: Exception) {
                Log.w(TAG, "Failed to report ACCEPTED job status: ${e.message}")
            }

            _serviceState.value = _serviceState.value.copy(
                isJobAccepted = true,
                lastJobAssignment = _serviceState.value.lastJobAssignment?.copy(status = "ACCEPTED")
            )

            val currentMember = prefs.getString(KEY_MEMBER_ID, DEFAULT_MEMBER_ID) ?: DEFAULT_MEMBER_ID
            if (currentMember == "ALPHA-M001") {
                if (locationTracker.hasLocationPermission()) {
                    promoteForegroundServiceToLocation()
                    locationTracker.startTracking()
                } else {
                    _serviceState.value = _serviceState.value.copy(gpsStatus = "WAITING_FOR_PERMISSION")
                }
            } else {
                Log.i(TAG, "[REAL_GPS] Member $currentMember remains simulation-only for job.")
            }
        }
    }

    /**
     * Handles runtime location permission result callback.
     */
    fun onLocationPermissionResult(granted: Boolean) {
        val currentMember = prefs.getString(KEY_MEMBER_ID, DEFAULT_MEMBER_ID) ?: DEFAULT_MEMBER_ID
        if (granted) {
            Log.i(TAG, "[REAL_GPS] Location permission granted")
            if (currentMember == "ALPHA-M001" && (_serviceState.value.isMissionAccepted || _serviceState.value.isJobAccepted)) {
                promoteForegroundServiceToLocation()
                locationTracker.startTracking()
            }
        } else {
            Log.w(TAG, "[REAL_GPS] Location permission denied")
            locationTracker.onPermissionDenied()
        }
    }

    private fun promoteForegroundServiceToLocation() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && locationTracker.hasLocationPermission()) {
            try {
                val notif = notificationManager.buildServiceNotification("RidgeWatch Real GPS Tracking Active")
                ServiceCompat.startForeground(
                    this,
                    EmergencyNotificationManager.SERVICE_NOTIFICATION_ID,
                    notif,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC or ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
                )
            } catch (e: Exception) {
                Log.w(TAG, "Could not promote foreground service to location: ${e.message}")
            }
        }
    }

    fun getSmsManager(): EmergencySmsManager = smsManager

    fun refreshSmsState() {
        val smsEnabled = prefs.getBoolean(KEY_SMS_ENABLED, DEFAULT_SMS_ENABLED)
        val emergencyContact = prefs.getString(KEY_EMERGENCY_CONTACT, DEFAULT_EMERGENCY_CONTACT) ?: DEFAULT_EMERGENCY_CONTACT
        val calculatedStatus = calculateSmsStatus(smsEnabled, emergencyContact)
        _serviceState.value = _serviceState.value.copy(
            isSmsEnabled = smsEnabled,
            emergencyContact = emergencyContact,
            smsStatus = calculatedStatus
        )
    }

    private fun calculateSmsStatus(enabled: Boolean, contact: String): String {
        return when {
            !enabled -> "DISABLED"
            !smsManager.hasSmsPermission() -> "PERMISSION_REQUIRED"
            contact.isBlank() -> "CONTACT_REQUIRED"
            !EmergencySmsManager.validateRecipient(contact) -> "INVALID_CONTACT"
            else -> "READY"
        }
    }

    /**
     * Executes manual test SMS dispatch.
     */
    fun sendManualTestSms(recipient: String? = null): SmsResult {
        val targetContact = if (!recipient.isNullOrBlank()) {
            recipient
        } else {
            prefs.getString(KEY_EMERGENCY_CONTACT, DEFAULT_EMERGENCY_CONTACT) ?: DEFAULT_EMERGENCY_CONTACT
        }

        val result = smsManager.sendTestSms(targetContact)
        when (result) {
            is SmsResult.Success -> {
                _serviceState.value = _serviceState.value.copy(
                    smsStatus = "SENT (TEST)",
                    lastSmsTimestamp = result.timestamp,
                    totalSmsSent = _serviceState.value.totalSmsSent + 1
                )
            }
            is SmsResult.PermissionDenied -> {
                _serviceState.value = _serviceState.value.copy(smsStatus = "PERMISSION_REQUIRED")
            }
            is SmsResult.InvalidRecipient -> {
                _serviceState.value = _serviceState.value.copy(smsStatus = "INVALID_CONTACT")
            }
            is SmsResult.Failed -> {
                _serviceState.value = _serviceState.value.copy(smsStatus = "FAILED")
            }
            is SmsResult.Disabled -> {
                _serviceState.value = _serviceState.value.copy(smsStatus = "DISABLED")
            }
        }
        return result
    }

    /**
     * Continuous polling loop executing periodic heartbeats against RIDGEWATCH backend.
     */
    private fun startPollingLoop() {
        pollJob?.cancel()
        pollJob = serviceScope.launch {
            while (isActive) {
                val currentUrl = prefs.getString(KEY_BACKEND_URL, DEFAULT_BACKEND_URL) ?: DEFAULT_BACKEND_URL
                val currentTeam = prefs.getString(KEY_TEAM_ID, DEFAULT_TEAM_ID) ?: DEFAULT_TEAM_ID
                val currentMember = prefs.getString(KEY_MEMBER_ID, DEFAULT_MEMBER_ID) ?: DEFAULT_MEMBER_ID

                if (apiClient.getBaseUrl() != currentUrl) {
                    apiClient = RidgeWatchApiClient(currentUrl)
                }

                val isAlpha1 = currentMember == "ALPHA-M001"
                val isAccepted = _serviceState.value.isMissionAccepted
                val gps = locationTracker.locationState.value

                // Activate real GPS if Alpha Member 1 mission has been accepted and tracker is in STANDBY or recovering from GPS_UNAVAILABLE
                val shouldStartTracking = isAlpha1 && isAccepted &&
                        (gps.status == RescuerLocationTracker.GpsStatus.STANDBY ||
                         (gps.status == RescuerLocationTracker.GpsStatus.GPS_UNAVAILABLE && locationTracker.hasAnyLocationProviderEnabled())) &&
                        locationTracker.hasLocationPermission() &&
                        locationTracker.hasAnyLocationProviderEnabled()

                if (shouldStartTracking) {
                    promoteForegroundServiceToLocation()
                    locationTracker.startTracking()
                }

                val hasValidFix = isAlpha1 && isAccepted &&
                        (gps.status == RescuerLocationTracker.GpsStatus.TRACKING || gps.status == RescuerLocationTracker.GpsStatus.STALE) &&
                        gps.latitude != null && gps.longitude != null

                val request = BridgeSyncRequest(
                    sessionId = sessionId,
                    teamId = currentTeam,
                    memberId = currentMember,
                    deviceName = "RidgeWatch Native Android Companion",
                    watchDeviceId = "DEV-WEARABLE-CALLPLUS",
                    watchMac = "CB:4E:FD:EE:7F:1B",
                    watchModel = "Wave Call Plus",
                    bluetoothState = "ENABLED",
                    gpsAvailable = hasValidFix,
                    latitude = if (hasValidFix) gps.latitude else null,
                    longitude = if (hasValidFix) gps.longitude else null,
                    altitudeM = if (hasValidFix) gps.altitudeM else null,
                    accuracyM = if (hasValidFix) gps.accuracyM else null,
                    speedMps = if (hasValidFix) gps.speedMps else null,
                    headingDeg = if (hasValidFix) gps.headingDeg else null,
                    timestamp = if (hasValidFix) gps.timestampIso else null,
                    locationSource = if (isAlpha1) "PHONE_GPS" else "SIMULATED",
                    status = "ONLINE",
                    notes = "Native Android Companion (Polling: $currentMember | GPS: ${gps.status})",
                    gpsStatus = gps.status.name
                )

                val result = apiClient.sendHeartbeat(request)

                if (result.isSuccess) {
                    val resp = result.getOrNull()
                    Log.i(TAG, "[ANDROID_COMPANION] BACKEND_CONNECTED ($currentUrl)")

                    val nav = resp?.navigation
                    val isMissionArrived = nav?.isArrived == true || resp?.missionStatus?.uppercase() == "ARRIVED"

                    _serviceState.value = _serviceState.value.copy(
                        isBackendConnected = true,
                        lastSyncTimestamp = System.currentTimeMillis(),
                        backendUrl = currentUrl,
                        teamId = currentTeam,
                        memberId = currentMember,
                        lastError = null,
                        navigationStatus = nav?.navigationStatus ?: _serviceState.value.navigationStatus,
                        targetBearingDeg = nav?.targetBearingDeg ?: _serviceState.value.targetBearingDeg,
                        directionDeltaDeg = nav?.directionDeltaDeg ?: _serviceState.value.directionDeltaDeg,
                        distanceToTargetM = nav?.distanceToTargetM ?: _serviceState.value.distanceToTargetM,
                        directionGuidance = nav?.directionGuidance ?: _serviceState.value.directionGuidance,
                        isArrived = isMissionArrived,
                        missionStatus = resp?.missionStatus ?: _serviceState.value.missionStatus
                    )

                    // If mission has ARRIVED, stop active GPS tracking per Requirement K
                    if (isMissionArrived && _serviceState.value.isMissionAccepted) {
                        Log.i(TAG, "[ANDROID_COMPANION] Mission ARRIVED — stopping active GPS tracking")
                        _serviceState.value = _serviceState.value.copy(isMissionAccepted = false)
                        locationTracker.stopTracking()
                    }

                    // Handle incoming command
                    resp?.activeCommand?.let { cmd ->
                        handleIncomingCommand(cmd)
                    }

                    // Handle incoming work assignment
                    resp?.activeJobAssignment?.let { job ->
                        handleIncomingJobAssignment(job)
                    }
                } else {
                    val err = result.exceptionOrNull()?.message ?: "Connection error"
                    Log.w(TAG, "[ANDROID_COMPANION] Backend disconnected: $err")
                    _serviceState.value = _serviceState.value.copy(
                        isBackendConnected = false,
                        lastError = err
                    )
                }

                delay(POLL_INTERVAL_MS)
            }
        }
    }

    /**
     * Processes incoming rescue command.
     */
    private suspend fun handleIncomingCommand(command: RescueCommand) {
        val postedSet = getPostedCommandIds()
        val currentMember = prefs.getString(KEY_MEMBER_ID, DEFAULT_MEMBER_ID) ?: DEFAULT_MEMBER_ID

        // Check if command is accepted remotely or locally
        val cmdStatusUpper = command.status.uppercase()
        if (cmdStatusUpper in listOf("ACCEPTED", "USER_ACCEPTED") && !_serviceState.value.isMissionAccepted) {
            _serviceState.value = _serviceState.value.copy(
                isMissionAccepted = true,
                lastCommand = command
            )
            if (currentMember == "ALPHA-M001" && locationTracker.hasLocationPermission()) {
                promoteForegroundServiceToLocation()
                locationTracker.startTracking()
            }
        } else if (cmdStatusUpper in listOf("COMPLETED", "RESCUED", "CANCELLED", "HOLD", "ARRIVED") && _serviceState.value.isMissionAccepted) {
            _serviceState.value = _serviceState.value.copy(
                isMissionAccepted = false,
                lastCommand = command
            )
            locationTracker.stopTracking()
        }

        // 1. Android Notification Flow (with Idempotency)
        if (!postedSet.contains(command.commandId)) {
            Log.i(TAG, "[ANDROID_COMPANION] COMMAND_RECEIVED command_id=${command.commandId}")

            val notifResult = notificationManager.postEmergencyNotification(command)
            if (notifResult is EmergencyNotificationManager.NotificationResult.Success) {
                markCommandPosted(command.commandId)
                apiClient.reportCommandStatus(command.commandId, "PHONE_NOTIFICATION_POSTED")

                _serviceState.value = _serviceState.value.copy(
                    lastCommand = command,
                    totalNotificationsPosted = _serviceState.value.totalNotificationsPosted + 1
                )
            }
        }

        // 2. Cellular SMS Emergency Alert Flow
        val smsPostedSet = getSmsPostedCommandIds()
        val smsEnabled = prefs.getBoolean(KEY_SMS_ENABLED, DEFAULT_SMS_ENABLED)
        val emergencyContact = prefs.getString(KEY_EMERGENCY_CONTACT, DEFAULT_EMERGENCY_CONTACT) ?: DEFAULT_EMERGENCY_CONTACT

        if (smsEnabled && emergencyContact.isNotBlank() && !smsPostedSet.contains(command.commandId)) {
            try {
                Log.i(TAG, "[ANDROID_COMPANION] Triggering Emergency SMS for command=${command.commandId} to=$emergencyContact")
                val smsResult = smsManager.sendEmergencySms(command, emergencyContact)

                when (smsResult) {
                    is SmsResult.Success -> {
                        markSmsCommandPosted(command.commandId)
                        _serviceState.value = _serviceState.value.copy(
                            smsStatus = "SENT",
                            lastSmsTimestamp = smsResult.timestamp,
                            totalSmsSent = _serviceState.value.totalSmsSent + 1
                        )
                        Log.i(TAG, "[ANDROID_COMPANION] SMS_SENT command_id=${command.commandId} recipient=$emergencyContact")
                    }
                    is SmsResult.PermissionDenied -> {
                        _serviceState.value = _serviceState.value.copy(smsStatus = "PERMISSION_REQUIRED")
                        Log.w(TAG, "[ANDROID_COMPANION] SMS_FAILED: Permission Denied")
                    }
                    is SmsResult.InvalidRecipient -> {
                        _serviceState.value = _serviceState.value.copy(smsStatus = "INVALID_CONTACT")
                        Log.w(TAG, "[ANDROID_COMPANION] SMS_FAILED: Invalid contact (${smsResult.reason})")
                    }
                    is SmsResult.Disabled -> {
                        _serviceState.value = _serviceState.value.copy(smsStatus = "DISABLED")
                    }
                    is SmsResult.Failed -> {
                        _serviceState.value = _serviceState.value.copy(smsStatus = "FAILED")
                        Log.e(TAG, "[ANDROID_COMPANION] SMS_FAILED: ${smsResult.error}")
                    }
                }
            } catch (smsEx: Exception) {
                Log.e(TAG, "[ANDROID_COMPANION] Isolated exception in SMS dispatch: ${smsEx.message}", smsEx)
                _serviceState.value = _serviceState.value.copy(smsStatus = "FAILED")
            }
        }
    }

    private fun getPostedCommandIds(): Set<String> {
        val raw = prefs.getStringSet(KEY_POSTED_COMMANDS, emptySet()) ?: emptySet()
        return raw.toSet()
    }

    private fun markCommandPosted(commandId: String) {
        val current = getPostedCommandIds().toMutableSet()
        current.add(commandId)
        prefs.edit().putStringSet(KEY_POSTED_COMMANDS, current).apply()
    }

    private fun getSmsPostedCommandIds(): Set<String> {
        val raw = prefs.getStringSet(KEY_SMS_POSTED_COMMANDS, emptySet()) ?: emptySet()
        return raw.toSet()
    }

    private fun markSmsCommandPosted(commandId: String) {
        val current = getSmsPostedCommandIds().toMutableSet()
        current.add(commandId)
        prefs.edit().putStringSet(KEY_SMS_POSTED_COMMANDS, current).apply()
    }

    /**
     * Processes incoming work/job assignment.
     */
    private suspend fun handleIncomingJobAssignment(job: org.ridgewatch.rescuer.model.JobAssignment) {
        val postedSet = getPostedJobIds()
        val currentMember = prefs.getString(KEY_MEMBER_ID, DEFAULT_MEMBER_ID) ?: DEFAULT_MEMBER_ID

        val jobStatusUpper = job.status.uppercase()
        if (jobStatusUpper in listOf("ACCEPTED", "IN_PROGRESS") && !_serviceState.value.isJobAccepted) {
            _serviceState.value = _serviceState.value.copy(
                isJobAccepted = true,
                lastJobAssignment = job
            )
            if (currentMember == "ALPHA-M001" && locationTracker.hasLocationPermission()) {
                promoteForegroundServiceToLocation()
                locationTracker.startTracking()
            }
        } else if (jobStatusUpper in listOf("COMPLETED", "FAILED", "CANCELLED") && _serviceState.value.isJobAccepted) {
            _serviceState.value = _serviceState.value.copy(
                isJobAccepted = false,
                lastJobAssignment = job
            )
            if (!_serviceState.value.isMissionAccepted) {
                locationTracker.stopTracking()
            }
        } else {
            _serviceState.value = _serviceState.value.copy(
                lastJobAssignment = job
            )
        }

        // Deduplicated Notification Flow
        if (!postedSet.contains(job.assignmentId)) {
            Log.i(TAG, "[ANDROID_COMPANION] JOB_ASSIGNMENT_RECEIVED assignment_id=${job.assignmentId}")
            val notifResult = notificationManager.postJobNotification(job)
            if (notifResult is EmergencyNotificationManager.NotificationResult.Success) {
                markJobPosted(job.assignmentId)
            }
        }
    }

    private fun getPostedJobIds(): Set<String> {
        val raw = prefs.getStringSet(KEY_POSTED_JOBS, emptySet()) ?: emptySet()
        return raw.toSet()
    }

    private fun markJobPosted(assignmentId: String) {
        val current = getPostedJobIds().toMutableSet()
        current.add(assignmentId)
        prefs.edit().putStringSet(KEY_POSTED_JOBS, current).apply()
    }
}
