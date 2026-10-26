package com.watchman.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "handover_tasks")
public class HandoverTask {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 50)
    private String taskCode; // e.g. TSK-VIS-501, TSK-PCL-301, TSK-EQP-001

    @Column(length = 40)
    private String handoverCode;

    // VISITORS, PARCELS, INCIDENTS, EQUIPMENT
    @Column(nullable = false, length = 30)
    private String category;

    @Column(nullable = false, length = 150)
    private String title;

    @Column(length = 500)
    private String description;

    @Column(length = 50)
    private String sourceReferenceId; // Pass #, Parcel Tracking #, or SOS Incident ID

    // OPEN, IN_PROGRESS, RESOLVED
    @Column(nullable = false, length = 20)
    private String status = "OPEN";

    // HIGH, MEDIUM, LOW
    @Column(nullable = false, length = 20)
    private String priority = "MEDIUM";

    private LocalDateTime createdAt = LocalDateTime.now();
    private LocalDateTime lastUpdatedAt = LocalDateTime.now();

    @Column(length = 255)
    private String nextRequiredAction;

    private String resolvedBy;
    private LocalDateTime resolvedAt;

    @Column(length = 500)
    private String resolutionNotes;

    public HandoverTask() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getTaskCode() { return taskCode; }
    public void setTaskCode(String taskCode) { this.taskCode = taskCode; }

    public String getHandoverCode() { return handoverCode; }
    public void setHandoverCode(String handoverCode) { this.handoverCode = handoverCode; }

    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getSourceReferenceId() { return sourceReferenceId; }
    public void setSourceReferenceId(String sourceReferenceId) { this.sourceReferenceId = sourceReferenceId; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getLastUpdatedAt() { return lastUpdatedAt; }
    public void setLastUpdatedAt(LocalDateTime lastUpdatedAt) { this.lastUpdatedAt = lastUpdatedAt; }

    public String getNextRequiredAction() { return nextRequiredAction; }
    public void setNextRequiredAction(String nextRequiredAction) { this.nextRequiredAction = nextRequiredAction; }

    public String getResolvedBy() { return resolvedBy; }
    public void setResolvedBy(String resolvedBy) { this.resolvedBy = resolvedBy; }

    public LocalDateTime getResolvedAt() { return resolvedAt; }
    public void setResolvedAt(LocalDateTime resolvedAt) { this.resolvedAt = resolvedAt; }

    public String getResolutionNotes() { return resolutionNotes; }
    public void setResolutionNotes(String resolutionNotes) { this.resolutionNotes = resolutionNotes; }
}
