package org.ridgewatch.rescuer.location

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.ridgewatch.rescuer.location.RescuerLocationTracker.Companion.isAcceptableAccuracy
import org.ridgewatch.rescuer.location.RescuerLocationTracker.Companion.isValidCoordinate
import org.ridgewatch.rescuer.location.RescuerLocationTracker.Companion.formatIso8601
import org.ridgewatch.rescuer.location.RescuerLocationTracker.GpsStatus
import org.ridgewatch.rescuer.location.RescuerLocationTracker.GpsLocationData
import org.ridgewatch.rescuer.model.BridgeSyncRequest

class RescuerLocationTrackerTest {

    @Test
    fun testIsValidCoordinate_validInputs() {
        assertTrue(isValidCoordinate(32.3739, 77.2491))
        assertTrue(isValidCoordinate(-33.8688, 151.2093))
        assertTrue(isValidCoordinate(90.0, 0.1))
        assertTrue(isValidCoordinate(-90.0, -179.9))
    }

    @Test
    fun testIsValidCoordinate_invalidBoundsAndNullIsland() {
        // Null Island rejection
        assertFalse(isValidCoordinate(0.0, 0.0))

        // Latitude out of bounds
        assertFalse(isValidCoordinate(90.001, 77.0))
        assertFalse(isValidCoordinate(-90.001, 77.0))

        // Longitude out of bounds
        assertFalse(isValidCoordinate(32.0, 180.001))
        assertFalse(isValidCoordinate(32.0, -180.001))
    }

    @Test
    fun testIsAcceptableAccuracy() {
        assertTrue(isAcceptableAccuracy(5.0f))
        assertTrue(isAcceptableAccuracy(15.0f))
        assertTrue(isAcceptableAccuracy(150.0f))

        // Unacceptable / bad readings
        assertFalse(isAcceptableAccuracy(0.0f))
        assertFalse(isAcceptableAccuracy(-1.0f))
        assertFalse(isAcceptableAccuracy(150.1f))
        assertFalse(isAcceptableAccuracy(500.0f))
    }

    @Test
    fun testFormatIso8601() {
        val epochMs = 1700000000000L
        val formatted = formatIso8601(epochMs)
        assertNotNull(formatted)
        assertTrue(formatted.endsWith("Z"))
        assertTrue(formatted.contains("T"))
    }

    @Test
    fun testGpsLocationDataModel_immutabilityAndDefaults() {
        val defaultData = GpsLocationData()
        assertEquals(GpsStatus.STANDBY, defaultData.status)
        assertNull(defaultData.latitude)
        assertNull(defaultData.longitude)
        assertEquals("PHONE_GPS", defaultData.locationSource)
        assertEquals(0, defaultData.updateCount)

        val trackingData = defaultData.copy(
            latitude = 32.3739,
            longitude = 77.2491,
            accuracyM = 4.2f,
            speedMps = 1.3f,
            headingDeg = 180.0f,
            status = GpsStatus.TRACKING,
            updateCount = 1
        )

        assertEquals(GpsStatus.TRACKING, trackingData.status)
        assertEquals(32.3739, trackingData.latitude!!, 0.0001)
        assertEquals(77.2491, trackingData.longitude!!, 0.0001)
        assertEquals(4.2f, trackingData.accuracyM!!, 0.01f)
        assertEquals(1.3f, trackingData.speedMps!!, 0.01f)
        assertEquals(180.0f, trackingData.headingDeg!!, 0.01f)
        assertEquals(1, trackingData.updateCount)
    }

    @Test
    fun testBridgeSyncRequest_realGpsSerialization() {
        val req = BridgeSyncRequest(
            sessionId = "TEST-SES-001",
            teamId = "ALPHA",
            memberId = "ALPHA-M001",
            latitude = 32.3739,
            longitude = 77.2491,
            altitudeM = 3950.0,
            accuracyM = 8.5f,
            speedMps = 1.4f,
            headingDeg = 92.0f,
            timestamp = "2026-09-05T14:30:00Z",
            gpsAvailable = true,
            locationSource = "PHONE_GPS",
            gpsStatus = "TRACKING"
        )

        val jsonStr = req.toJsonString()
        val json = JSONObject(jsonStr)

        assertEquals("ALPHA-M001", json.getString("member_id"))
        assertTrue(json.getBoolean("gps_available"))
        assertEquals(32.3739, json.getDouble("latitude"), 0.0001)
        assertEquals(77.2491, json.getDouble("longitude"), 0.0001)
        assertEquals(3950.0, json.getDouble("altitude_m"), 0.01)
        assertEquals(8.5, json.getDouble("accuracy_m"), 0.01)
        assertEquals(1.4, json.getDouble("speed_mps"), 0.01)
        assertEquals(92.0, json.getDouble("heading_deg"), 0.01)
        assertEquals("2026-09-05T14:30:00Z", json.getString("timestamp"))
        assertEquals("TRACKING", json.getString("gps_status"))
        assertEquals("PHONE_GPS", json.getString("location_source"))
    }

    @Test
    fun testBridgeSyncRequest_nullCoordinatesWhenNotTracking() {
        val req = BridgeSyncRequest(
            sessionId = "TEST-SES-002",
            teamId = "ALPHA",
            memberId = "ALPHA-M001",
            latitude = null,
            longitude = null,
            gpsAvailable = false,
            gpsStatus = "STANDBY"
        )

        val jsonStr = req.toJsonString()
        val json = JSONObject(jsonStr)

        assertFalse(json.getBoolean("gps_available"))
        assertFalse(json.has("latitude"))
        assertFalse(json.has("longitude"))
        assertEquals("STANDBY", json.getString("gps_status"))
    }
}
