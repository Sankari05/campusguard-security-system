package com.watchman.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "out_passes")
public class OutPass {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false, length = 30)
    private String passCode;

    private Long studentId;
    private String studentRollNumber;
    private String studentName;
    private String department;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String reason;

    private String destination;

    private LocalDateTime outTimeExpected;
    private LocalDateTime inTimeExpected;

    @Column(nullable = false, length = 30)
    private String status = "PENDING"; // PENDING, APPROVED_BY_HOD, REJECTED, EXITED_GATE, COMPLETED

    private String approvedBy;
    private Boolean parentConsentVerified = false;

    private LocalDateTime actualOutTime;
    private LocalDateTime actualInTime;
    private LocalDateTime createdAt = LocalDateTime.now();

    public OutPass() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getPassCode() { return passCode; }
    public void setPassCode(String passCode) { this.passCode = passCode; }

    public Long getStudentId() { return studentId; }
    public void setStudentId(Long studentId) { this.studentId = studentId; }

    public String getStudentRollNumber() { return studentRollNumber; }
    public void setStudentRollNumber(String studentRollNumber) { this.studentRollNumber = studentRollNumber; }

    public String getStudentName() { return studentName; }
    public void setStudentName(String studentName) { this.studentName = studentName; }

    public String getDepartment() { return department; }
    public void setDepartment(String department) { this.department = department; }

    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }

    public String getDestination() { return destination; }
    public void setDestination(String destination) { this.destination = destination; }

    public LocalDateTime getOutTimeExpected() { return outTimeExpected; }
    public void setOutTimeExpected(LocalDateTime outTimeExpected) { this.outTimeExpected = outTimeExpected; }

    public LocalDateTime getInTimeExpected() { return inTimeExpected; }
    public void setInTimeExpected(LocalDateTime inTimeExpected) { this.inTimeExpected = inTimeExpected; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getApprovedBy() { return approvedBy; }
    public void setApprovedBy(String approvedBy) { this.approvedBy = approvedBy; }

    public Boolean getParentConsentVerified() { return parentConsentVerified; }
    public void setParentConsentVerified(Boolean parentConsentVerified) { this.parentConsentVerified = parentConsentVerified; }

    public LocalDateTime getActualOutTime() { return actualOutTime; }
    public void setActualOutTime(LocalDateTime actualOutTime) { this.actualOutTime = actualOutTime; }

    public LocalDateTime getActualInTime() { return actualInTime; }
    public void setActualInTime(LocalDateTime actualInTime) { this.actualInTime = actualInTime; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
