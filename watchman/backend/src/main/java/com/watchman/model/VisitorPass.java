package com.watchman.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "visitor_passes")
public class VisitorPass {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // STUDENT, STAFF, PARENT, OTHERS
    @Column(nullable = false, length = 30)
    private String visitorType = "STUDENT";

    @Column(nullable = false, length = 100)
    private String visitorName;

    // Student Roll Number, Staff ID, or Contact Number
    @Column(length = 50)
    private String identifier;

    @Column(length = 20)
    private String phoneNumber;

    @Column(length = 100)
    private String department;

    // Late Arrival Reason (Students) or Visit Purpose (Staff, Parent, Others)
    @Column(length = 255)
    private String reason;

    @Column(length = 255)
    private String additionalDetails;

    @Column(length = 100)
    private String personToMeet;

    @Column(unique = true, nullable = false, length = 40)
    private String passNumber;

    // Secure 6-digit OTP for Watchman verification
    @Column(length = 10)
    private String otp;

    private LocalDateTime createdAt = LocalDateTime.now();
    private LocalDateTime otpExpiresAt;
    private LocalDateTime otpVerifiedAt;
    private LocalDateTime checkInTime;
    private LocalDateTime checkOutTime;

    // PENDING_OTP, APPROVED (Checked In), CHECKED_OUT, EXPIRED
    @Column(length = 30)
    private String status = "PENDING_OTP";

    private String verifiedByWatchmanId;
    private String verifiedByWatchmanName;
    private String badgeNumber;
    private String vehicleNumber;

    public VisitorPass() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getVisitorType() { return visitorType; }
    public void setVisitorType(String visitorType) { this.visitorType = visitorType; }

    public String getVisitorName() { return visitorName; }
    public void setVisitorName(String visitorName) { this.visitorName = visitorName; }

    public String getIdentifier() { return identifier; }
    public void setIdentifier(String identifier) { this.identifier = identifier; }

    public String getPhoneNumber() { return phoneNumber; }
    public void setPhoneNumber(String phoneNumber) { this.phoneNumber = phoneNumber; }

    public String getDepartment() { return department; }
    public void setDepartment(String department) { this.department = department; }

    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }

    public String getAdditionalDetails() { return additionalDetails; }
    public void setAdditionalDetails(String additionalDetails) { this.additionalDetails = additionalDetails; }

    public String getPersonToMeet() { return personToMeet; }
    public void setPersonToMeet(String personToMeet) { this.personToMeet = personToMeet; }

    public String getPassNumber() { return passNumber; }
    public void setPassNumber(String passNumber) { this.passNumber = passNumber; }

    public String getOtp() { return otp; }
    public void setOtp(String otp) { this.otp = otp; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getOtpExpiresAt() { return otpExpiresAt; }
    public void setOtpExpiresAt(LocalDateTime otpExpiresAt) { this.otpExpiresAt = otpExpiresAt; }

    public LocalDateTime getOtpVerifiedAt() { return otpVerifiedAt; }
    public void setOtpVerifiedAt(LocalDateTime otpVerifiedAt) { this.otpVerifiedAt = otpVerifiedAt; }

    public LocalDateTime getCheckInTime() { return checkInTime; }
    public void setCheckInTime(LocalDateTime checkInTime) { this.checkInTime = checkInTime; }

    public LocalDateTime getCheckOutTime() { return checkOutTime; }
    public void setCheckOutTime(LocalDateTime checkOutTime) { this.checkOutTime = checkOutTime; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getVerifiedByWatchmanId() { return verifiedByWatchmanId; }
    public void setVerifiedByWatchmanId(String verifiedByWatchmanId) { this.verifiedByWatchmanId = verifiedByWatchmanId; }

    public String getVerifiedByWatchmanName() { return verifiedByWatchmanName; }
    public void setVerifiedByWatchmanName(String verifiedByWatchmanName) { this.verifiedByWatchmanName = verifiedByWatchmanName; }

    public String getBadgeNumber() { return badgeNumber; }
    public void setBadgeNumber(String badgeNumber) { this.badgeNumber = badgeNumber; }

    public String getVehicleNumber() { return vehicleNumber; }
    public void setVehicleNumber(String vehicleNumber) { this.vehicleNumber = vehicleNumber; }
}
