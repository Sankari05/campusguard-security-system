package org.ridgewatch.rescuer.notification

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import org.ridgewatch.rescuer.R
import org.ridgewatch.rescuer.model.RescueCommand
import org.ridgewatch.rescuer.ui.MainActivity

/**
 * Manages high-priority emergency notifications and system channels.
 */
class EmergencyNotificationManager(private val context: Context) {

    companion object {
        const val TAG = "RidgeWatchNotif"
        const val DIAGNOSTIC_TAG = "RIDGEWATCH_TEST"
        const val CHANNEL_EMERGENCY_ID = "RIDGEWATCH_EMERGENCY"
        const val CHANNEL_EMERGENCY_NAME = "RidgeWatch Emergency Alerts"
        const val CHANNEL_JOB_ID = "RIDGEWATCH_WORK"
        const val CHANNEL_JOB_NAME = "RidgeWatch Work Assignments"
        const val CHANNEL_SERVICE_ID = "RIDGEWATCH_SERVICE"
        const val CHANNEL_SERVICE_NAME = "RidgeWatch Companion Service"
        const val SERVICE_NOTIFICATION_ID = 9001
        val EMERGENCY_VIBRATION_PATTERN = longArrayOf(0, 500, 200, 500, 200, 500)
    }

    init {
        createNotificationChannels()
    }

    /**
     * Sets up the Android Notification Channels for Emergency Alerts, Work Assignments, and Background Service.
     */
    fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            if (notificationManager == null) {
                Log.e(TAG, "[ANDROID_COMPANION] NotificationManager system service is NULL")
                return
            }

            // 1. High-Priority Emergency Channel (Mirrors to Smartwatches)
            val emergencySound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            val audioAttributes = AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setUsage(AudioAttributes.USAGE_ALARM)
                .build()

            val emergencyChannel = NotificationChannel(
                CHANNEL_EMERGENCY_ID,
                CHANNEL_EMERGENCY_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Critical Survivor Detection and Disaster Rescue GO Commands"
                enableLights(true)
                lightColor = Color.RED
                enableVibration(true)
                vibrationPattern = EMERGENCY_VIBRATION_PATTERN
                setSound(emergencySound, audioAttributes)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                setShowBadge(true)
            }
            notificationManager.createNotificationChannel(emergencyChannel)
            Log.d(DIAGNOSTIC_TAG, "NotificationChannel created/verified: $CHANNEL_EMERGENCY_ID (IMPORTANCE_HIGH)")

            // 2. Work / Job Assignment Channel (Distinct, Non-Emergency)
            val jobChannel = NotificationChannel(
                CHANNEL_JOB_ID,
                CHANNEL_JOB_NAME,
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Operational tasks and work assignments from Commander"
                enableLights(true)
                lightColor = Color.CYAN
                enableVibration(true)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                setShowBadge(true)
            }
            notificationManager.createNotificationChannel(jobChannel)
            Log.d(DIAGNOSTIC_TAG, "NotificationChannel created/verified: $CHANNEL_JOB_ID (IMPORTANCE_DEFAULT)")

