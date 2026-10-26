package org.ridgewatch.rescuer.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import org.ridgewatch.rescuer.model.RescueCommand
import org.ridgewatch.rescuer.notification.EmergencyNotificationManager
import org.ridgewatch.rescuer.service.RescuerPollingService
import org.ridgewatch.rescuer.sms.EmergencySmsManager
import org.ridgewatch.rescuer.sms.SmsResult
import org.ridgewatch.rescuer.ui.theme.*
import java.util.UUID

class MainActivity : ComponentActivity() {

    companion object {
        private const val DIAGNOSTIC_TAG = "RIDGEWATCH_COMPANION"
    }

    private var hasNotificationPermissionState = mutableStateOf(false)
    private var hasSmsPermissionState = mutableStateOf(false)
    private var hasLocationPermissionState = mutableStateOf(false)
    private var showLocationRationaleState = mutableStateOf(false)
    private var pendingAcceptedCommandIdState = mutableStateOf<String?>(null)
    private var testNotificationStatusState = mutableStateOf<String?>(null)
    private var testSmsStatusState = mutableStateOf<String?>(null)

    private val requestNotificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        hasNotificationPermissionState.value = isGranted
        Log.d(DIAGNOSTIC_TAG, "POST_NOTIFICATIONS permission result: isGranted=$isGranted")
        if (isGranted) {
            testNotificationStatusState.value = "NOTIFICATION_PERMISSION_GRANTED"
            Toast.makeText(this, "✅ Notification permission granted!", Toast.LENGTH_SHORT).show()
            RescuerPollingService.startService(this)
        } else {
            testNotificationStatusState.value = "NOTIFICATION_PERMISSION_DENIED"
            Toast.makeText(this, "⚠️ Notification permission denied. Emergency alerts cannot be displayed.", Toast.LENGTH_LONG).show()
        }
    }

    private val requestSmsPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        hasSmsPermissionState.value = isGranted
        Log.d(DIAGNOSTIC_TAG, "SEND_SMS permission result: isGranted=$isGranted")
        if (isGranted) {
            testSmsStatusState.value = "SMS_PERMISSION_GRANTED"
            Toast.makeText(this, "✅ SMS permission granted!", Toast.LENGTH_SHORT).show()
            updateSmsStateInService()
        } else {
            testSmsStatusState.value = "SMS_PERMISSION_DENIED"
            Toast.makeText(this, "⚠️ SMS permission denied. Emergency SMS alerts cannot be sent.", Toast.LENGTH_LONG).show()
            updateSmsStateInService()
        }
    }

    private val requestLocationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions: Map<String, Boolean> ->
        val fineGranted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] ?: false
        val coarseGranted = permissions[Manifest.permission.ACCESS_COARSE_LOCATION] ?: false
        val isGranted = fineGranted || coarseGranted
        hasLocationPermissionState.value = isGranted
        Log.d(DIAGNOSTIC_TAG, "Location permissions result: fine=$fineGranted coarse=$coarseGranted granted=$isGranted")
        RescuerPollingService.notifyLocationPermissionResult(isGranted)
        if (isGranted) {
            Toast.makeText(this, "🛰️ GPS permission granted! Real GPS active for Alpha Member 1.", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "⚠️ Location permission denied. Real GPS tracking cannot start.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        checkNotificationPermission()
        checkSmsPermission()
        checkLocationPermission()

        // Automatically start polling service if notification permission granted
        if (hasNotificationPermissionState.value) {
            RescuerPollingService.startService(this)
        }

        setContent {
            val status by RescuerPollingService.serviceState.collectAsState()
            val hasNotifPerm by hasNotificationPermissionState
            val hasSmsPerm by hasSmsPermissionState
            val hasLocPerm by hasLocationPermissionState
            val showRationale by showLocationRationaleState
            val testNotifStatus by testNotificationStatusState
            val testSmsStatus by testSmsStatusState

            RidgeWatchCompanionTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    RidgeWatchDashboard(
                        status = status,
                        hasNotificationPermission = hasNotifPerm,
                        hasSmsPermission = hasSmsPerm,
                        hasLocationPermission = hasLocPerm,
                        testStatus = testNotifStatus,
                        testSmsStatus = testSmsStatus,
                        onRequestNotificationPermission = { requestNotificationPermission() },
                        onRequestSmsPermission = { requestSmsPermission() },
                        onRequestLocationPermission = { requestLocationPermission() },
                        onAcceptMission = { cmdId -> handleAcceptMission(cmdId) },
                        onAcceptWork = { assignmentId -> handleAcceptWork(assignmentId) },
                        onStartService = { RescuerPollingService.startService(this) },
                        onStopService = { RescuerPollingService.stopService(this) },
                        onTestNotification = { triggerTestNotification() },
                        onTestSms = { recipient -> triggerTestSms(recipient) },
                        onSaveSettings = { url, team, member, smsEnabled, emergencyContact ->
                            saveSettings(url, team, member, smsEnabled, emergencyContact)
                        }
                    )

                    // Clear explanation rationale dialog for location permission
                    if (showRationale) {
                        AlertDialog(
                            onDismissRequest = { showLocationRationaleState.value = false },
                            title = { Text("🛰️ Location Permission Required", fontWeight = FontWeight.Bold, color = RescueText) },
                            text = {
                                Text(
                                    "RidgeWatch needs your phone location to track the rescuer during an active rescue mission.",
                                    color = RescueText,
                                    fontSize = 14.sp
                                )
                            },
                            confirmButton = {
                                Button(
                                    onClick = {
                                        showLocationRationaleState.value = false
                                        requestLocationPermission()
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = RescueRed)
                                ) {
                                    Text("Grant Permission", color = Color.White, fontWeight = FontWeight.Bold)
                                }
                            },
                            dismissButton = {
                                TextButton(onClick = {
                                    showLocationRationaleState.value = false
                                    RescuerPollingService.notifyLocationPermissionResult(false)
                                }) {
                                    Text("Deny", color = RescueSubText)
                                }
                            },
                            containerColor = RescueSurface
                        )
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        checkNotificationPermission()
        checkSmsPermission()
        checkLocationPermission()
    }

    private fun checkNotificationPermission() {
        val granted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED && NotificationManagerCompat.from(this).areNotificationsEnabled()
        } else {
            NotificationManagerCompat.from(this).areNotificationsEnabled()
        }
        hasNotificationPermissionState.value = granted
    }

    private fun checkSmsPermission() {
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.SEND_SMS
        ) == PackageManager.PERMISSION_GRANTED
        hasSmsPermissionState.value = granted
    }

    private fun checkLocationPermission() {
        val fine = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        hasLocationPermissionState.value = fine || coarse
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            Log.d(DIAGNOSTIC_TAG, "Requesting POST_NOTIFICATIONS runtime permission...")
            requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            Toast.makeText(this, "Notification permission is managed in system settings", Toast.LENGTH_SHORT).show()
        }
    }

    private fun requestSmsPermission() {
        Log.d(DIAGNOSTIC_TAG, "Requesting SEND_SMS runtime permission...")
        requestSmsPermissionLauncher.launch(Manifest.permission.SEND_SMS)
    }

    private fun requestLocationPermission() {
        Log.d(DIAGNOSTIC_TAG, "Requesting location runtime permissions...")
        requestLocationPermissionLauncher.launch(
            arrayOf(
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION
            )
        )
    }

    private fun handleAcceptMission(commandId: String) {
        Log.i(DIAGNOSTIC_TAG, "Accept mission requested: $commandId")
        RescuerPollingService.acceptMission(commandId)

        val prefs = getSharedPreferences(RescuerPollingService.PREFS_NAME, Context.MODE_PRIVATE)
        val memberId = prefs.getString(RescuerPollingService.KEY_MEMBER_ID, RescuerPollingService.DEFAULT_MEMBER_ID) ?: RescuerPollingService.DEFAULT_MEMBER_ID

        if (memberId == "ALPHA-M001") {
            checkLocationPermission()
            if (!hasLocationPermissionState.value) {
                // Show clear rationale dialog explaining why phone location is required
                pendingAcceptedCommandIdState.value = commandId
                showLocationRationaleState.value = true
            } else {
                RescuerPollingService.notifyLocationPermissionResult(true)
                Toast.makeText(this, "🚨 Mission Accepted! Real GPS tracking activated for Alpha Member 1.", Toast.LENGTH_SHORT).show()
            }
        } else {
            Toast.makeText(this, "🚨 Mission Accepted! (Simulation tracking for $memberId)", Toast.LENGTH_SHORT).show()
        }
    }

    private fun handleAcceptWork(assignmentId: String) {
        Log.i(DIAGNOSTIC_TAG, "Accept work assignment requested: $assignmentId")
        RescuerPollingService.acceptWorkAssignment(assignmentId)

        val prefs = getSharedPreferences(RescuerPollingService.PREFS_NAME, Context.MODE_PRIVATE)
        val memberId = prefs.getString(RescuerPollingService.KEY_MEMBER_ID, RescuerPollingService.DEFAULT_MEMBER_ID) ?: RescuerPollingService.DEFAULT_MEMBER_ID

        if (memberId == "ALPHA-M001") {
            checkLocationPermission()
            if (!hasLocationPermissionState.value) {
                pendingAcceptedCommandIdState.value = assignmentId
                showLocationRationaleState.value = true
            } else {
                RescuerPollingService.notifyLocationPermissionResult(true)
                Toast.makeText(this, "📋 Work Assignment Accepted! Real GPS tracking activated for Alpha Member 1.", Toast.LENGTH_SHORT).show()
            }
        } else {
            Toast.makeText(this, "📋 Work Assignment Accepted! (Simulation tracking for $memberId)", Toast.LENGTH_SHORT).show()
        }
    }

    private fun updateSmsStateInService() {
        val prefs = getSharedPreferences(RescuerPollingService.PREFS_NAME, Context.MODE_PRIVATE)
        val enabled = prefs.getBoolean(RescuerPollingService.KEY_SMS_ENABLED, RescuerPollingService.DEFAULT_SMS_ENABLED)
        val contact = prefs.getString(RescuerPollingService.KEY_EMERGENCY_CONTACT, RescuerPollingService.DEFAULT_EMERGENCY_CONTACT) ?: ""
        RescuerPollingService.updateServiceStateSms(enabled, contact)
    }

    private fun triggerTestNotification() {
        Log.d(DIAGNOSTIC_TAG, "TEST NOTIFICATION BUTTON CLICKED")
        testNotificationStatusState.value = "TEST_NOTIFICATION_REQUESTED"

        checkNotificationPermission()
        if (!hasNotificationPermissionState.value) {
            Log.w(DIAGNOSTIC_TAG, "POST_ABORTED: Notification permission not granted")
            testNotificationStatusState.value = "NOTIFICATION_PERMISSION_DENIED"
            Toast.makeText(
                this,
                "⚠️ Notification permission required!\nRequesting permission now...",
                Toast.LENGTH_LONG
            ).show()
            requestNotificationPermission()
            return
        }

        val prefs = getSharedPreferences(RescuerPollingService.PREFS_NAME, Context.MODE_PRIVATE)
        val notifManager = EmergencyNotificationManager(this)
        val testCmdId = "TEST-ALERT-" + UUID.randomUUID().toString().substring(0, 6).uppercase()

        val testCmd = RescueCommand(
            commandId = testCmdId,
            teamId = prefs.getString(RescuerPollingService.KEY_TEAM_ID, RescuerPollingService.DEFAULT_TEAM_ID) ?: RescuerPollingService.DEFAULT_TEAM_ID,
            memberId = prefs.getString(RescuerPollingService.KEY_MEMBER_ID, RescuerPollingService.DEFAULT_MEMBER_ID) ?: RescuerPollingService.DEFAULT_MEMBER_ID,
            commandType = "TEST",
            targetId = "Survivor (Simulation)",
            locationLabel = "Test Sector Alpha",
            distanceM = 45.0,
            title = "🚨 RIDGEWATCH — TEST ALERT",
            body = "Survivor detected [Test Alert]\nSector: Test Sector Alpha\nTesting boAt Wave Call Plus Mirroring"
        )

        val result = notifManager.postEmergencyNotification(testCmd)

        when (result) {
            is EmergencyNotificationManager.NotificationResult.Success -> {
                Log.d(DIAGNOSTIC_TAG, "POST_SUCCESS: commandId=${result.commandId} notificationId=${result.notificationId}")
                testNotificationStatusState.value = "TEST_NOTIFICATION_POSTED (ID: ${result.commandId})"
                Toast.makeText(
                    this,
                    "🚨 Test Emergency Alert Posted!\nCheck Notification Shade & boAt Watch",
                    Toast.LENGTH_SHORT
                ).show()
            }
            is EmergencyNotificationManager.NotificationResult.PermissionDenied -> {
                Log.w(DIAGNOSTIC_TAG, "POST_FAILED PermissionDenied: ${result.reason}")
                testNotificationStatusState.value = "NOTIFICATION_PERMISSION_DENIED"
                hasNotificationPermissionState.value = false
                Toast.makeText(
                    this,
                    "⚠️ Permission Denied: ${result.reason}",
                    Toast.LENGTH_LONG
                ).show()
                requestNotificationPermission()
            }
            is EmergencyNotificationManager.NotificationResult.Failed -> {
                Log.e(DIAGNOSTIC_TAG, "POST_FAILED Error: ${result.error}")
                testNotificationStatusState.value = "NOTIFICATION_POST_FAILED: ${result.error}"
                Toast.makeText(
                    this,
                    "❌ Notification Post Failed: ${result.error}",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun triggerTestSms(recipientOverride: String? = null) {
        Log.d(DIAGNOSTIC_TAG, "TEST SMS BUTTON CLICKED")
        testSmsStatusState.value = "TEST_SMS_REQUESTED"

        checkSmsPermission()
        if (!hasSmsPermissionState.value) {
            Log.w(DIAGNOSTIC_TAG, "SMS_ABORTED: SEND_SMS permission not granted")
            testSmsStatusState.value = "SMS_PERMISSION_DENIED"
            Toast.makeText(
                this,
                "⚠️ SMS Permission required to send emergency SMS alerts.\nRequesting permission now...",
                Toast.LENGTH_LONG
            ).show()
            requestSmsPermission()
            return
        }

        val prefs = getSharedPreferences(RescuerPollingService.PREFS_NAME, Context.MODE_PRIVATE)
        val targetContact = if (!recipientOverride.isNullOrBlank()) {
            recipientOverride
        } else {
            prefs.getString(RescuerPollingService.KEY_EMERGENCY_CONTACT, "") ?: ""
        }

        if (targetContact.isBlank()) {
            testSmsStatusState.value = "SMS_FAILED (No contact configured)"
            Toast.makeText(
                this,
                "⚠️ Please set an Emergency Contact phone number in Settings (⚙️)",
                Toast.LENGTH_LONG
            ).show()
            return
        }

        val smsManager = EmergencySmsManager(this)
        val result = smsManager.sendTestSms(targetContact)

        when (result) {
            is SmsResult.Success -> {
                Log.d(DIAGNOSTIC_TAG, "SMS_SUCCESS to=${result.recipient}")
                testSmsStatusState.value = "SMS_SENT to ${result.recipient}"
                Toast.makeText(
                    this,
                    "📱 Test Emergency SMS sent to ${result.recipient}!",
                    Toast.LENGTH_SHORT
                ).show()
                updateSmsStateInService()
            }
            is SmsResult.PermissionDenied -> {
                Log.w(DIAGNOSTIC_TAG, "SMS_PERMISSION_DENIED: ${result.reason}")
                testSmsStatusState.value = "SMS_PERMISSION_DENIED"
                hasSmsPermissionState.value = false
                Toast.makeText(
                    this,
                    "⚠️ SMS Permission Denied: ${result.reason}",
                    Toast.LENGTH_LONG
                ).show()
                requestSmsPermission()
            }
            is SmsResult.InvalidRecipient -> {
                Log.w(DIAGNOSTIC_TAG, "SMS_INVALID_RECIPIENT: ${result.reason}")
                testSmsStatusState.value = "SMS_INVALID_RECIPIENT: ${result.reason}"
                Toast.makeText(
                    this,
                    "❌ Invalid phone number: ${result.reason}",
                    Toast.LENGTH_LONG
                ).show()
            }
            is SmsResult.Disabled -> {
                testSmsStatusState.value = "SMS_DISABLED: ${result.reason}"
                Toast.makeText(this, "ℹ️ ${result.reason}", Toast.LENGTH_SHORT).show()
            }
            is SmsResult.Failed -> {
                Log.e(DIAGNOSTIC_TAG, "SMS_FAILED: ${result.error}")
                testSmsStatusState.value = "SMS_FAILED: ${result.error}"
                Toast.makeText(
                    this,
                    "❌ SMS Dispatch Failed: ${result.error}",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun saveSettings(
        url: String,
        team: String,
        member: String,
        smsEnabled: Boolean,
        emergencyContact: String
    ) {
        val prefs = getSharedPreferences(RescuerPollingService.PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(RescuerPollingService.KEY_BACKEND_URL, url)
            .putString(RescuerPollingService.KEY_TEAM_ID, team)
            .putString(RescuerPollingService.KEY_MEMBER_ID, member)
            .putBoolean(RescuerPollingService.KEY_SMS_ENABLED, smsEnabled)
            .putString(RescuerPollingService.KEY_EMERGENCY_CONTACT, emergencyContact.trim())
            .apply()

        if (smsEnabled && !hasSmsPermissionState.value) {
            requestSmsPermission()
        }

        RescuerPollingService.stopService(this)
        RescuerPollingService.startService(this)
        Toast.makeText(this, "⚙️ Settings saved successfully!", Toast.LENGTH_SHORT).show()
    }
}
