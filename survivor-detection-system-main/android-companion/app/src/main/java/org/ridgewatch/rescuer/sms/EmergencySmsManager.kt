package org.ridgewatch.rescuer.sms

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.telephony.SmsManager
import android.util.Log
import androidx.core.content.ContextCompat
import org.ridgewatch.rescuer.model.RescueCommand
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Result state for SMS alert operations.
 */
sealed class SmsResult {
    data class Success(
        val recipient: String,
        val message: String,
        val partsCount: Int = 1,
        val timestamp: Long = System.currentTimeMillis()
    ) : SmsResult()

    data class Disabled(
        val reason: String = "SMS Emergency Alerting is disabled in settings"
    ) : SmsResult()

    data class PermissionDenied(
        val reason: String = "SEND_SMS permission not granted by user"
    ) : SmsResult()

    data class InvalidRecipient(
        val recipient: String,
        val reason: String
    ) : SmsResult()

    data class Failed(
        val error: String,
        val exception: Throwable? = null
    ) : SmsResult()
}

/**
 * EmergencySmsManager
 * -------------------
 * Manages cellular SMS-based emergency notifications for RidgeWatch.
 *
 * Key Guarantees:
 * 1. Independent & Non-Blocking: SMS failure never throws an unhandled exception or interrupts the notification flow.
 * 2. Truthful State: SMS_SENT only indicates submission to the cellular telephony stack; it does not claim watch delivery.
 * 3. Clear Separation: Test alerts and real emergency alerts use distinct, unambiguous formats.
 * 4. Zero Hardcoded Credentials: All recipient destinations are dynamically passed or retrieved from user configuration.
 */
class EmergencySmsManager(private val context: Context) {

    companion object {
        private const val TAG = "RidgeWatchSMS"

        /**
         * Validates a destination phone number string.
         * Allows E.164 (+1234567890), national formats (9876543210), and emergency shortcodes (112, 911).
         */
        fun validateRecipient(recipient: String?): Boolean {
            if (recipient.isNullOrBlank()) return false
            val sanitized = recipient.trim().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if (sanitized.isEmpty()) return false
            // Allow + prefix followed by 3 to 15 digits
            val phoneRegex = Regex("""^\+?[0-9]{3,15}$""")
            return phoneRegex.matches(sanitized)
        }

        /**
         * Sanitizes a recipient string into a compact dialable string.
         */
        fun sanitizeRecipient(recipient: String): String {
            return recipient.trim().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        }

        /**
         * Builds canonical real emergency SMS message text.
         */
        fun buildEmergencySms(command: RescueCommand, timeFormatted: String? = null): String {
            val timeStr = timeFormatted ?: formatCurrentTime()
            val location = command.locationLabel.ifBlank { "Sector Unknown" }
            val priority = command.priority.ifBlank { "HIGH" }
            val alertId = command.commandId.ifBlank { "ALERT" }
            val distLabel = if (!command.distanceLabel.isNullOrBlank()) " (${command.distanceLabel})" else ""

            return """
🚨 RIDGEWATCH EMERGENCY ALERT

Survivor detected.

Priority: $priority
Location: $location$distLabel
Alert ID: $alertId
Time: $timeStr

Please check RidgeWatch immediately.
""".trimIndent()
        }

        /**
         * Builds canonical test alert SMS message text.
         */
        fun buildTestSms(timeFormatted: String? = null): String {
            val timeStr = timeFormatted ?: formatCurrentTime()
            return """
🚨 RIDGEWATCH TEST ALERT

This is a test message.
No real emergency detected.
Time: $timeStr
""".trimIndent()
        }

        private fun formatCurrentTime(): String {
            return try {
                SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
            } catch (e: Exception) {
                "NOW"
            }
        }
    }

