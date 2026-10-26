package org.ridgewatch.rescuer.network

import android.util.Log
import org.json.JSONObject
import org.ridgewatch.rescuer.model.BridgeSyncRequest
import org.ridgewatch.rescuer.model.BridgeSyncResponse
import org.ridgewatch.rescuer.model.CommandStatusReport
import org.ridgewatch.rescuer.model.RescueCommand
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Robust HTTP client for communicating with RIDGEWATCH backend REST APIs.
 */
class RidgeWatchApiClient(private var baseUrl: String) {

    companion object {
        private const val TAG = "RidgeWatchApi"
        private const val CONNECT_TIMEOUT_MS = 6000
        private const val READ_TIMEOUT_MS = 6000
    }

    fun setBaseUrl(url: String) {
        this.baseUrl = url.trimEnd('/')
    }

    fun getBaseUrl(): String = baseUrl

    /**
     * Sends heartbeat and receives any pending/active rescue commands.
     */
    suspend fun sendHeartbeat(request: BridgeSyncRequest): Result<BridgeSyncResponse> = withContext(Dispatchers.IO) {
        try {
            val endpoint = "$baseUrl/api/wearable/bridge/heartbeat"
            val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("Accept", "application/json")
            }

            OutputStreamWriter(conn.outputStream, "UTF-8").use { writer ->
                writer.write(request.toJsonString())
                writer.flush()
            }

            val responseCode = conn.responseCode
            if (responseCode in 200..299) {
                val responseText = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                val jsonObj = JSONObject(responseText)

                val activeCmd = if (jsonObj.has("active_command") && !jsonObj.isNull("active_command")) {
                    RescueCommand.fromJson(jsonObj.getJSONObject("active_command"))
                } else null

                val activeJob = if (jsonObj.has("active_job_assignment") && !jsonObj.isNull("active_job_assignment")) {
                    org.ridgewatch.rescuer.model.JobAssignment.fromJson(jsonObj.getJSONObject("active_job_assignment"))
                } else null

                val navObj = jsonObj.optJSONObject("navigation")
                val navTelemetry = if (navObj != null) {
                    org.ridgewatch.rescuer.model.NavigationTelemetry(
                        navigationStatus = navObj.optString("navigation_status", "STANDBY"),
                        targetBearingDeg = if (navObj.has("target_bearing_deg") && !navObj.isNull("target_bearing_deg")) navObj.optDouble("target_bearing_deg") else null,
                        directionDeltaDeg = if (navObj.has("direction_delta_deg") && !navObj.isNull("direction_delta_deg")) navObj.optDouble("direction_delta_deg") else null,
                        distanceToTargetM = if (navObj.has("distance_to_target_m") && !navObj.isNull("distance_to_target_m")) navObj.optDouble("distance_to_target_m") else null,
                        directionGuidance = navObj.optString("direction_guidance").takeIf { it.isNotBlank() },
                        isArrived = navObj.optBoolean("is_arrived", false),
                        victimId = navObj.optString("victim_id").takeIf { it.isNotBlank() }
                    )
                } else null

                val syncResp = BridgeSyncResponse(
                    status = jsonObj.optString("status", "ok"),
                    sessionId = jsonObj.optString("session_id", request.sessionId),
                    activeCommand = activeCmd,
                    activeJobAssignment = activeJob,
                    serverTime = jsonObj.optString("server_time"),
                    navigation = navTelemetry,
                    missionStatus = jsonObj.optString("mission_status").takeIf { it.isNotBlank() }
                )
                Result.success(syncResp)
            } else {
                val errText = conn.errorStream?.let { BufferedReader(InputStreamReader(it, "UTF-8")).use { r -> r.readText() } }
                Log.w(TAG, "[ANDROID_COMPANION] Heartbeat HTTP $responseCode: $errText")
                Result.failure(Exception("HTTP $responseCode: $errText"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "[ANDROID_COMPANION] Heartbeat connection error: ${e.message}")
            Result.failure(e)
        }
    }

    /**
     * Reports staff job assignment status to backend (e.g. ACCEPTED, IN_PROGRESS, COMPLETED, FAILED).
     */
    suspend fun reportJobStatus(
        assignmentId: String,
        status: String,
        progressPct: Int = 0,
        notes: String? = null
    ): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val endpoint = "$baseUrl/staff/jobs/$assignmentId/status"
            val payload = JSONObject().apply {
                put("status", status)
                put("progress_pct", progressPct)
                if (notes != null) put("result_notes", notes)
            }

            val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("Accept", "application/json")
            }

