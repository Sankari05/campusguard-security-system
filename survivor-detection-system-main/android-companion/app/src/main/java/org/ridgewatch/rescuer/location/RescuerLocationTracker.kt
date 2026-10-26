package org.ridgewatch.rescuer.location

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * RidgeWatch Native Real GPS Tracking Module for Alpha Member 1.
 *
 * Strict Architectural Guarantees:
 * 1. Native Android Location APIs only (android.location.LocationManager).
 * 2. Zero Google Maps SDK, zero external GPS accounts/devices.
 * 3. Safe filtering (Null Island, bounds, accuracy threshold).
 * 4. Stale threshold monitoring (15 seconds) - preserves last fix, never fabricates synthetic movement.
 * 5. Lifecycle safe with leak-free listener detachment.
 */
class RescuerLocationTracker(
    private val context: Context,
    private val onLocationUpdate: ((GpsLocationData) -> Unit)? = null
) {

    companion object {
        private const val TAG = "RidgeWatchGps"
        const val GPS_STALE_THRESHOLD_SECONDS = 15L
        const val GPS_STALE_THRESHOLD_MS = GPS_STALE_THRESHOLD_SECONDS * 1000L
        const val UPDATE_INTERVAL_MS = 3000L
        const val MIN_DISTANCE_METERS = 1.0f
        const val MAX_ACCEPTABLE_ACCURACY_M = 1000.0f

        /**
         * Pure validation logic for coordinate bounds and realism.
         */
        fun isValidCoordinate(latitude: Double, longitude: Double): Boolean {
            if (latitude < -90.0 || latitude > 90.0) return false
            if (longitude < -180.0 || longitude > 180.0) return false
            // Null-Island rejection (0.0, 0.0 is an ocean artifact for missing GPS fixes)
            if (latitude == 0.0 && longitude == 0.0) return false
            return true
        }

        /**
         * Pure validation logic for GPS reading accuracy.
         */
        fun isAcceptableAccuracy(accuracyM: Float): Boolean {
            return accuracyM > 0.0f && accuracyM <= MAX_ACCEPTABLE_ACCURACY_M
        }

        /**
         * Formats epoch timestamp to ISO-8601 UTC string.
         */
        fun formatIso8601(epochMs: Long): String {
            val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
            sdf.timeZone = TimeZone.getTimeZone("UTC")
            return sdf.format(Date(epochMs))
        }
    }

    enum class GpsStatus {
        STANDBY,
        WAITING_FOR_PERMISSION,
        WAITING_FOR_GPS,
        TRACKING,
        STALE,
        GPS_UNAVAILABLE,
        PERMISSION_DENIED
    }

    data class GpsLocationData(
        val latitude: Double? = null,
        val longitude: Double? = null,
        val altitudeM: Double? = null,
        val accuracyM: Float? = null,
        val speedMps: Float? = null,
        val headingDeg: Float? = null,
        val timestamp: Long = 0L,
        val timestampIso: String? = null,
        val status: GpsStatus = GpsStatus.STANDBY,
        val updateCount: Int = 0,
        val locationSource: String = "PHONE_GPS",
        val lastFixTimestamp: Long = 0L
    )

    private val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
    private val trackerScope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    private val _locationState = MutableStateFlow(GpsLocationData())
    val locationState: StateFlow<GpsLocationData> = _locationState.asStateFlow()

    private var isTrackingRequested = false
    private var staleWatchdogJob: Job? = null
    private var internalUpdateCounter = 0

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            handleRawLocation(location)
        }

        @Deprecated("Deprecated in Java")
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {
            Log.d(TAG, "Provider status changed: $provider status=$status")
        }

        override fun onProviderEnabled(provider: String) {
            Log.i(TAG, "Location provider enabled: $provider")
            if (isTrackingRequested) {
                startTracking()
            }
        }

        override fun onProviderDisabled(provider: String) {
            Log.w(TAG, "Location provider disabled: $provider")
            if (isTrackingRequested && !hasAnyLocationProviderEnabled()) {
                _locationState.value = _locationState.value.copy(status = GpsStatus.GPS_UNAVAILABLE)
                onLocationUpdate?.invoke(_locationState.value)
            }
        }
    }

    /**
     * Verifies if location permissions are currently granted.
     */
    fun hasLocationPermission(): Boolean {
        val finePerm = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarsePerm = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        return finePerm || coarsePerm
    }

    /**
     * Checks if at least one location provider is enabled on device.
     */
    fun hasAnyLocationProviderEnabled(): Boolean {
        val mgr = locationManager ?: return false
        val gpsEnabled = mgr.isProviderEnabled(LocationManager.GPS_PROVIDER)
        val networkEnabled = mgr.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
        return gpsEnabled || networkEnabled
    }

    /**
     * Initiates real GPS tracking. Only called when Alpha Member 1 mission is ACCEPTED.
     */
    @Synchronized
    fun startTracking() {
        Log.i(TAG, "[REAL_GPS] startTracking() requested for Alpha Member 1")
        isTrackingRequested = true

        if (!hasLocationPermission()) {
            Log.w(TAG, "[REAL_GPS] Tracking aborted: Location permission missing")
            _locationState.value = _locationState.value.copy(status = GpsStatus.WAITING_FOR_PERMISSION)
            onLocationUpdate?.invoke(_locationState.value)
            return
        }

        if (locationManager == null || !hasAnyLocationProviderEnabled()) {
            Log.w(TAG, "[REAL_GPS] Tracking aborted: Location providers disabled on device")
            _locationState.value = _locationState.value.copy(status = GpsStatus.GPS_UNAVAILABLE)
            onLocationUpdate?.invoke(_locationState.value)
            return
        }

        _locationState.value = _locationState.value.copy(status = GpsStatus.WAITING_FOR_GPS)
        onLocationUpdate?.invoke(_locationState.value)

        try {
            // Unregister first to guarantee idempotency
            locationManager.removeUpdates(locationListener)

            // Register GPS Provider (primary)
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    UPDATE_INTERVAL_MS,
                    MIN_DISTANCE_METERS,
                    locationListener,
                    Looper.getMainLooper()
                )
            }

            // Register Network Provider (secondary fallback while GPS establishes fix)
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    UPDATE_INTERVAL_MS,
                    MIN_DISTANCE_METERS,
                    locationListener,
                    Looper.getMainLooper()
                )
            }

            // Check if there is a fresh last known location
            checkLastKnownLocation()

            // Start stale monitor watchdog
            startStaleWatchdog()

            Log.i(TAG, "[REAL_GPS] Native location listeners successfully registered (Interval: ${UPDATE_INTERVAL_MS}ms)")
        } catch (se: SecurityException) {
            Log.e(TAG, "[REAL_GPS] SecurityException registering location updates: ${se.message}", se)
            _locationState.value = _locationState.value.copy(status = GpsStatus.PERMISSION_DENIED)
            onLocationUpdate?.invoke(_locationState.value)
        } catch (e: Exception) {
            Log.e(TAG, "[REAL_GPS] Error registering location updates: ${e.message}", e)
            _locationState.value = _locationState.value.copy(status = GpsStatus.GPS_UNAVAILABLE)
            onLocationUpdate?.invoke(_locationState.value)
        }
    }

    /**
     * Halts GPS tracking and releases listeners to prevent resource leaks.
     */
    @Synchronized
    fun stopTracking() {
        Log.i(TAG, "[REAL_GPS] stopTracking() called. Releasing listeners.")
        isTrackingRequested = false
        staleWatchdogJob?.cancel()

        try {
            locationManager?.removeUpdates(locationListener)
        } catch (e: Exception) {
            Log.w(TAG, "Error detaching location listener: ${e.message}")
        }

        _locationState.value = _locationState.value.copy(status = GpsStatus.STANDBY)
        onLocationUpdate?.invoke(_locationState.value)
    }

    /**
     * Reports permission denied status without crashing.
     */
    fun onPermissionDenied() {
        Log.w(TAG, "[REAL_GPS] User denied location permission")
        _locationState.value = _locationState.value.copy(status = GpsStatus.PERMISSION_DENIED)
        onLocationUpdate?.invoke(_locationState.value)
    }

    /**
     * Processes raw Android Location reading with safety filtering.
     */
    private fun handleRawLocation(location: Location) {
        val lat = location.latitude
        val lon = location.longitude

        if (!isValidCoordinate(lat, lon)) {
            Log.w(TAG, "[REAL_GPS] Invalid coordinate rejected: lat=$lat lon=$lon")
            return
        }

        val accuracy = if (location.hasAccuracy()) location.accuracy else Float.MAX_VALUE
        if (!isAcceptableAccuracy(accuracy)) {
            Log.w(TAG, "[REAL_GPS] Poor accuracy reading rejected (${accuracy}m > ${MAX_ACCEPTABLE_ACCURACY_M}m)")
            // Retain last known fix, do not fabricate fake replacements
            return
        }

        val now = System.currentTimeMillis()
        val fixTime = if (location.time > 0L) location.time else now
        internalUpdateCounter++

        val newGpsData = GpsLocationData(
            latitude = lat,
            longitude = lon,
            altitudeM = if (location.hasAltitude()) location.altitude else null,
            accuracyM = accuracy,
            speedMps = if (location.hasSpeed()) location.speed else null,
            headingDeg = if (location.hasBearing()) location.bearing else null,
            timestamp = fixTime,
            timestampIso = formatIso8601(fixTime),
            status = GpsStatus.TRACKING,
            updateCount = internalUpdateCounter,
            locationSource = "PHONE_GPS",
            lastFixTimestamp = now
        )

        _locationState.value = newGpsData
        onLocationUpdate?.invoke(newGpsData)

        Log.d(TAG, "[REAL_GPS_SAMPLE] #$internalUpdateCounter lat=$lat lon=$lon acc=${accuracy}m status=TRACKING")
    }

    /**
     * Checks if a recent valid location is already available from system providers.
     */
    private fun checkLastKnownLocation() {
        if (!hasLocationPermission() || locationManager == null) return
        try {
            val lastGps = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            val lastNet = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)

            val candidate = when {
                lastGps != null && lastNet != null -> if (lastGps.time >= lastNet.time) lastGps else lastNet
                lastGps != null -> lastGps
                else -> lastNet
            }

            if (candidate != null) {
                val ageMs = System.currentTimeMillis() - candidate.time
                // Only use if reasonably recent (< 60 seconds)
                if (ageMs < 60_000L && isValidCoordinate(candidate.latitude, candidate.longitude) && candidate.accuracy <= MAX_ACCEPTABLE_ACCURACY_M) {
                    handleRawLocation(candidate)
                }
            }
        } catch (se: SecurityException) {
            Log.w(TAG, "SecurityException querying lastKnownLocation")
        } catch (e: Exception) {
            Log.w(TAG, "Error checking lastKnownLocation: ${e.message}")
        }
    }

    /**
     * Periodic watchdog checking if latest GPS sample exceeded the 15-second stale threshold.
     */
    private fun startStaleWatchdog() {
        staleWatchdogJob?.cancel()
        staleWatchdogJob = trackerScope.launch {
            while (isActive && isTrackingRequested) {
                delay(3000L)
                val current = _locationState.value
                if (current.status == GpsStatus.TRACKING && current.lastFixTimestamp > 0L) {
                    val elapsedMs = System.currentTimeMillis() - current.lastFixTimestamp
                    if (elapsedMs > GPS_STALE_THRESHOLD_MS) {
                        Log.w(TAG, "[REAL_GPS] GPS reading is STALE (${elapsedMs / 1000}s since last fix)")
                        val staleData = current.copy(status = GpsStatus.STALE)
                        _locationState.value = staleData
                        onLocationUpdate?.invoke(staleData)
                    }
                }
            }
        }
    }
}