    /**
     * Checks if the app currently holds SEND_SMS permission.
     */
    fun hasSmsPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.SEND_SMS
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Resolves the appropriate system SmsManager instance across Android API levels.
     */
    private fun getSystemSmsManager(): SmsManager {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            context.getSystemService(SmsManager::class.java) ?: SmsManager.getDefault()
        } else {
            @Suppress("DEPRECATION")
            SmsManager.getDefault()
        }
    }

    /**
     * Sends an emergency SMS for an active rescue command.
     *
     * @param command The active rescue command.
     * @param recipient Optional recipient override; if null/blank, must be provided by caller.
     * @return SmsResult capturing the outcome.
     */
    fun sendEmergencySms(command: RescueCommand, recipient: String?): SmsResult {
        if (recipient.isNullOrBlank()) {
            Log.w(TAG, "[SMS_SKIPPED] No emergency contact configured for command=${command.commandId}")
            return SmsResult.Disabled("Emergency contact phone number is not configured")
        }

        val messageText = buildEmergencySms(command)
        return sendRawSms(recipient, messageText, isEmergency = true, commandId = command.commandId)
    }

    /**
     * Sends a test emergency SMS.
     *
     * @param recipient Destination phone number.
     * @return SmsResult capturing the outcome.
     */
    fun sendTestSms(recipient: String?): SmsResult {
        if (recipient.isNullOrBlank()) {
            Log.w(TAG, "[SMS_SKIPPED] No recipient provided for test SMS")
            return SmsResult.InvalidRecipient("", "Recipient phone number is required for test SMS")
        }

        val messageText = buildTestSms()
        return sendRawSms(recipient, messageText, isEmergency = false, commandId = "TEST-SMS")
    }

    /**
     * Internal raw SMS dispatcher.
     * Handles permission checks, recipient validation, message splitting, and error resilience.
     */
    fun sendRawSms(
        recipient: String,
        messageText: String,
        isEmergency: Boolean = false,
        commandId: String = "MANUAL"
    ): SmsResult {
        val sanitizedRecipient = sanitizeRecipient(recipient)

        if (!validateRecipient(sanitizedRecipient)) {
            Log.e(TAG, "[SMS_FAILED] Invalid recipient phone number: '$recipient'")
            return SmsResult.InvalidRecipient(
                recipient,
                "Phone number must contain 3 to 15 digits (e.g. +919876543210 or 9876543210)"
            )
        }

        if (!hasSmsPermission()) {
            Log.w(TAG, "[SMS_PERMISSION_DENIED] SEND_SMS permission is not granted. Cannot dispatch SMS.")
            return SmsResult.PermissionDenied("SEND_SMS permission required")
        }

        return try {
            val smsManager = getSystemSmsManager()
            val parts = smsManager.divideMessage(messageText)

            Log.i(
                TAG,
                "[SMS_DISPATCH] Dispatching ${if (isEmergency) "EMERGENCY" else "TEST"} SMS " +
                        "to=$sanitizedRecipient parts=${parts.size} commandId=$commandId"
            )

            if (parts.size > 1) {
                smsManager.sendMultipartTextMessage(
                    sanitizedRecipient,
                    null,
                    parts,
                    null,
                    null
                )
            } else {
                smsManager.sendTextMessage(
                    sanitizedRecipient,
                    null,
                    messageText,
                    null,
                    null
                )
            }

            Log.i(
                TAG,
                "[SMS_SENT] Successfully submitted SMS to telephony provider " +
                        "recipient=$sanitizedRecipient commandId=$commandId"
            )

            SmsResult.Success(
                recipient = sanitizedRecipient,
                message = messageText,
                partsCount = parts.size,
                timestamp = System.currentTimeMillis()
            )
        } catch (secEx: SecurityException) {
            Log.e(TAG, "[SMS_SECURITY_EXCEPTION] Failed to send SMS: ${secEx.message}", secEx)
            SmsResult.PermissionDenied(secEx.message ?: "Security exception accessing SMS telephony stack")
        } catch (argEx: IllegalArgumentException) {
            Log.e(TAG, "[SMS_ILLEGAL_ARGUMENT] Invalid argument for SMS: ${argEx.message}", argEx)
            SmsResult.InvalidRecipient(sanitizedRecipient, argEx.message ?: "Invalid phone number or message argument")
        } catch (e: Exception) {
            Log.e(TAG, "[SMS_EXCEPTION] Unexpected error sending SMS: ${e.message}", e)
            SmsResult.Failed(e.message ?: "Unknown telephony error occurred", e)
        }
    }
}