            OutputStreamWriter(conn.outputStream, "UTF-8").use { writer ->
                writer.write(payload.toString())
                writer.flush()
            }

            val responseCode = conn.responseCode
            if (responseCode in 200..299) {
                Log.i(TAG, "[ANDROID_COMPANION] Successfully reported job status '$status' for assignment $assignmentId")
                Result.success(true)
            } else {
                val errText = conn.errorStream?.let { BufferedReader(InputStreamReader(it, "UTF-8")).use { r -> r.readText() } }
                Log.w(TAG, "[ANDROID_COMPANION] Job status report HTTP $responseCode: $errText")
                Result.failure(Exception("HTTP $responseCode: $errText"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "[ANDROID_COMPANION] Job status report error for $assignmentId: ${e.message}")
            Result.failure(e)
        }
    }

    /**
     * Reports command status to the backend (e.g. PHONE_NOTIFICATION_POSTED).
     */
    suspend fun reportCommandStatus(commandId: String, status: String, error: String? = null): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val endpoint = "$baseUrl/api/wearable/commands/$commandId/status"
            val report = CommandStatusReport(commandId = commandId, status = status, deliveryError = error)

            val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("Accept", "application/json")
            }

            OutputStreamWriter(conn.outputStream, "UTF-8").use { writer ->
                writer.write(report.toJsonString())
                writer.flush()
            }

            val responseCode = conn.responseCode
            if (responseCode in 200..299) {
                Log.i(TAG, "[ANDROID_COMPANION] Successfully reported status '$status' for command $commandId")
                Result.success(true)
            } else {
                val errText = conn.errorStream?.let { BufferedReader(InputStreamReader(it, "UTF-8")).use { r -> r.readText() } }
                Log.w(TAG, "[ANDROID_COMPANION] Status report HTTP $responseCode: $errText")
                Result.failure(Exception("HTTP $responseCode: $errText"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "[ANDROID_COMPANION] Status report error for $commandId: ${e.message}")
            Result.failure(e)
        }
    }

    /**
     * Triggers backend development test alert.
     */
    suspend fun triggerTestAlert(teamId: String = "ALPHA", memberId: String = "ALPHA-M001"): Result<RescueCommand?> = withContext(Dispatchers.IO) {
        try {
            val endpoint = "$baseUrl/api/wearable/commands/test_alert"
            val payload = JSONObject().apply {
                put("team_id", teamId)
                put("member_id", memberId)
                put("target_id", "Survivor")
                put("location_label", "Test Sector Alpha")
                put("distance_m", 45.0)
            }

            val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("Accept", "application/json")
            }

            OutputStreamWriter(conn.outputStream, "UTF-8").use { writer ->
                writer.write(payload.toString())
                writer.flush()
            }

            val responseCode = conn.responseCode
            if (responseCode in 200..299) {
                val responseText = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                val jsonObj = JSONObject(responseText)
                val cmd = if (jsonObj.has("command") && !jsonObj.isNull("command")) {
                    RescueCommand.fromJson(jsonObj.getJSONObject("command"))
                } else if (jsonObj.has("command_id")) {
                    RescueCommand.fromJson(jsonObj)
                } else null
                Result.success(cmd)
            } else {
                val errText = conn.errorStream?.let { BufferedReader(InputStreamReader(it, "UTF-8")).use { r -> r.readText() } }
                Result.failure(Exception("HTTP $responseCode: $errText"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
