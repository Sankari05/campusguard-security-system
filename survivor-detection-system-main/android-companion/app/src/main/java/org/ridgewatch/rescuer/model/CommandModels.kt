package org.ridgewatch.rescuer.model

import org.json.JSONObject
import java.io.Serializable

/**
 * High-priority rescue command received from RIDGEWATCH backend.
 */
data class RescueCommand(
    val commandId: String,
    val teamId: String,
    val memberId: String,
    val commandType: String = "GO",
    val targetId: String = "Survivor",
    val victimId: String? = null,
    val locationLabel: String = "Target Location",
    val distanceM: Double? = null,
    val distanceLabel: String? = null,
    val priority: String = "HIGH",
    val title: String = "🚨 RIDGEWATCH — GO",
    val body: String = "Survivor detected. Proceed to assigned rescue sector.",
    val createdAt: String? = null,
    val status: String = "SENT_TO_BRIDGE"
) : Serializable {
    companion object {
        fun fromJson(json: JSONObject): RescueCommand {
            val cmdId = json.optString("command_id", "CMD-UNKNOWN")
            val notifObj = json.optJSONObject("notification_payload")
            val title = notifObj?.optString("title") ?: json.optString("title", "🚨 RIDGEWATCH — GO")
            val body = notifObj?.optString("body") ?: json.optString("message", "Survivor detected. Proceed to assigned sector.")
            val priority = if (notifObj != null && notifObj.has("priority")) notifObj.optString("priority", "HIGH") else json.optString("priority", "HIGH")
            val distLabel = if (notifObj != null && notifObj.has("distance_label")) notifObj.optString("distance_label") else json.optString("distance_label")

            val dist = if (json.has("distance_m") && !json.isNull("distance_m")) {
                json.optDouble("distance_m")
            } else null

            return RescueCommand(
                commandId = cmdId,
                teamId = json.optString("team_id", "ALPHA"),
                memberId = json.optString("member_id", "ALPHA-M001"),
                commandType = json.optString("command_type", "GO"),
                targetId = json.optString("target_id", json.optString("victim_id", "Survivor")),
                victimId = json.optString("victim_id").takeIf { it.isNotBlank() },
                locationLabel = json.optString("location_label", json.optString("location", "Target Sector")),
                distanceM = dist,
                distanceLabel = distLabel,
                priority = priority,
                title = title,
                body = body,
                createdAt = json.optString("created_at"),
                status = json.optString("status", "SENT_TO_BRIDGE")
            )
        }
    }
}

/**
 * Rescuer Bridge Heartbeat Sync Request.
 */
data class BridgeSyncRequest(
    val sessionId: String,
    val teamId: String,
    val memberId: String,
    val deviceName: String = "RidgeWatch Native Android Companion",
    val watchDeviceId: String = "DEV-WEARABLE-CALLPLUS",
    val watchMac: String = "CB:4E:FD:EE:7F:1B",
    val watchModel: String = "Wave Call Plus",
    val watchConnected: Boolean = false,
    val bluetoothState: String = "ENABLED",
    val gpsAvailable: Boolean = true,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val altitudeM: Double? = null,
    val accuracyM: Float? = null,
    val speedMps: Float? = null,
    val headingDeg: Float? = null,
    val timestamp: String? = null,
    val locationSource: String = "PHONE_GPS",
    val status: String = "ONLINE",
    val notes: String = "Native Android Companion Active",
    val gpsStatus: String? = null
) {
    fun toJsonString(): String {
        val json = JSONObject()
        json.put("session_id", sessionId)
        json.put("team_id", teamId)
        json.put("member_id", memberId)
        json.put("device_name", deviceName)
        json.put("watch_device_id", watchDeviceId)
        json.put("watch_mac", watchMac)
        json.put("watch_model", watchModel)
        json.put("watch_connected", watchConnected)
        json.put("bluetooth_state", bluetoothState)
        json.put("gps_available", gpsAvailable)
        if (latitude != null) json.put("latitude", latitude)
        if (longitude != null) json.put("longitude", longitude)
        if (altitudeM != null) json.put("altitude_m", altitudeM)
        if (accuracyM != null) json.put("accuracy_m", accuracyM.toDouble())
        if (speedMps != null) json.put("speed_mps", speedMps.toDouble())
        if (headingDeg != null) json.put("heading_deg", headingDeg.toDouble())
        if (timestamp != null) json.put("timestamp", timestamp)
        if (gpsStatus != null) json.put("gps_status", gpsStatus)
        json.put("location_source", locationSource)
        json.put("status", status)
        json.put("notes", notes)
        return json.toString()
    }
}

