package com.watchman.controller;

import com.watchman.model.HandoverTask;
import com.watchman.model.ShiftHandover;
import com.watchman.repository.HandoverTaskRepository;
import com.watchman.repository.ShiftHandoverRepository;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.*;

@RestController
@RequestMapping("/handovers")
@CrossOrigin(origins = "*")
public class ShiftHandoverController {

    private final ShiftHandoverRepository shiftHandoverRepository;
    private final HandoverTaskRepository handoverTaskRepository;

    public ShiftHandoverController(ShiftHandoverRepository shiftHandoverRepository, HandoverTaskRepository handoverTaskRepository) {
        this.shiftHandoverRepository = shiftHandoverRepository;
        this.handoverTaskRepository = handoverTaskRepository;
    }

    /**
     * Get all shift handovers (Supervisor / Audit view)
     */
    @GetMapping("/list")
    public ResponseEntity<List<ShiftHandover>> getAllHandovers() {
        return ResponseEntity.ok(shiftHandoverRepository.findAllByOrderByHandoverTimeDesc());
    }

    /**
     * Get the latest/current shift handover
     */
    @GetMapping("/current")
    public ResponseEntity<?> getCurrentHandover() {
        List<ShiftHandover> list = shiftHandoverRepository.findAllByOrderByHandoverTimeDesc();
        if (list.isEmpty()) {
            return ResponseEntity.ok(Map.of("hasActiveHandover", false));
        }
        ShiftHandover latest = list.get(0);
        List<HandoverTask> tasks = handoverTaskRepository.findByHandoverCode(latest.getHandoverCode());
        return ResponseEntity.ok(Map.of(
            "hasActiveHandover", true,
            "handover", latest,
            "tasks", tasks
        ));
    }

    /**
     * Get all unresolved tasks across shifts (Feature D: Task Continuity)
     */
    @GetMapping("/unresolved-tasks")
    public ResponseEntity<List<HandoverTask>> getUnresolvedTasks() {
        return ResponseEntity.ok(handoverTaskRepository.findByStatusNotOrderByCreatedAtDesc("RESOLVED"));
    }

