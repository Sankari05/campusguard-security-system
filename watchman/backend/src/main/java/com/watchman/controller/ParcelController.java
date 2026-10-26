package com.watchman.controller;

import com.watchman.model.ParcelLog;
import com.watchman.repository.ParcelLogRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.Random;

@RestController
@RequestMapping("/parcels")
public class ParcelController {

    private final ParcelLogRepository parcelLogRepository;

    public ParcelController(ParcelLogRepository parcelLogRepository) {
        this.parcelLogRepository = parcelLogRepository;
    }

    @PostMapping("/receive")
    public ResponseEntity<ParcelLog> receiveParcel(@RequestBody ParcelLog log) {
        log.setReceivedAt(LocalDateTime.now());
        log.setStatus("WAITING_COLLECTION");
        log.setHandoverOtp(String.valueOf(1000 + new Random().nextInt(9000)));
        return ResponseEntity.ok(parcelLogRepository.save(log));
    }

    @GetMapping("/pending")
    public ResponseEntity<List<ParcelLog>> getPendingParcels() {
        return ResponseEntity.ok(parcelLogRepository.findByStatusOrderByReceivedAtDesc("WAITING_COLLECTION"));
    }

    @PutMapping("/{id}/handover")
    public ResponseEntity<?> handoverParcel(@PathVariable Long id, @RequestParam(required = false) String otp) {
        Optional<ParcelLog> logOpt = parcelLogRepository.findById(id);
        if (logOpt.isPresent()) {
            ParcelLog parcel = logOpt.get();
            parcel.setStatus("DELIVERED");
            parcel.setPickedUpAt(LocalDateTime.now());
            return ResponseEntity.ok(parcelLogRepository.save(parcel));
        }
        return ResponseEntity.notFound().build();
    }
}