            // 3. Low-Importance Ongoing Background Service Channel
            val serviceChannel = NotificationChannel(
                CHANNEL_SERVICE_ID,
                CHANNEL_SERVICE_NAME,
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Background monitoring connection to RIDGEWATCH backend"
                setShowBadge(false)
            }
            notificationManager.createNotificationChannel(serviceChannel)
        }
    }

    /**
     * Builds the foreground service notification.
     */
    fun buildServiceNotification(statusText: String): Notification {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
        )

        return NotificationCompat.Builder(context, CHANNEL_SERVICE_ID)
            .setContentTitle("🛡️ RidgeWatch Companion Active")
            .setContentText(statusText)
            .setSmallIcon(R.drawable.ic_notification_emergency)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(pendingIntent)
            .build()
    }

    /**
     * Triggers physical device vibration directly for emergency feedback.
     */
    fun triggerDirectVibration() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                val vibrator = vibratorManager?.defaultVibrator
                vibrator?.vibrate(VibrationEffect.createWaveform(EMERGENCY_VIBRATION_PATTERN, -1))
            } else {
                @Suppress("DEPRECATION")
                val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator?.vibrate(VibrationEffect.createWaveform(EMERGENCY_VIBRATION_PATTERN, -1))
                } else {
                    @Suppress("DEPRECATION")
                    vibrator?.vibrate(EMERGENCY_VIBRATION_PATTERN, -1)
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Direct vibration failed: ${e.message}")
        }
    }

    /**
     * Posts a native emergency rescue notification.
     * Honestly reports package identity: org.ridgewatch.rescuer.
     */
    fun postEmergencyNotification(command: RescueCommand): NotificationResult {
        // Ensure channels are created before notify
        createNotificationChannels()

        val notificationManager = NotificationManagerCompat.from(context)
        if (!notificationManager.areNotificationsEnabled()) {
            Log.w(DIAGNOSTIC_TAG, "POST_ABORTED: Notifications are disabled in Android Settings for org.ridgewatch.rescuer")
            return NotificationResult.PermissionDenied("Notifications are disabled in Android system settings for this app")
        }

        try {
            val intent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                putExtra("EXTRA_COMMAND_ID", command.commandId)
            }
            val pendingIntent = PendingIntent.getActivity(
                context,
                command.commandId.hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )

            val distStr = command.distanceM?.let { " (${Math.round(it)}m)" } ?: ""
            val bodyText = "Target: ${command.targetId}$distStr\nSector: ${command.locationLabel}\nAlert: ${command.commandId}"

            val builder = NotificationCompat.Builder(context, CHANNEL_EMERGENCY_ID)
                .setContentTitle(command.title)
                .setContentText(bodyText)
                .setStyle(NotificationCompat.BigTextStyle().bigText(bodyText))
                .setSmallIcon(R.drawable.ic_notification_emergency)
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setVibrate(EMERGENCY_VIBRATION_PATTERN)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)

            val notificationId = command.commandId.hashCode()

            Log.d(DIAGNOSTIC_TAG, "BEFORE_NOTIFY: id=$notificationId channel=$CHANNEL_EMERGENCY_ID title='${command.title}'")
            notificationManager.notify(notificationId, builder.build())
            Log.d(DIAGNOSTIC_TAG, "AFTER_NOTIFY: success=true notificationId=$notificationId")

            // Provide immediate tactile haptic feedback
            triggerDirectVibration()

            Log.i(TAG, "[ANDROID_COMPANION] NOTIFICATION_POSTED command_id=${command.commandId}")
            Log.i(TAG, "[ANDROID_COMPANION] WATCH_DELIVERY_UNCONFIRMED command_id=${command.commandId}")
            return NotificationResult.Success(command.commandId, notificationId)
        } catch (e: SecurityException) {
            Log.e(DIAGNOSTIC_TAG, "POST_FAILED SecurityException: ${e.message}", e)
            return NotificationResult.PermissionDenied(e.message ?: "SecurityException posting notification")
        } catch (e: Exception) {
            Log.e(DIAGNOSTIC_TAG, "POST_FAILED Exception: ${e.message}", e)
            return NotificationResult.Failed(e.message ?: "Exception posting notification")
        }
    }

    /**
     * Posts a work/job assignment notification (distinct non-emergency channel).
     */
    fun postJobNotification(job: org.ridgewatch.rescuer.model.JobAssignment): NotificationResult {
        createNotificationChannels()

        val notificationManager = NotificationManagerCompat.from(context)
        if (!notificationManager.areNotificationsEnabled()) {
            Log.w(DIAGNOSTIC_TAG, "POST_ABORTED: Notifications are disabled in Android Settings for org.ridgewatch.rescuer")
            return NotificationResult.PermissionDenied("Notifications are disabled in Android system settings for this app")
        }

        try {
            val intent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                putExtra("EXTRA_ASSIGNMENT_ID", job.assignmentId)
            }
            val pendingIntent = PendingIntent.getActivity(
                context,
                job.assignmentId.hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )

            val bodyText = "Task: ${job.jobName}\nLocation: ${job.location ?: "Assigned Sector"}\nStatus: ${job.status}"

            val builder = NotificationCompat.Builder(context, CHANNEL_JOB_ID)
                .setContentTitle(job.title)
                .setContentText(bodyText)
                .setStyle(NotificationCompat.BigTextStyle().bigText(bodyText))
                .setSmallIcon(R.drawable.ic_notification_emergency)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .setCategory(NotificationCompat.CATEGORY_EVENT)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)

            val notificationId = job.assignmentId.hashCode()

            Log.d(DIAGNOSTIC_TAG, "BEFORE_NOTIFY_JOB: id=$notificationId channel=$CHANNEL_JOB_ID title='${job.title}'")
            notificationManager.notify(notificationId, builder.build())
            Log.d(DIAGNOSTIC_TAG, "AFTER_NOTIFY_JOB: success=true notificationId=$notificationId")

            Log.i(TAG, "[ANDROID_COMPANION] JOB_NOTIFICATION_POSTED assignment_id=${job.assignmentId}")
            return NotificationResult.Success(job.assignmentId, notificationId)
        } catch (e: SecurityException) {
            Log.e(DIAGNOSTIC_TAG, "POST_JOB_FAILED SecurityException: ${e.message}", e)
            return NotificationResult.PermissionDenied(e.message ?: "SecurityException posting job notification")
        } catch (e: Exception) {
            Log.e(DIAGNOSTIC_TAG, "POST_JOB_FAILED Exception: ${e.message}", e)
            return NotificationResult.Failed(e.message ?: "Exception posting job notification")
        }
    }

    sealed class NotificationResult {
        data class Success(val commandId: String, val notificationId: Int) : NotificationResult()
        data class PermissionDenied(val reason: String) : NotificationResult()
        data class Failed(val error: String) : NotificationResult()
    }
}