    /**
     * Feature B: Create Shift Handover (Outgoing Watchman)
     */
    @PostMapping("/create")
    public ResponseEntity<?> createHandover(@RequestBody Map<String, Object> payload) {
        String shiftName = (String) payload.getOrDefault("shiftName", "Morning Shift (06:00 AM - 02:00 PM)");
        String outgoingId = (String) payload.getOrDefault("outgoingWatchmanId", "WM-01");
        String outgoingName = (String) payload.getOrDefault("outgoingWatchmanName", "Ramasamy (Main Gate Security)");
        String incomingId = (String) payload.getOrDefault("incomingWatchmanId", "WM-02");
        String incomingName = (String) payload.getOrDefault("incomingWatchmanName", "Murugan (Gate Guard - Shift B)");
        String notes = (String) payload.getOrDefault("handoverNotes", "");

        // Prevent duplicate pending submission for same outgoing shift within active window
        List<ShiftHandover> pendingList = shiftHandoverRepository.findByStatusOrderByHandoverTimeDesc("PENDING_ACKNOWLEDGEMENT");
        if (!pendingList.isEmpty()) {
            ShiftHandover existing = pendingList.get(0);
            if (existing.getOutgoingWatchmanId().equals(outgoingId)) {
                return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                    "error", "A pending handover for this shift already exists (" + existing.getHandoverCode() + "). Please have the incoming guard acknowledge it or update the existing one."
                ));
            }
        }

        String handoverCode = "HO-2026-" + (1000 + new Random().nextInt(9000));

        ShiftHandover handover = new ShiftHandover();
        handover.setHandoverCode(handoverCode);
        handover.setShiftName(shiftName);
        handover.setGateLocation("Main Gate 1");
        handover.setOutgoingWatchmanId(outgoingId);
        handover.setOutgoingWatchmanName(outgoingName);
        handover.setIncomingWatchmanId(incomingId);
        handover.setIncomingWatchmanName(incomingName);
        handover.setHandoverTime(LocalDateTime.now());
        handover.setHandoverNotes(notes);
        handover.setStatus("PENDING_ACKNOWLEDGEMENT");

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> taskList = (List<Map<String, Object>>) payload.get("tasks");
        int count = 0;
        int unresolved = 0;

        if (taskList != null) {
            for (Map<String, Object> tMap : taskList) {
                HandoverTask task = new HandoverTask();
                String tCode = (String) tMap.getOrDefault("taskCode", "TSK-" + (100 + new Random().nextInt(900)));
                task.setTaskCode(tCode);
                task.setHandoverCode(handoverCode);
                task.setCategory((String) tMap.getOrDefault("category", "EQUIPMENT"));
                task.setTitle((String) tMap.getOrDefault("title", "Task Title"));
                task.setDescription((String) tMap.getOrDefault("description", ""));
                task.setSourceReferenceId((String) tMap.getOrDefault("sourceReferenceId", ""));
                String status = (String) tMap.getOrDefault("status", "OPEN");
                task.setStatus(status);
                task.setPriority((String) tMap.getOrDefault("priority", "MEDIUM"));
                task.setNextRequiredAction((String) tMap.getOrDefault("nextRequiredAction", ""));
                task.setCreatedAt(LocalDateTime.now());
                task.setLastUpdatedAt(LocalDateTime.now());

                handoverTaskRepository.save(task);
                count++;
                if (!"RESOLVED".equalsIgnoreCase(status)) {
                    unresolved++;
                }
            }
        }

        handover.setTotalPendingTasks(count);
        handover.setUnresolvedTasksCount(unresolved);
        ShiftHandover saved = shiftHandoverRepository.save(handover);

        return ResponseEntity.ok(Map.of(
            "success", true,
            "message", "Shift Handover created successfully. Awaiting acknowledgement from incoming guard.",
            "handover", saved
        ));
    }

    /**
     * Feature C: Acknowledge Handover (Incoming Watchman)
     * Does NOT mark tasks as resolved!
     */
    @PostMapping("/{id}/acknowledge")
    public ResponseEntity<?> acknowledgeHandover(@PathVariable Long id, @RequestBody Map<String, String> payload) {
        Optional<ShiftHandover> opt = shiftHandoverRepository.findById(id);
        if (opt.isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        ShiftHandover handover = opt.get();
        handover.setStatus("ACKNOWLEDGED");
        handover.setAcknowledgedAt(LocalDateTime.now());
        handover.setAcknowledgedByWatchmanId(payload.getOrDefault("watchmanId", "WM-02"));
        handover.setAcknowledgedByWatchmanName(payload.getOrDefault("watchmanName", "Murugan (Gate Guard - Shift B)"));

        ShiftHandover saved = shiftHandoverRepository.save(handover);
        return ResponseEntity.ok(Map.of(
            "success", true,
            "message", "Handover acknowledged! Shift transfer complete. All unresolved tasks remain active.",
            "handover", saved
        ));
    }

    /**
     * Feature D: Update Task Status with History & Audit
     */
    @PutMapping("/tasks/{taskCode}/status")
    public ResponseEntity<?> updateTaskStatus(@PathVariable String taskCode, @RequestBody Map<String, String> payload) {
        Optional<HandoverTask> opt = handoverTaskRepository.findByTaskCode(taskCode);
        if (opt.isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        HandoverTask task = opt.get();
        String newStatus = payload.getOrDefault("status", "RESOLVED");
        String resolvedBy = payload.getOrDefault("resolvedBy", "Guard on Duty");
        String notes = payload.getOrDefault("notes", "Task resolved.");

        task.setStatus(newStatus);
        task.setLastUpdatedAt(LocalDateTime.now());
        if ("RESOLVED".equalsIgnoreCase(newStatus)) {
            task.setResolvedBy(resolvedBy);
            task.setResolvedAt(LocalDateTime.now());
            task.setResolutionNotes(notes);
        }

        HandoverTask saved = handoverTaskRepository.save(task);
        return ResponseEntity.ok(Map.of(
            "success", true,
            "task", saved
        ));
    }

    /**
     * Feature E: Supervisor Sign-off
     */
    @PostMapping("/{id}/supervisor-signoff")
    public ResponseEntity<?> supervisorSignOff(@PathVariable Long id, @RequestBody Map<String, String> payload) {
        Optional<ShiftHandover> opt = shiftHandoverRepository.findById(id);
        if (opt.isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        ShiftHandover handover = opt.get();
        handover.setSupervisorSignedBy(payload.getOrDefault("supervisorName", "Dr. Sundaram (Chief Security Officer)"));
        handover.setSupervisorSignedAt(LocalDateTime.now());
        handover.setSupervisorNotes(payload.getOrDefault("supervisorNotes", "Handover verified & approved."));
        handover.setStatus("SUPERVISOR_REVIEWED");

        return ResponseEntity.ok(Map.of(
            "success", true,
            "message", "Supervisor sign-off recorded.",
            "handover", shiftHandoverRepository.save(handover)
        ));
    }
}
