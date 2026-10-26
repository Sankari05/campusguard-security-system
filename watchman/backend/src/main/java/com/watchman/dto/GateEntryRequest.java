package com.watchman.dto;

public class GateEntryRequest {
    private String personType; // STUDENT, VISITOR, FACULTY, DELIVERY, VEHICLE
    private String identifier; // Roll Number / Phone / Vehicle
    private String personName;
    private String purpose;
    private String direction; // 'IN' or 'OUT'
    private String gateNumber;
    private String remarks;

    public GateEntryRequest() {}

    public String getPersonType() { return personType; }
    public void setPersonType(String personType) { this.personType = personType; }

    public String getIdentifier() { return identifier; }
    public void setIdentifier(String identifier) { this.identifier = identifier; }

    public String getPersonName() { return personName; }
    public void setPersonName(String personName) { this.personName = personName; }

    public String getPurpose() { return purpose; }
    public void setPurpose(String purpose) { this.purpose = purpose; }

    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }

    public String getGateNumber() { return gateNumber; }
    public void setGateNumber(String gateNumber) { this.gateNumber = gateNumber; }

    public String getRemarks() { return remarks; }
    public void setRemarks(String remarks) { this.remarks = remarks; }
}
