package com.watchman.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "shift_handovers")
public class ShiftHandover {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false, length = 40)
    private String handoverCode;

    @Column(nullable = false, length = 60)
    private String shiftName; // Morning Shift (06:00 AM - 02:00 PM), Evening Shift (02:00 PM - 10:00 PM), Night Shift (10:00 PM - 06:00 AM)

    @Column(length = 50)
    private String gateLocation = "Main Gate 1";

    @Column(nullable = false, length = 50)
    private String outgoingWatchmanId;

    @Column(nullable = false, length = 100)
    private String outgoingWatchmanName;

    @Column(nullable = false, length = 50)
    private String incomingWatchmanId;

    @Column(nullable = false, length = 100)
    private String incomingWatchmanName;

    private LocalDateTime handoverTime = LocalDateTime.now();

    @Column(length = 1000)
    private String handoverNotes;

    // PENDING_ACKNOWLEDGEMENT, ACKNOWLEDGED, COMPLETED, SUPERVISOR_REVIEWED
    @Column(nullable = false, length = 40)
    private String status = "PENDING_ACKNOWLEDGEMENT";

    private LocalDateTime acknowledgedAt;

    private String acknowledgedByWatchmanId;
    private String acknowledgedByWatchmanName;

    private String supervisorSignedBy;
    private LocalDateTime supervisorSignedAt;

    @Column(length = 500)
    private String supervisorNotes;

    private Integer totalPendingTasks = 0;
    private Integer unresolvedTasksCount = 0;

    public ShiftHandover() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getHandoverCode() { return handoverCode; }
    public void setHandoverCode(String handoverCode) { this.handoverCode = handoverCode; }

    public String getShiftName() { return shiftName; }
    public void setShiftName(String shiftName) { this.shiftName = shiftName; }

    public String getGateLocation() { return gateLocation; }
    public void setGateLocation(String gateLocation) { this.gateLocation = gateLocation; }

    public String getOutgoingWatchmanId() { return outgoingWatchmanId; }
    public void setOutgoingWatchmanId(String outgoingWatchmanId) { this.outgoingWatchmanId = outgoingWatchmanId; }

    public String getOutgoingWatchmanName() { return outgoingWatchmanName; }
    public void setOutgoingWatchmanName(String outgoingWatchmanName) { this.outgoingWatchmanName = outgoingWatchmanName; }

    public String getIncomingWatchmanId() { return incomingWatchmanId; }
    public void setIncomingWatchmanId(String incomingWatchmanId) { this.incomingWatchmanId = incomingWatchmanId; }

    public String getIncomingWatchmanName() { return incomingWatchmanName; }
    public void setIncomingWatchmanName(String incomingWatchmanName) { this.incomingWatchmanName = incomingWatchmanName; }

    public LocalDateTime getHandoverTime() { return handoverTime; }
    public void setHandoverTime(LocalDateTime handoverTime) { this.handoverTime = handoverTime; }

    public String getHandoverNotes() { return handoverNotes; }
    public void setHandoverNotes(String handoverNotes) { this.handoverNotes = handoverNotes; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public LocalDateTime getAcknowledgedAt() { return acknowledgedAt; }
    public void setAcknowledgedAt(LocalDateTime acknowledgedAt) { this.acknowledgedAt = acknowledgedAt; }

    public String getAcknowledgedByWatchmanId() { return acknowledgedByWatchmanId; }
    public void setAcknowledgedByWatchmanId(String acknowledgedByWatchmanId) { this.acknowledgedByWatchmanId = acknowledgedByWatchmanId; }

    public String getAcknowledgedByWatchmanName() { return acknowledgedByWatchmanName; }
    public void setAcknowledgedByWatchmanName(String acknowledgedByWatchmanName) { this.acknowledgedByWatchmanName = acknowledgedByWatchmanName; }

    public String getSupervisorSignedBy() { return supervisorSignedBy; }
    public void setSupervisorSignedBy(String supervisorSignedBy) { this.supervisorSignedBy = supervisorSignedBy; }

    public LocalDateTime getSupervisorSignedAt() { return supervisorSignedAt; }
    public void setSupervisorSignedAt(LocalDateTime supervisorSignedAt) { this.supervisorSignedAt = supervisorSignedAt; }

    public String getSupervisorNotes() { return supervisorNotes; }
    public void setSupervisorNotes(String supervisorNotes) { this.supervisorNotes = supervisorNotes; }

    public Integer getTotalPendingTasks() { return totalPendingTasks; }
    public void setTotalPendingTasks(Integer totalPendingTasks) { this.totalPendingTasks = totalPendingTasks; }

    public Integer getUnresolvedTasksCount() { return unresolvedTasksCount; }
    public void setUnresolvedTasksCount(Integer unresolvedTasksCount) { this.unresolvedTasksCount = unresolvedTasksCount; }
}