/**
 * Real-time navigation telemetry from backend guidance engine (Stage 4).
 */
data class NavigationTelemetry(
    val navigationStatus: String = "STANDBY", // ON_TRACK | WRONG_DIRECTION | ARRIVED | EN_ROUTE | STANDBY
    val targetBearingDeg: Double? = null,
    val directionDeltaDeg: Double? = null,
    val distanceToTargetM: Double? = null,
    val directionGuidance: String? = null,
    val isArrived: Boolean = false,
    val victimId: String? = null
) : Serializable

/**
 * Staff Work/Job Assignment received from RIDGEWATCH backend.
 */
data class JobAssignment(
    val assignmentId: String,
    val jobId: String,
    val jobName: String,
    val memberId: String,
    val teamId: String,
    val scenarioId: String? = null,
    val location: String? = null,
    val priority: String = "HIGH",
    val description: String? = null,
    val resultNotes: String? = null,
    val progressPct: Int = 0,
    val status: String = "ASSIGNED",
    val assignedAt: String? = null,
    val title: String = "📋 Work Assignment",
    val body: String = "You have been assigned a new task."
) : Serializable {
    companion object {
        fun fromJson(json: JSONObject): JobAssignment {
            val aId = json.optString("assignment_id", "ASN-UNKNOWN")
            val jId = json.optString("job_id", "")
            val jName = json.optString("job_name", if (jId.isNotBlank()) "Job $jId" else "Work Assignment")
            val loc = if (json.has("location") && !json.isNull("location")) {
                json.optString("location")
            } else if (json.has("job_location") && !json.isNull("job_location")) {
                json.optString("job_location")
            } else "Assigned Sector"

            val desc = if (json.has("description") && !json.isNull("description")) {
                json.optString("description")
            } else if (json.has("job_description") && !json.isNull("job_description")) {
                json.optString("job_description")
            } else ""

            val prio = if (json.has("priority") && !json.isNull("priority")) {
                json.optString("priority")
            } else if (json.has("job_priority") && !json.isNull("job_priority")) {
                json.optString("job_priority")
            } else "HIGH"

            val stat = json.optString("status", "ASSIGNED")

            return JobAssignment(
                assignmentId = aId,
                jobId = jId,
                jobName = jName,
                memberId = json.optString("member_id", "ALPHA-M001"),
                teamId = json.optString("team_id", "ALPHA"),
                scenarioId = json.optString("scenario_id").takeIf { it.isNotBlank() },
                location = loc.takeIf { it.isNotBlank() },
                priority = prio,
                description = desc.takeIf { it.isNotBlank() },
                resultNotes = json.optString("result_notes").takeIf { it.isNotBlank() },
                progressPct = json.optInt("progress_pct", 0),
                status = stat,
                assignedAt = json.optString("assigned_at").takeIf { it.isNotBlank() },
                title = "📋 WORK ASSIGNMENT: $jName",
                body = "Task: $jName\nLocation: $loc\nStatus: $stat"
            )
        }
    }
}

/**
 * Rescuer Bridge Heartbeat Sync Response.
 */
data class BridgeSyncResponse(
    val status: String,
    val sessionId: String,
    val activeCommand: RescueCommand?,
    val activeJobAssignment: JobAssignment? = null,
    val serverTime: String? = null,
    val navigation: NavigationTelemetry? = null,
    val missionStatus: String? = null
)

/**
 * Command Status Update payload.
 */
data class CommandStatusReport(
    val commandId: String,
    val status: String, // PHONE_NOTIFICATION_POSTED | WATCH_DELIVERY_UNCONFIRMED | COMMAND_RECEIVED_BY_ANDROID
    val deliveryError: String? = null
) {
    fun toJsonString(): String {
        val json = JSONObject()
        json.put("status", status)
        json.put("delivery_error", deliveryError)
        return json.toString()
    }
}

