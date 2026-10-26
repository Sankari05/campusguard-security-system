-- ============================================================
-- CAMPUSGUARD - POSTGRESQL DATABASE SCHEMA (psql)
-- Supports College Gatekeeper, Students, Visitors, Staff & Admin
-- Multi-situation ready (Can be extended to Apartments / Offices)
-- ============================================================

-- Create Database (Run if not exists):
-- CREATE DATABASE campusguard_db;

-- Users table (Watchman, Admin, Faculty/HOD, Student)
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    role VARCHAR(30) NOT NULL, -- 'WATCHMAN', 'ADMIN', 'FACULTY', 'STUDENT'
    department VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Password Reset OTP tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    token_otp VARCHAR(10) NOT NULL,
    expiry_time TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Students Master Table
CREATE TABLE IF NOT EXISTS students (
    id BIGSERIAL PRIMARY KEY,
    roll_number VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL,
    year_of_study INT NOT NULL,
    hostel_or_day_scholar VARCHAR(20) NOT NULL, -- 'HOSTEL', 'DAY_SCHOLAR'
    room_or_bus_route VARCHAR(50),
    parent_phone VARCHAR(20) NOT NULL,
    photo_url VARCHAR(255),
    is_suspended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gate Logs (Live In & Out entries by Watchman)
CREATE TABLE IF NOT EXISTS gate_logs (
    id BIGSERIAL PRIMARY KEY,
    person_type VARCHAR(20) NOT NULL, -- 'STUDENT', 'VISITOR', 'FACULTY', 'DELIVERY', 'VEHICLE'
    identifier VARCHAR(100) NOT NULL, -- Roll Number / Name / Vehicle Number
    person_name VARCHAR(100) NOT NULL,
    purpose VARCHAR(255),
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP,
    direction VARCHAR(10) NOT NULL, -- 'IN' or 'OUT'
    gate_number VARCHAR(20) DEFAULT 'Main Gate',
    watchman_id BIGINT REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'APPROVED', -- 'APPROVED', 'LATE_ENTRY', 'FLAGGED'
    remarks TEXT
);

-- Student Out-Passes (HOD / Warden Approval system)
CREATE TABLE IF NOT EXISTS out_passes (
    id BIGSERIAL PRIMARY KEY,
    pass_code VARCHAR(30) UNIQUE NOT NULL,
    student_id BIGINT REFERENCES students(id),
    reason TEXT NOT NULL,
    destination VARCHAR(150),
    out_time_expected TIMESTAMP NOT NULL,
    in_time_expected TIMESTAMP NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING', -- 'PENDING', 'APPROVED_BY_HOD', 'REJECTED', 'EXITED_GATE', 'COMPLETED'
    approved_by VARCHAR(100),
    parent_consent_verified BOOLEAN DEFAULT FALSE,
    actual_out_time TIMESTAMP,
    actual_in_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Visitors & Parents Passes
CREATE TABLE IF NOT EXISTS visitor_passes (
    id BIGSERIAL PRIMARY KEY,
    visitor_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    purpose VARCHAR(100) NOT NULL, -- 'PARENTS_VISIT', 'FEE_PAYMENT', 'INTERVIEW', 'VENDOR', 'COURIER'
    person_to_meet VARCHAR(100) NOT NULL,
    department_to_visit VARCHAR(50),
    id_proof_type VARCHAR(30), -- 'AADHAAR', 'DRIVING_LICENCE', 'COLLEGE_ID'
    id_proof_number VARCHAR(50),
    pass_number VARCHAR(30) UNIQUE NOT NULL,
    check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    check_out_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ACTIVE', -- 'ACTIVE', 'CHECKED_OUT'
    badge_number VARCHAR(20),
    vehicle_number VARCHAR(30)
);

-- Main Gate Deliveries & Lab Parcels (Watchman parcel tracker)
CREATE TABLE IF NOT EXISTS parcel_logs (
    id BIGSERIAL PRIMARY KEY,
    courier_company VARCHAR(50) NOT NULL, -- 'AMAZON', 'FLIPKART', 'BLUEDART', 'LAB_EQUIPMENT'
    tracking_number VARCHAR(100),
    recipient_name VARCHAR(100) NOT NULL,
    department_or_hostel VARCHAR(100) NOT NULL,
    recipient_phone VARCHAR(20),
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    picked_up_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'WAITING_COLLECTION', -- 'WAITING_COLLECTION', 'DELIVERED'
    handover_otp VARCHAR(6),
    received_by_watchman VARCHAR(100)
);

-- Emergency Gate Alerts & SOS
CREATE TABLE IF NOT EXISTS emergency_alerts (
    id BIGSERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL, -- 'UNAUTHORIZED_ENTRY', 'MEDICAL_EMERGENCY', 'FIRE', 'STUDENT_ALTERCATION'
    location VARCHAR(100) NOT NULL,
    description TEXT,
    reported_by VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ACTIVE' -- 'ACTIVE', 'RESOLVED'
);

-- ============================================================
-- INITIAL SEED DATA (For Immediate Testing)
-- ============================================================

INSERT INTO users (username, email, password_hash, full_name, phone_number, role, department)
VALUES 
('watchman1', 'gate1@college.edu', '$2a$10$w8T0s0L1qN9rM4s1iV8mO.7hY0Q/kH8a9K2y6w2R7xV7T7W7g6', 'Ramasamy (Main Gate Security)', '9876543210', 'WATCHMAN', 'Security Department'),
('admin', 'principal@college.edu', '$2a$10$w8T0s0L1qN9rM4s1iV8mO.7hY0Q/kH8a9K2y6w2R7xV7T7W7g6', 'Dr. Sundaram (College Admin)', '9876500001', 'ADMIN', 'Management'),
('hod_cse', 'hod.cse@college.edu', '$2a$10$w8T0s0L1qN9rM4s1iV8mO.7hY0Q/kH8a9K2y6w2R7xV7T7W7g6', 'Prof. Meenakshi (HOD CSE)', '9876500002', 'FACULTY', 'Computer Science'),
('student1', 'karthik.22cs@college.edu', '$2a$10$w8T0s0L1qN9rM4s1iV8mO.7hY0Q/kH8a9K2y6w2R7xV7T7W7g6', 'Karthik Subramanian', '9845612340', 'STUDENT', 'Computer Science')
ON CONFLICT (username) DO NOTHING;

INSERT INTO students (roll_number, name, department, year_of_study, hostel_or_day_scholar, room_or_bus_route, parent_phone)
VALUES
('22CS101', 'Karthik Subramanian', 'Computer Science', 3, 'HOSTEL', 'B-Block 204', '9845612340'),
('22CS102', 'Priya Anbarasan', 'Computer Science', 3, 'DAY_SCHOLAR', 'Bus Route #14 (Tambaram)', '9845612341'),
('23ME045', 'Vigneshwaran K', 'Mechanical Engg', 2, 'HOSTEL', 'A-Block 112', '9845612342'),
('21EC088', 'Sneha Murali', 'ECE', 4, 'DAY_SCHOLAR', 'Bus Route #08 (Velachery)', '9845612343')
ON CONFLICT (roll_number) DO NOTHING;
