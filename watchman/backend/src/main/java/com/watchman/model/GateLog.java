package com.watchman.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "gate_logs")
public class GateLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 20)
    private String personType; // STUDENT, VISITOR, FACULTY, DELIVERY, VEHICLE

    @Column(nullable = false, length = 100)
    private String identifier; // Roll Number / Phone / Vehicle

    @Column(nullable = false, length = 100)
    private String personName;

    private String purpose;

    private LocalDateTime entryTime = LocalDateTime.now();

    private LocalDateTime exitTime;

    @Column(nullable = false, length = 10)
    private String direction = "IN"; // 'IN' or 'OUT'

    private String gateNumber = "Main Gate 1";

    private Long watchmanId;

    @Column(length = 20)
    private String status = "APPROVED"; // APPROVED, LATE_ENTRY, FLAGGED

    @Column(columnDefinition = "TEXT")
    private String remarks;

    public GateLog() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getPersonType() { return personType; }
    public void setPersonType(String personType) { this.personType = personType; }

    public String getIdentifier() { return identifier; }
    public void setIdentifier(String identifier) { this.identifier = identifier; }

    public String getPersonName() { return personName; }
    public void setPersonName(String personName) { this.personName = personName; }

    public String getPurpose() { return purpose; }
    public void setPurpose(String purpose) { this.purpose = purpose; }

    public LocalDateTime getEntryTime() { return entryTime; }
    public void setEntryTime(LocalDateTime entryTime) { this.entryTime = entryTime; }

    public LocalDateTime getExitTime() { return exitTime; }
    public void setExitTime(LocalDateTime exitTime) { this.exitTime = exitTime; }

    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }

    public String getGateNumber() { return gateNumber; }
    public void setGateNumber(String gateNumber) { this.gateNumber = gateNumber; }

    public Long getWatchmanId() { return watchmanId; }
    public void setWatchmanId(Long watchmanId) { this.watchmanId = watchmanId; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getRemarks() { return remarks; }
    public void setRemarks(String remarks) { this.remarks = remarks; }
}
