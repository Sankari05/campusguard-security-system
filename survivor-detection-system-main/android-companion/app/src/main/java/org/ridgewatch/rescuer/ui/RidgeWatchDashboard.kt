package org.ridgewatch.rescuer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.ridgewatch.rescuer.service.RescuerPollingService
import org.ridgewatch.rescuer.ui.theme.*
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RidgeWatchDashboard(
    status: RescuerPollingService.ServiceStatus,
    hasNotificationPermission: Boolean,
    hasSmsPermission: Boolean,
    hasLocationPermission: Boolean,
    testStatus: String? = null,
    testSmsStatus: String? = null,
    onRequestNotificationPermission: () -> Unit,
    onRequestSmsPermission: () -> Unit,
    onRequestLocationPermission: () -> Unit,
    onAcceptMission: (commandId: String) -> Unit,
    onAcceptWork: (assignmentId: String) -> Unit = {},
    onStartService: () -> Unit,
    onStopService: () -> Unit,
    onTestNotification: () -> Unit,
    onTestSms: (recipient: String?) -> Unit,
    onSaveSettings: (url: String, team: String, member: String, smsEnabled: Boolean, emergencyContact: String) -> Unit
) {
    val scrollState = rememberScrollState()
    var showSettingsDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("🚨 RidgeWatch Rescuer", fontWeight = FontWeight.Bold, color = RescueText)
                        Spacer(modifier = Modifier.width(8.dp))
                        Badge(
                            containerColor = if (status.isBackendConnected) RescueGreen else RescueRed
                        ) {
                            Text(
                                if (status.isBackendConnected) "ONLINE" else "OFFLINE",
                                color = Color.White,
                                modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { showSettingsDialog = true }) {
                        Text("⚙️", fontSize = 20.sp)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = RescueSurface)
            )
        },
        containerColor = RescueDark
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(scrollState),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 1. Notification Permission Warning
            if (!hasNotificationPermission) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = RescueYellow.copy(alpha = 0.2f)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("⚠️ Notification Permission Required", fontWeight = FontWeight.Bold, color = RescueYellow)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "Android requires notification permission to trigger emergency alerts and mirror to boAt Wave Call Plus smartwatch.",
                            color = RescueText,
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(
                            onClick = onRequestNotificationPermission,
                            colors = ButtonDefaults.buttonColors(containerColor = RescueYellow)
                        ) {
                            Text("Grant Notification Permission", color = Color.Black, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // 2. SMS Permission Warning
            if (status.isSmsEnabled && !hasSmsPermission) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = RescueBlue.copy(alpha = 0.2f)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("📱 SMS Permission Required", fontWeight = FontWeight.Bold, color = RescueBlue)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "SMS Emergency Alerting is enabled. RidgeWatch requires SEND_SMS permission to dispatch emergency texts.",
                            color = RescueText,
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(
                            onClick = onRequestSmsPermission,
                            colors = ButtonDefaults.buttonColors(containerColor = RescueBlue)
                        ) {
                            Text("Grant SMS Permission", color = Color.White, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // 3. Backend & Gateway Status Card
            Card(
                colors = CardDefaults.cardColors(containerColor = RescueSurface),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("📡 Backend Connection", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 16.sp)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Backend URL:", color = RescueSubText, fontSize = 13.sp)
                        Text(status.backendUrl, color = RescueText, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Status:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            if (status.isBackendConnected) "● CONNECTED (200 OK)" else "○ DISCONNECTED",
                            color = if (status.isBackendConnected) RescueGreen else RescueRed,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Last Sync:", color = RescueSubText, fontSize = 13.sp)
                        val timeStr = if (status.lastSyncTimestamp > 0) {
                            SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date(status.lastSyncTimestamp))
                        } else "Never"
                        Text(timeStr, color = RescueText, fontSize = 13.sp)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Rescuer Target:", color = RescueSubText, fontSize = 13.sp)
                        Text("${status.teamId} / ${status.memberId}", color = RescueBlue, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }

            // 4. Active Emergency Mission Card (with Stage 2 Mission Acceptance)
            Card(
                colors = CardDefaults.cardColors(containerColor = if (status.lastCommand != null) RescueRed.copy(alpha = 0.2f) else RescueSurface),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("🚨 Active Rescue Command", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 16.sp)
                        if (status.isMissionAccepted || status.lastCommand?.status?.uppercase() in listOf("ACCEPTED", "USER_ACCEPTED")) {
                            Badge(containerColor = RescueGreen) {
                                Text("ACCEPTED", color = Color.White, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp), fontWeight = FontWeight.Bold)
                            }
                        } else if (status.lastCommand != null) {
                            Badge(containerColor = RescueYellow) {
                                Text("ASSIGNED", color = Color.Black, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp), fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))
                    if (status.lastCommand != null) {
                        val cmd = status.lastCommand
                        Text(cmd.title, fontWeight = FontWeight.Bold, color = RescueRed, fontSize = 18.sp)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text("Command ID: ${cmd.commandId}", color = RescueSubText, fontSize = 13.sp)
                        Text("Target: ${cmd.targetId}", color = RescueText, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text("Sector: ${cmd.locationLabel}", color = RescueText, fontSize = 14.sp)
                        cmd.distanceM?.let { dist ->
                            Text("Distance: ${Math.round(dist)} m", color = RescueYellow, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                        }

                        Spacer(modifier = Modifier.height(10.dp))

                        // Mission Acceptance Action
                        val isAlreadyAccepted = status.isMissionAccepted || cmd.status.uppercase() in listOf("ACCEPTED", "USER_ACCEPTED")
                        if (!isAlreadyAccepted) {
                            Button(
                                onClick = { onAcceptMission(cmd.commandId) },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.buttonColors(containerColor = RescueGreen),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("✅ ACCEPT RESCUE MISSION", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Badge(containerColor = RescueGreen) {
                                Text("NOTIFICATION_POSTED", color = Color.White, modifier = Modifier.padding(4.dp))
                            }
                            if (status.isSmsEnabled) {
                                Badge(containerColor = RescueBlue) {
                                    Text("SMS_${status.smsStatus}", color = Color.White, modifier = Modifier.padding(4.dp))
                                }
                            }
                        }
                    } else {
                        Text("No active rescue commands. Standing by...", color = RescueSubText, fontSize = 14.sp)
                    }
                }
            }

            // 4B. Active Work Assignment Card
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = if (status.lastJobAssignment != null) RescueBlue.copy(alpha = 0.15f) else RescueSurface
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("📋 Active Work Assignment", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 16.sp)
                        if (status.isJobAccepted || status.lastJobAssignment?.status?.uppercase() in listOf("ACCEPTED", "COMPLETED")) {
                            Badge(containerColor = RescueGreen) {
                                Text("ACCEPTED", color = Color.White, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp), fontWeight = FontWeight.Bold)
                            }
                        } else if (status.lastJobAssignment != null) {
                            Badge(containerColor = RescueYellow) {
                                Text("ASSIGNED", color = Color.Black, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp), fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))
                    if (status.lastJobAssignment != null) {
                        val job = status.lastJobAssignment
                        Text(job.title, fontWeight = FontWeight.Bold, color = RescueBlue, fontSize = 17.sp)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text("Assignment ID: ${job.assignmentId}", color = RescueSubText, fontSize = 13.sp)
                        Text("Priority: ${job.priority.uppercase()}", color = RescueText, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                        if (!job.location.isNullOrBlank()) {
                            Text("Location: ${job.location}", color = RescueText, fontSize = 13.sp)
                        }
                        if (!job.description.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(job.description, color = RescueSubText, fontSize = 13.sp)
                        }

                        Spacer(modifier = Modifier.height(10.dp))

                        val isAlreadyAccepted = status.isJobAccepted || job.status.uppercase() in listOf("ACCEPTED", "COMPLETED")
                        if (!isAlreadyAccepted) {
                            Button(
                                onClick = { onAcceptWork(job.assignmentId) },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.buttonColors(containerColor = RescueBlue),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("✅ ACCEPT WORK ASSIGNMENT", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Badge(containerColor = RescueGreen) {
                                Text("JOB_DISPATCHED", color = Color.White, modifier = Modifier.padding(4.dp))
                            }
                        }
                    } else {
                        Text("No active work assignments. Standing by...", color = RescueSubText, fontSize = 14.sp)
                    }
                }
            }

            // 5. Dedicated RIDGEWATCH REAL GPS Monitoring View (Stage 3)
            val isAlpha1 = status.memberId == "ALPHA-M001"
            val gpsBadgeColor = when (status.gpsStatus) {
                "TRACKING" -> RescueGreen
                "WAITING_FOR_GPS" -> RescueBlue
                "WAITING_FOR_PERMISSION" -> RescueYellow
                "STALE" -> Color(0xFFFF9800) // Orange
                "GPS_UNAVAILABLE", "PERMISSION_DENIED" -> RescueRed
                else -> RescueSubText // STANDBY
            }

            Card(
                colors = CardDefaults.cardColors(containerColor = RescueSurface),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("🛰️ RIDGEWATCH REAL GPS", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 16.sp)
                            Text("REAL PHONE GPS (Native Android Location)", color = RescueSubText, fontSize = 11.sp)
                        }
                        Badge(containerColor = gpsBadgeColor) {
                            Text(
                                text = status.gpsStatus,
                                color = if (status.gpsStatus == "WAITING_FOR_PERMISSION") Color.Black else Color.White,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                fontWeight = FontWeight.Bold,
                                fontSize = 11.sp
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Member:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = if (isAlpha1) "Alpha Member 1 (ALPHA-M001)" else "${status.memberId} (Simulation Only)",
                            color = if (isAlpha1) RescueBlue else RescueSubText,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Mission / Task:", color = RescueSubText, fontSize = 13.sp)
                        val activeTaskStr = status.lastCommand?.commandId
                            ?: status.lastJobAssignment?.let { "${it.title} (${it.assignmentId})" }
                            ?: "None (STANDBY)"
                        Text(
                            text = activeTaskStr,
                            color = RescueText,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    HorizontalDivider(color = RescueCard, thickness = 1.dp, modifier = Modifier.padding(vertical = 6.dp))

                    // Real GPS Coordinates (truthful, never fabricated)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Latitude:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = status.latitude?.let { String.format(Locale.US, "%.6f°", it) } ?: "--",
                            color = if (status.latitude != null) RescueText else RescueSubText,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Longitude:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = status.longitude?.let { String.format(Locale.US, "%.6f°", it) } ?: "--",
                            color = if (status.longitude != null) RescueText else RescueSubText,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Accuracy:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = status.accuracyM?.let { String.format(Locale.US, "%.1f m", it) } ?: "--",
                            color = if (status.accuracyM != null && status.accuracyM <= 25.0f) RescueGreen else RescueYellow,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Speed:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = status.speedMps?.let { String.format(Locale.US, "%.2f m/s (%.1f km/h)", it, it * 3.6) } ?: "--",
                            color = RescueText,
                            fontSize = 13.sp
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Heading:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = status.headingDeg?.let { String.format(Locale.US, "%.1f°", it) } ?: "--",
                            color = RescueText,
                            fontSize = 13.sp
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Last GPS Update:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = status.gpsTimestamp ?: "No GPS fixes yet",
                            color = RescueText,
                            fontSize = 12.sp
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("GPS Update Count:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = "${status.gpsUpdateCount}",
                            color = RescueText,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Backend Connection:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            text = if (status.isBackendConnected) "CONNECTED" else "DISCONNECTED",
                            color = if (status.isBackendConnected) RescueGreen else RescueRed,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    if (isAlpha1 && (status.isMissionAccepted || status.isArrived)) {
                        HorizontalDivider(color = RescueCard, thickness = 1.dp, modifier = Modifier.padding(vertical = 6.dp))

                        val navBadgeColor = when (status.navigationStatus) {
                            "ON_TRACK" -> RescueGreen
                            "WRONG_DIRECTION" -> RescueRed
                            "ARRIVED" -> Color(0xFF8B5CF6)
                            "EN_ROUTE" -> RescueYellow
                            else -> RescueSubText
                        }

                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text("Navigation Status:", color = RescueSubText, fontSize = 13.sp)
                            Badge(containerColor = navBadgeColor) {
                                Text(
                                    text = status.navigationStatus.replace('_', ' '),
                                    color = Color.White,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 11.sp
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(4.dp))

                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Distance to Target:", color = RescueSubText, fontSize = 13.sp)
                            Text(
                                text = status.distanceToTargetM?.let { String.format(Locale.US, "%.1f m", it) } ?: "--",
                                color = if (status.isArrived) RescueGreen else RescueYellow,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        Spacer(modifier = Modifier.height(4.dp))

                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Target Bearing:", color = RescueSubText, fontSize = 13.sp)
                            Text(
                                text = status.targetBearingDeg?.let { String.format(Locale.US, "%.1f°", it) } ?: "--",
                                color = RescueText,
                                fontSize = 13.sp
                            )
                        }

                        if (!status.directionGuidance.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(6.dp))
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = if (status.navigationStatus == "WRONG_DIRECTION") RescueRed.copy(alpha = 0.25f) else RescueSurface
                                ),
                                shape = RoundedCornerShape(8.dp),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(
                                    text = status.directionGuidance,
                                    color = if (status.navigationStatus == "WRONG_DIRECTION") RescueRed else RescueGreen,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    modifier = Modifier.padding(8.dp)
                                )
                            }
                        }
                    }

                    if (status.gpsStatus == "WAITING_FOR_PERMISSION" || (!hasLocationPermission && isAlpha1 && (status.isMissionAccepted || status.isJobAccepted))) {
                        Spacer(modifier = Modifier.height(10.dp))
                        Button(
                            onClick = onRequestLocationPermission,
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = RescueYellow),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("Grant Location Permission", color = Color.Black, fontWeight = FontWeight.Bold)
                        }
                    }

                    if (!isAlpha1) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            "ℹ️ Real GPS is active exclusively for Alpha Member 1. Member ${status.memberId} operates via Commander simulation.",
                            color = RescueSubText,
                            fontSize = 11.sp
                        )
                    }
                }
            }

            // 6. Dual Alert Testing Center Card
            Card(
                colors = CardDefaults.cardColors(containerColor = RescueSurface),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("⚡ Emergency Channels & Testing", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 16.sp)
                    Spacer(modifier = Modifier.height(12.dp))

                    // 6A. Android Notification / Watch Mirroring Test
                    Button(
                        onClick = onTestNotification,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = RescueRed),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text("🚨 Send Test RidgeWatch Notification", fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    }

                    if (testStatus != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        val isSuccess = testStatus.startsWith("TEST_NOTIFICATION_POSTED") || testStatus.startsWith("NOTIFICATION_PERMISSION_GRANTED")
                        val isDenied = testStatus.contains("DENIED")
                        val badgeColor = when {
                            isSuccess -> RescueGreen
                            isDenied -> RescueYellow
                            else -> RescueRed
                        }
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(badgeColor.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
                                .padding(8.dp)
                        ) {
                            Text(
                                text = "Notification: $testStatus",
                                color = badgeColor,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))
                    HorizontalDivider(color = RescueCard, thickness = 1.dp)
                    Spacer(modifier = Modifier.height(14.dp))

                    // 6B. Cellular SMS Alert Test
                    Button(
                        onClick = { onTestSms(null) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = RescueBlue),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text("📱 Send Test Emergency SMS", fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    }

                    if (testSmsStatus != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        val isSmsOk = testSmsStatus.startsWith("SMS_SENT") || testSmsStatus.startsWith("SMS_PERMISSION_GRANTED")
                        val isSmsDenied = testSmsStatus.contains("DENIED") || testSmsStatus.contains("REQUIRED")
                        val smsBadgeColor = when {
                            isSmsOk -> RescueGreen
                            isSmsDenied -> RescueYellow
                            else -> RescueRed
                        }
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(smsBadgeColor.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
                                .padding(8.dp)
                        ) {
                            Text(
                                text = "SMS: $testSmsStatus",
                                color = smsBadgeColor,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }

            // 7. SMS Emergency Channel Status Card
            Card(
                colors = CardDefaults.cardColors(containerColor = RescueSurface),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("📱 SMS Emergency Channel", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 16.sp)
                        val badgeBg = when (status.smsStatus) {
                            "READY", "SENT", "SENT (TEST)" -> RescueGreen
                            "PERMISSION_REQUIRED", "CONTACT_REQUIRED" -> RescueYellow
                            "DISABLED" -> RescueSubText
                            else -> RescueRed
                        }
                        Badge(containerColor = badgeBg) {
                            Text(
                                status.smsStatus,
                                color = Color.White,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                fontWeight = FontWeight.Bold,
                                fontSize = 11.sp
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("SMS Alerts Enabled:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            if (status.isSmsEnabled) "ON (Enabled)" else "OFF (Disabled)",
                            color = if (status.isSmsEnabled) RescueGreen else RescueSubText,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Emergency Contact:", color = RescueSubText, fontSize = 13.sp)
                        Text(
                            if (status.emergencyContact.isNotBlank()) status.emergencyContact else "Not Configured (Tap ⚙️)",
                            color = if (status.emergencyContact.isNotBlank()) RescueText else RescueYellow,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Total SMS Dispatched:", color = RescueSubText, fontSize = 13.sp)
                        Text("${status.totalSmsSent}", color = RescueText, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    }
                    if (status.lastSmsTimestamp > 0) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Last SMS Time:", color = RescueSubText, fontSize = 13.sp)
                            val smsTimeStr = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date(status.lastSmsTimestamp))
                            Text(smsTimeStr, color = RescueText, fontSize = 13.sp)
                        }
                    }
                }
            }

            // 8. Background Service Control
            Card(
                colors = CardDefaults.cardColors(containerColor = RescueSurface),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("Background Rescuer Service", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 15.sp)
                            Text(
                                if (status.isRunning) "Actively polling backend" else "Service stopped",
                                color = RescueSubText,
                                fontSize = 12.sp
                            )
                        }
                        Switch(
                            checked = status.isRunning,
                            onCheckedChange = { if (it) onStartService() else onStopService() }
                        )
                    }
                }
            }

            // 9. Smartwatch Mirroring & GPS Architecture Guide
            Card(
                colors = CardDefaults.cardColors(containerColor = RescueCard),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("ℹ️ RidgeWatch Stage 3 Architecture Guide", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 15.sp)
                    Spacer(modifier = Modifier.height(6.dp))
                    Text("1. Real GPS: Active strictly for Alpha Member 1 upon Mission Acceptance. Zero synthetic movement.", color = RescueSubText, fontSize = 12.sp)
                    Spacer(modifier = Modifier.height(2.dp))
                    Text("2. Simulation Isolation: Alpha 2 and Bravo 1 & 2 remain simulation-driven without disruption.", color = RescueSubText, fontSize = 12.sp)
                    Spacer(modifier = Modifier.height(2.dp))
                    Text("3. Stale Protection: If GPS stops updating for >15s, marked STALE without fabricating replacement coordinates.", color = RescueText, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }

    // Settings Dialog
    if (showSettingsDialog) {
        var tempUrl by remember { mutableStateOf(status.backendUrl) }
        var tempTeam by remember { mutableStateOf(status.teamId) }
        var tempMember by remember { mutableStateOf(status.memberId) }
        var tempSmsEnabled by remember { mutableStateOf(status.isSmsEnabled) }
        var tempEmergencyContact by remember { mutableStateOf(status.emergencyContact) }

        AlertDialog(
            onDismissRequest = { showSettingsDialog = false },
            title = { Text("⚙️ Rescuer Settings", fontWeight = FontWeight.Bold) },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Backend & Identity", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 14.sp)
                    OutlinedTextField(
                        value = tempUrl,
                        onValueChange = { tempUrl = it },
                        label = { Text("Backend URL") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = tempTeam,
                        onValueChange = { tempTeam = it },
                        label = { Text("Team ID (e.g. ALPHA)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = tempMember,
                        onValueChange = { tempMember = it },
                        label = { Text("Member ID (e.g. ALPHA-M001)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(modifier = Modifier.height(6.dp))
                    HorizontalDivider(color = RescueCard, thickness = 1.dp)
                    Spacer(modifier = Modifier.height(6.dp))

                    Text("SMS Emergency Channel", fontWeight = FontWeight.Bold, color = RescueText, fontSize = 14.sp)

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Enable Emergency SMS", color = RescueText, fontSize = 14.sp)
                        Switch(
                            checked = tempSmsEnabled,
                            onCheckedChange = { tempSmsEnabled = it }
                        )
                    }

                    OutlinedTextField(
                        value = tempEmergencyContact,
                        onValueChange = { tempEmergencyContact = it },
                        label = { Text("Emergency Contact Phone") },
                        placeholder = { Text("+919876543210 or 9876543210") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Text(
                        "Enter phone number to receive cellular SMS alerts when a survivor is detected.",
                        color = RescueSubText,
                        fontSize = 11.sp
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        onSaveSettings(
                            tempUrl.trim(),
                            tempTeam.trim(),
                            tempMember.trim(),
                            tempSmsEnabled,
                            tempEmergencyContact.trim()
                        )
                        showSettingsDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = RescueRed)
                ) {
                    Text("Save", color = Color.White, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showSettingsDialog = false }) {
                    Text("Cancel", color = RescueSubText)
                }
            },
            containerColor = RescueSurface
        )
    }
}
