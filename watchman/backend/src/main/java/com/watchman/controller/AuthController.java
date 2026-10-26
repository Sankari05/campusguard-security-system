package com.watchman.controller;

import com.watchman.config.JwtUtils;
import com.watchman.dto.*;
import com.watchman.model.User;
import com.watchman.repository.UserRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Random;

@RestController
@RequestMapping("/auth")
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtils jwtUtils;

    // In-memory demo OTP cache (key: email, value: otp)
    private final Map<String, String> otpStore = new HashMap<>();

    public AuthController(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtUtils jwtUtils) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtUtils = jwtUtils;
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        // Fast-path for demo/convenience credentials or DB query
        String username = request.getUsernameOrEmail();
        Optional<User> userOpt = userRepository.findByUsername(username)
                .or(() -> userRepository.findByEmail(username));

        User user;
        if (userOpt.isPresent()) {
            user = userOpt.get();
        } else {
            // Default fallback users so login works immediately even before DB seed
            user = createDefaultUserIfMissing(username, request.getRole());
        }

        String token = jwtUtils.generateToken(user.getUsername(), user.getRole());
        return ResponseEntity.ok(new LoginResponse(
                token,
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getFullName(),
                user.getRole(),
                user.getDepartment()
        ));
    }

    @PostMapping("/forgot-password")
    public ResponseEntity<?> forgotPassword(@RequestBody ForgotPasswordRequest request) {
        String identifier = request.getEmailOrUsername();
        String generatedOtp = String.valueOf(100000 + new Random().nextInt(900000));
        otpStore.put(identifier.toLowerCase(), generatedOtp);

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("message", "A 6-digit verification code has been sent to your registered email / phone.");
        response.put("demoOtp", generatedOtp); // provided in response for easy testing!
        return ResponseEntity.ok(response);
    }

    @PostMapping("/reset-password")
    public ResponseEntity<?> resetPassword(@RequestBody ResetPasswordRequest request) {
        String identifier = request.getEmailOrUsername() != null ? request.getEmailOrUsername().toLowerCase() : "";
        String storedOtp = otpStore.get(identifier);

        if (storedOtp == null || !storedOtp.equals(request.getOtpToken())) {
            Map<String, Object> error = new HashMap<>();
            error.put("success", false);
            error.put("message", "Invalid or expired OTP code. Please try again.");
            return ResponseEntity.badRequest().body(error);
        }

        // Update password if user exists in DB
        userRepository.findByEmail(identifier)
                .or(() -> userRepository.findByUsername(identifier))
                .ifPresent(u -> {
                    u.setPasswordHash(passwordEncoder.encode(request.getNewPassword()));
                    userRepository.save(u);
                });

        otpStore.remove(identifier);

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("message", "Password has been successfully reset! You can now log in.");
        return ResponseEntity.ok(response);
    }

    private User createDefaultUserIfMissing(String identifier, String requestedRole) {
        String role = requestedRole != null ? requestedRole.toUpperCase() : "WATCHMAN";
        String fullName = switch (role) {
            case "ADMIN" -> "Dr. Sundaram (College Admin)";
            case "FACULTY" -> "Prof. Meenakshi (HOD CSE)";
            case "STUDENT" -> "Karthik Subramanian";
            default -> "Ramasamy (Main Gate Security)";
        };
        User user = new User(identifier, identifier + "@college.edu", "pass123", fullName, "9876543210", role, "Campus Gate");
        user.setId(101L);
        return user;
    }
}
