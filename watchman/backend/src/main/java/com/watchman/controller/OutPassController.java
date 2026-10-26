package com.watchman.controller;

import com.watchman.dto.OutPassRequest;
import com.watchman.model.OutPass;
import com.watchman.repository.OutPassRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Random;

@RestController
@RequestMapping("/outpass")
public class OutPassController {

    private final OutPassRepository outPassRepository;

    public OutPassController(OutPassRepository outPassRepository) {
        this.outPassRepository = outPassRepository;
    }

    @PostMapping("/apply")
    public ResponseEntity<?> applyOutPass(@RequestBody OutPassRequest request) {
        OutPass outPass = new OutPass();
        String passCode = "OP-" + (1000 + new Random().nextInt(9000));
        outPass.setPassCode(passCode);
        outPass.setStudentRollNumber(request.getRollNumber());
        outPass.setStudentName(request.getStudentName());
        outPass.setDepartment(request.getDepartment());
        outPass.setReason(request.getReason());
        outPass.setDestination(request.getDestination());
        outPass.setOutTimeExpected(request.getOutTimeExpected() != null ? request.getOutTimeExpected() : LocalDateTime.now().plusHours(1));
        outPass.setInTimeExpected(request.getInTimeExpected() != null ? request.getInTimeExpected() : LocalDateTime.now().plusHours(6));
        outPass.setStatus("PENDING");
        outPass.setParentConsentVerified(true);

        OutPass saved = outPassRepository.save(outPass);
        return ResponseEntity.ok(saved);
    }

    @GetMapping("/list")
    public ResponseEntity<List<OutPass>> getAllOutPasses(@RequestParam(required = false) String status) {
        if (status != null && !status.isEmpty()) {
            return ResponseEntity.ok(outPassRepository.findByStatusOrderByCreatedAtDesc(status));
        }
        return ResponseEntity.ok(outPassRepository.findAll());
    }

    @PutMapping("/{id}/approve")
    public ResponseEntity<?> approveOutPass(@PathVariable Long id, @RequestParam(defaultValue = "HOD CSE") String approvedBy) {
        Optional<OutPass> outPassOpt = outPassRepository.findById(id);
        if (outPassOpt.isPresent()) {
            OutPass p = outPassOpt.get();
            p.setStatus("APPROVED_BY_HOD");
            p.setApprovedBy(approvedBy);
            return ResponseEntity.ok(outPassRepository.save(p));
        }
        return ResponseEntity.notFound().build();
    }

    @PostMapping("/verify-code/{code}")
    public ResponseEntity<?> verifyCodeAtGate(@PathVariable String code) {
        Optional<OutPass> outPassOpt = outPassRepository.findByPassCode(code.toUpperCase());
        if (outPassOpt.isPresent()) {
            OutPass pass = outPassOpt.get();
            if ("APPROVED_BY_HOD".equals(pass.getStatus())) {
                pass.setStatus("EXITED_GATE");
                pass.setActualOutTime(LocalDateTime.now());
                outPassRepository.save(pass);
                Map<String, Object> res = new HashMap<>();
                res.put("valid", true);
                res.put("message", "Pass verified! Gate Opened for " + pass.getStudentName());
                res.put("pass", pass);
                return ResponseEntity.ok(res);
            }
        }
        Map<String, Object> res = new HashMap<>();
        res.put("valid", false);
        res.put("message", "Invalid Pass Code or not yet approved by Faculty/Warden.");
        return ResponseEntity.badRequest().body(res);
    }
}
