# 🚪 Student Gate Pass & Watchman Integration Guide

This guide explains how the **Student Gate Pass System** works across both projects:
1. **EduTrack Pro / Face Recognition System (`smf_merged_fixed_updated`)** on `http://localhost:8000`
2. **Watchman Security Portal (`watchman`)** on `http://localhost:5173`

---

## 🏗️ Architecture Overview

The system uses the **REST API Bridge Pattern (Microservices)**:
- Both projects run completely independently on their own ports.
- Neither project touches the other's database directly.
- Communication is through CORS-enabled high-speed JSON APIs.

```
+------------------------------------+          REST API (Port 8000)          +------------------------------------+
|         EDUTRACK PRO               | <====================================> |          WATCHMAN PORTAL           |
|                                    |                                        |                                    |
| 1. Student Portal (Apply Pass)     |    POST /api/v1/gatepass/verify        | • Watchman types OTP               |
| 2. Class Incharge Approval         |    POST /api/v1/gatepass/mark-exit     | • Displays Student Photo & Status  |
| 3. HOD Approval -> OTP Generated   |    GET  /api/v1/gatepass/recent-exits  | • Guard clicks "Confirm Exit"      |
+------------------------------------+                                        +------------------------------------+
```

---

## 🚀 How to Run Both Projects

### Step 1: Start EduTrack Pro (Face Recognition & Portals)
In terminal inside `smf_merged_fixed_updated`:
```bash
python main.py
```
* EduTrack Backend will start at: `http://localhost:8000`
* Student Portal: `http://localhost:8000/student`
* Faculty Portal: `http://localhost:8000/faculty.html`
* HOD Portal: `http://localhost:8000/hod.html`

### Step 2: Start Watchman Portal
In terminal inside `watchman/frontend`:
```bash
npm run dev
```
* Watchman Portal starts at: `http://localhost:5173`

---

## 📦 How to Add the Gate Pass Page into the Watchman React App

1. Copy the file:
   `smf_merged_fixed_updated/watchman_component/StudentGatePassVerify.jsx`
   into your Watchman project:
   `watchman/frontend/src/pages/StudentGatePassVerify.jsx`

2. In your Watchman routing (e.g. `App.jsx` or `App.tsx`):
   ```jsx
   import StudentGatePassVerify from "./pages/StudentGatePassVerify";

   // Inside your <Routes>:
   <Route path="/student-gatepass" element={<StudentGatePassVerify />} />
   ```

3. In your Watchman Navigation Sidebar (e.g. `Sidebar.jsx` or `Navbar.jsx`):
   ```jsx
   <NavLink to="/student-gatepass" className="nav-item">
     <span>🚪 Student Gate Pass</span>
   </NavLink>
   ```

---

## 🔄 End-to-End Test Workflow

1. **Student submits Gate Pass:**
   - Go to `http://localhost:8000/student` and login with Register Number and DOB.
   - Click **🚪 Gate Pass** in sidebar.
   - Fill reason, date, and out-time $\rightarrow$ click **🚀 Submit for Gate Pass**.

2. **Class Incharge approves:**
   - Go to `http://localhost:8000/faculty.html` and sign in.
   - Click **🚪 Gate Pass Approvals** in sidebar.
   - Click **Approve** on the student's request $\rightarrow$ status becomes `Forwarded to HOD`.

3. **HOD final approval & OTP generation:**
   - Go to `http://localhost:8000/hod.html` and sign in.
   - Click **🚪 Gate Pass Approvals** in sidebar.
   - Click **Final Approve (Generate OTP)**.
   - System creates a unique 6-digit OTP (e.g. `745743`).

4. **Student sees active OTP & QR Code:**
   - On the Student Portal (`/student`), under **Gate Pass**, the student now sees a green card:
     - 🟢 **GATE PASS APPROVED — READY FOR EXIT**
     - Big OTP: **`745743`**
     - QR Token code

5. **Watchman verifies OTP at the Gate:**
   - In the Watchman App (`http://localhost:5173/student-gatepass`):
   - Watchman enters `745743` and clicks **Verify Gate Pass**.
   - System immediately displays:
     - **Student Photo**
     - Student Name, Register Number, Department
     - Green Badge: **✅ GATE PASS APPROVED — ALLOW EXIT**
     - Verification trail: Class Incharge name + HOD approval
   - Watchman clicks **🚪 Confirm Exit & Open Gate**.
   - The exit timestamp is recorded in the database, and the pass is marked as used (cannot be reused by anyone else).
