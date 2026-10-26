package com.watchman.controller;

import com.watchman.model.VisitorPass;
import com.watchman.repository.VisitorPassRepository;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.*;

@RestController
@RequestMapping("/visitors")
@CrossOrigin(origins = "*")
public class VisitorController {

    private final VisitorPassRepository visitorPassRepository;

    public VisitorController(VisitorPassRepository visitorPassRepository) {
        this.visitorPassRepository = visitorPassRepository;
    }

    /**
     * STEP 1-4: Public Self-Registration for Students, Staff, Parents, and Visitors
     * Accessible via QR code scan on mobile camera.
     * Generates a unique Gate Pass Number & 6-digit verification OTP with 15m expiry.
     */
    @PostMapping("/self-register")
    public ResponseEntity<?> selfRegister(@RequestBody VisitorPass request) {
        if (request.getVisitorName() == null || request.getVisitorName().trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Name is mandatory."));
        }

        // Generate unique pass number
        String passNum = "GP-2026-" + (1000 + new Random().nextInt(9000));
        // Generate secure 6-digit numeric OTP
        String otp = String.format("%06d", new Random().nextInt(1000000));

        request.setPassNumber(passNum);
        request.setOtp(otp);
        request.setCreatedAt(LocalDateTime.now());
        // OTP valid for 15 minutes
        request.setOtpExpiresAt(LocalDateTime.now().plusMinutes(15));
        request.setStatus("PENDING_OTP");

        VisitorPass saved = visitorPassRepository.save(request);

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("message", "Digital Gate Pass generated successfully!");
        response.put("passNumber", saved.getPassNumber());
        response.put("otp", saved.getOtp());
        response.put("expiresAt", saved.getOtpExpiresAt());
        response.put("visitorPass", saved);

        return ResponseEntity.ok(response);
    }

    /**
     * STEP 6-7: Watchman OTP Verification
     * Watchman enters ONLY the 6-digit OTP shown by student/visitor.
     * Validates:
     * 1. Correct OTP -> retrieves details
     * 2. Wrong OTP -> rejected
     * 3. Expired OTP -> rejected
     * 4. Already used OTP -> rejected
     */
    @PostMapping("/verify-otp")
    public ResponseEntity<?> verifyOtp(@RequestBody Map<String, String> payload) {
        String inputOtp = payload.get("otp");
        if (inputOtp == null || inputOtp.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Please enter the 6-digit OTP."));
        }

        Optional<VisitorPass> passOpt = visitorPassRepository.findByOtp(inputOtp.trim());
        if (passOpt.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of(
                "success", false,
                "error", "Invalid OTP. No visitor pass found with this code."
            ));
        }

        VisitorPass pass = passOpt.get();

        // Check if already used
        if ("APPROVED".equalsIgnoreCase(pass.getStatus()) || "CHECKED_OUT".equalsIgnoreCase(pass.getStatus())) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                "success", false,
                "error", "This OTP has already been verified and used at " +
                         (pass.getCheckInTime() != null ? pass.getCheckInTime() : "earlier") +
                         (pass.getVerifiedByWatchmanName() != null ? " by " + pass.getVerifiedByWatchmanName() : "") + "."
            ));
        }

        // Check if expired
        if (pass.getOtpExpiresAt() != null && LocalDateTime.now().isAfter(pass.getOtpExpiresAt())) {
            pass.setStatus("EXPIRED");
            visitorPassRepository.save(pass);
            return ResponseEntity.status(HttpStatus.GONE).body(Map.of(
                "success", false,
                "error", "This Gate Pass OTP has expired (15-minute time limit). Please ask visitor to re-scan QR."
            ));
        }

        // Valid OTP -> Return full visitor details for watchman screen display
        return ResponseEntity.ok(Map.of(
            "success", true,
            "message", "OTP Verified Successfully!",
            "visitorPass", pass
        ));
    }

    /**
     * STEP 7: Watchman Confirms Entry & Opens Gate
     * Logs exact check-in time, date, and Watchman ID permanently.
     */
    @PostMapping("/{id}/confirm-entry")
    public ResponseEntity<?> confirmEntry(@PathVariable Long id, @RequestBody Map<String, String> payload) {
        Optional<VisitorPass> passOpt = visitorPassRepository.findById(id);
        if (passOpt.isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        VisitorPass pass = passOpt.get();
        pass.setStatus("APPROVED");
        pass.setCheckInTime(LocalDateTime.now());
        pass.setOtpVerifiedAt(LocalDateTime.now());
        pass.setVerifiedByWatchmanId(payload.getOrDefault("watchmanId", "WM-01"));
        pass.setVerifiedByWatchmanName(payload.getOrDefault("watchmanName", "Ramasamy (Main Gate Security)"));
        if (payload.containsKey("badgeNumber")) {
            pass.setBadgeNumber(payload.get("badgeNumber"));
        }

        VisitorPass saved = visitorPassRepository.save(pass);
        return ResponseEntity.ok(Map.of(
            "success", true,
            "message", "Gate Entry Confirmed & Barrier Opened!",
            "visitorPass", saved
        ));
    }

    /**
     * Get all currently active visitors inside campus
     */
    @GetMapping("/active")
    public ResponseEntity<List<VisitorPass>> getActiveVisitors() {
        return ResponseEntity.ok(visitorPassRepository.findByStatusOrderByCheckInTimeDesc("APPROVED"));
    }

    /**
     * Checkout visitor
     */
    @PutMapping("/{id}/checkout")
    public ResponseEntity<?> checkOutVisitor(@PathVariable Long id) {
        Optional<VisitorPass> passOpt = visitorPassRepository.findById(id);
        if (passOpt.isPresent()) {
            VisitorPass pass = passOpt.get();
            pass.setStatus("CHECKED_OUT");
            pass.setCheckOutTime(LocalDateTime.now());
            return ResponseEntity.ok(visitorPassRepository.save(pass));
        }
        return ResponseEntity.notFound().build();
    }
}
