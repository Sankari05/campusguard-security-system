package org.ridgewatch.rescuer.sms

import org.junit.Assert.*
import org.junit.Test
import org.ridgewatch.rescuer.model.RescueCommand

class EmergencySmsManagerTest {

    @Test
    fun testValidateRecipient_validNumbers() {
        assertTrue(EmergencySmsManager.validateRecipient("+919876543210"))
        assertTrue(EmergencySmsManager.validateRecipient("9876543210"))
        assertTrue(EmergencySmsManager.validateRecipient("+14155552671"))
        assertTrue(EmergencySmsManager.validateRecipient("112"))
        assertTrue(EmergencySmsManager.validateRecipient("911"))
        assertTrue(EmergencySmsManager.validateRecipient(" +91 98765-43210 "))
        assertTrue(EmergencySmsManager.validateRecipient("(987) 654-3210"))
    }

    @Test
    fun testValidateRecipient_invalidNumbers() {
        assertFalse(EmergencySmsManager.validateRecipient(null))
        assertFalse(EmergencySmsManager.validateRecipient(""))
        assertFalse(EmergencySmsManager.validateRecipient("   "))
        assertFalse(EmergencySmsManager.validateRecipient("abc"))
        assertFalse(EmergencySmsManager.validateRecipient("12")) // Less than 3 digits
        assertFalse(EmergencySmsManager.validateRecipient("++919876543210"))
        assertFalse(EmergencySmsManager.validateRecipient("9876543210123456789")) // Too long
    }

    @Test
    fun testSanitizeRecipient() {
        assertEquals("+919876543210", EmergencySmsManager.sanitizeRecipient("+91 98765-43210"))
        assertEquals("9876543210", EmergencySmsManager.sanitizeRecipient("(987) 654-3210"))
    }

    @Test
    fun testBuildEmergencySms_containsCanonicalFields() {
        val command = RescueCommand(
            commandId = "CMD-TEST-7788",
            teamId = "ALPHA",
            memberId = "ALPHA-M001",
            commandType = "GO",
            targetId = "Survivor-42",
            locationLabel = "Sector Charlie",
            distanceM = 120.0,
            distanceLabel = "120 m",
            priority = "HIGH"
        )

        val sms = EmergencySmsManager.buildEmergencySms(command, timeFormatted = "14:30")

        assertTrue(sms.contains("🚨 RIDGEWATCH EMERGENCY ALERT"))
        assertTrue(sms.contains("Survivor detected."))
        assertTrue(sms.contains("Priority: HIGH"))
        assertTrue(sms.contains("Location: Sector Charlie (120 m)"))
        assertTrue(sms.contains("Alert ID: CMD-TEST-7788"))
        assertTrue(sms.contains("Time: 14:30"))
        assertTrue(sms.contains("Please check RidgeWatch immediately."))
    }

    @Test
    fun testBuildTestSms_containsClearTestMarkers() {
        val testSms = EmergencySmsManager.buildTestSms(timeFormatted = "14:30")

        assertTrue(testSms.contains("🚨 RIDGEWATCH TEST ALERT"))
        assertTrue(testSms.contains("This is a test message."))
        assertTrue(testSms.contains("No real emergency detected."))
        assertTrue(testSms.contains("Time: 14:30"))

        // Must not contain real emergency text
        assertFalse(testSms.contains("Please check RidgeWatch immediately."))
        assertFalse(testSms.contains("Survivor detected."))
    }

    @Test
    fun testEmergencyAndTestSms_areDistinct() {
        val command = RescueCommand(
            commandId = "CMD-REAL-001",
            teamId = "ALPHA",
            memberId = "ALPHA-M001",
            commandType = "GO",
            targetId = "Survivor-1",
            locationLabel = "Sector Alpha",
            priority = "CRITICAL"
        )

        val emergencySms = EmergencySmsManager.buildEmergencySms(command, "12:00")
        val testSms = EmergencySmsManager.buildTestSms("12:00")

        assertNotEquals(emergencySms, testSms)
        assertTrue(emergencySms.contains("EMERGENCY ALERT"))
        assertTrue(testSms.contains("TEST ALERT"))
    }
}
