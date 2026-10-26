package com.watchman.controller;

import com.watchman.model.EmergencyAlert;
import com.watchman.repository.EmergencyAlertRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/emergency")
public class EmergencyController {

    private final EmergencyAlertRepository emergencyAlertRepository;

    public EmergencyController(EmergencyAlertRepository emergencyAlertRepository) {
        this.emergencyAlertRepository = emergencyAlertRepository;
    }

    @PostMapping("/trigger")
    public ResponseEntity<EmergencyAlert> triggerSos(@RequestBody EmergencyAlert alert) {
        alert.setTimestamp(LocalDateTime.now());
        alert.setStatus("ACTIVE");
        return ResponseEntity.ok(emergencyAlertRepository.save(alert));
    }

    @GetMapping("/list")
    public ResponseEntity<List<EmergencyAlert>> getAlerts() {
        return ResponseEntity.ok(emergencyAlertRepository.findByStatusOrderByTimestampDesc("ACTIVE"));
    }

    @PutMapping("/{id}/resolve")
    public ResponseEntity<?> resolveAlert(@PathVariable Long id) {
        Optional<EmergencyAlert> alertOpt = emergencyAlertRepository.findById(id);
        if (alertOpt.isPresent()) {
            EmergencyAlert alert = alertOpt.get();
            alert.setStatus("RESOLVED");
            return ResponseEntity.ok(emergencyAlertRepository.save(alert));
        }
        return ResponseEntity.notFound().build();
    }
}
