package com.watchman.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "students")
public class Student {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false, length = 30)
    private String rollNumber;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(nullable = false, length = 50)
    private String department;

    private Integer yearOfStudy;

    @Column(nullable = false, length = 20)
    private String hostelOrDayScholar; // 'HOSTEL', 'DAY_SCHOLAR'

    @Column(length = 50)
    private String roomOrBusRoute;

    @Column(nullable = false, length = 20)
    private String parentPhone;

    private String photoUrl;
    private Boolean isSuspended = false;
    private LocalDateTime createdAt = LocalDateTime.now();

    public Student() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getRollNumber() { return rollNumber; }
    public void setRollNumber(String rollNumber) { this.rollNumber = rollNumber; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDepartment() { return department; }
    public void setDepartment(String department) { this.department = department; }

    public Integer getYearOfStudy() { return yearOfStudy; }
    public void setYearOfStudy(Integer yearOfStudy) { this.yearOfStudy = yearOfStudy; }

    public String getHostelOrDayScholar() { return hostelOrDayScholar; }
    public void setHostelOrDayScholar(String hostelOrDayScholar) { this.hostelOrDayScholar = hostelOrDayScholar; }

    public String getRoomOrBusRoute() { return roomOrBusRoute; }
    public void setRoomOrBusRoute(String roomOrBusRoute) { this.roomOrBusRoute = roomOrBusRoute; }

    public String getParentPhone() { return parentPhone; }
    public void setParentPhone(String parentPhone) { this.parentPhone = parentPhone; }

    public String getPhotoUrl() { return photoUrl; }
    public void setPhotoUrl(String photoUrl) { this.photoUrl = photoUrl; }

    public Boolean getIsSuspended() { return isSuspended; }
    public void setIsSuspended(Boolean suspended) { isSuspended = suspended; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
