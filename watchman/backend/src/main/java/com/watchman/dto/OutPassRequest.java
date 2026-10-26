package com.watchman.dto;

import java.time.LocalDateTime;

public class OutPassRequest {
    private String rollNumber;
    private String studentName;
    private String department;
    private String reason;
    private String destination;
    private LocalDateTime outTimeExpected;
    private LocalDateTime inTimeExpected;

    public OutPassRequest() {}

    public String getRollNumber() { return rollNumber; }
    public void setRollNumber(String rollNumber) { this.rollNumber = rollNumber; }

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
}
