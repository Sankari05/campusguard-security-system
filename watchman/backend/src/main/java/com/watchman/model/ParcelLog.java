package com.watchman.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "parcel_logs")
public class ParcelLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 50)
    private String courierCompany;

    private String trackingNumber;

    @Column(nullable = false, length = 100)
    private String recipientName;

    @Column(nullable = false, length = 100)
    private String departmentOrHostel;

    private String recipientPhone;

    private LocalDateTime receivedAt = LocalDateTime.now();
    private LocalDateTime pickedUpAt;

    @Column(length = 30)
    private String status = "WAITING_COLLECTION"; // WAITING_COLLECTION, DELIVERED

    private String handoverOtp;
    private String receivedByWatchman;

    public ParcelLog() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getCourierCompany() { return courierCompany; }
    public void setCourierCompany(String courierCompany) { this.courierCompany = courierCompany; }

    public String getTrackingNumber() { return trackingNumber; }
    public void setTrackingNumber(String trackingNumber) { this.trackingNumber = trackingNumber; }

    public String getRecipientName() { return recipientName; }
    public void setRecipientName(String recipientName) { this.recipientName = recipientName; }

    public String getDepartmentOrHostel() { return departmentOrHostel; }
    public void setDepartmentOrHostel(String departmentOrHostel) { this.departmentOrHostel = departmentOrHostel; }

    public String getRecipientPhone() { return recipientPhone; }
    public void setRecipientPhone(String recipientPhone) { this.recipientPhone = recipientPhone; }

    public LocalDateTime getReceivedAt() { return receivedAt; }
    public void setReceivedAt(LocalDateTime receivedAt) { this.receivedAt = receivedAt; }

    public LocalDateTime getPickedUpAt() { return pickedUpAt; }
    public void setPickedUpAt(LocalDateTime pickedUpAt) { this.pickedUpAt = pickedUpAt; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getHandoverOtp() { return handoverOtp; }
    public void setHandoverOtp(String handoverOtp) { this.handoverOtp = handoverOtp; }

    public String getReceivedByWatchman() { return receivedByWatchman; }
    public void setReceivedByWatchman(String receivedByWatchman) { this.receivedByWatchman = receivedByWatchman; }
}
