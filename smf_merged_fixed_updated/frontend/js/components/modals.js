/**
 * frontend/js/components/modals.js
 * ================================
 * Centralized Enterprise Modal Registry for EduTrack Pro.
 * Eliminates 650+ lines of duplicate modal HTML across admin.html, faculty.html, and hod.html.
 * Single Source of Truth for:
 * - Academic Record Modal (#acadModal)
 * - NBA/NAAC Compliance Modal (#compModal)
 * - Hierarchical Role-Based Override Modals (#overrideModal_admin, #overrideModal_hod, #overrideModal_faculty)
 * - Faculty Attendance Modal (#facAttModal)
 * - Student Bio Info Modal (#infoModal)
 * - HOD Management Modals (#hodModal, #hodAttModal, #hodAttDetailModal)
 */

export const SHARED_MODALS_HTML = `
<!-- Academic Record Add/Update Modal -->
<div id="acadModal" class="modal-bg dn">
  <div class="modal-box">
    <div class="modal-header">
      <h3><i class="fa fa-graduation-cap"></i> Add / Update Academic Record</h3>
      <button onclick="closeModal('acadModal')"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body">
      <div class="fg"><label>Student ID *</label><input id="acadStudentId" class="sel" placeholder="e.g. STU001"/></div>
      <div class="fg-3">
        <div class="fg"><label>Semester *</label><input id="acadSemester" type="number" min="1" max="8" class="sel" value="1"/></div>
        <div class="fg"><label>CGPA</label><input id="acadCgpa" type="number" step="0.01" min="0" max="10" class="sel"/></div>
        <div class="fg"><label>SGPA</label><input id="acadSgpa" type="number" step="0.01" min="0" max="10" class="sel"/></div>
      </div>
      <div class="fg"><label>Backlog Count</label><input id="acadBacklogCount" type="number" min="0" class="sel" value="0"/></div>
      <div class="fg"><label>Backlog Subjects (comma-separated)</label><input id="acadBacklogSubjects" class="sel" placeholder="e.g. MA3151, CS3251"/></div>
      <button class="btn-primary" onclick="saveAcademicRecord()" style="margin-top:8px"><i class="fa fa-save"></i> Save Record</button>
    </div>
  </div>
</div>

<!-- Compliance Add Item Modal -->
<div id="compModal" class="modal-bg dn">
  <div class="modal-box">
    <div class="modal-header">
      <h3><i class="fa fa-file-shield"></i> Add Compliance Item</h3>
      <button onclick="closeModal('compModal')"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body">
      <div class="fg-3">
        <div class="fg"><label>Department</label><input id="compDept" class="sel" placeholder="e.g. CSE"/></div>
        <div class="fg"><label>Category *</label>
          <select id="compCategory" class="sel"><option value="NBA">NBA</option><option value="NAAC">NAAC</option></select>
        </div>
        <div class="fg"><label>Due Date</label><input id="compDueDate" type="date" class="sel"/></div>
      </div>
      <div class="fg"><label>Title *</label><input id="compTitle" class="sel" placeholder="e.g. SAR Submission"/></div>
      <div class="fg"><label>Description</label><input id="compDescription" class="sel" placeholder="Optional details"/></div>
      <div class="fg"><label>Assigned To</label><input id="compAssignedTo" class="sel" placeholder="e.g. Dr. S. Rajendran"/></div>
      <button class="btn-primary" onclick="saveComplianceItem()" style="margin-top:8px"><i class="fa fa-save"></i> Add Item</button>
    </div>
  </div>
</div>

<!-- ── ADMIN → HOD Override Modal ─────────────────────────── -->
<div id="overrideModal_admin" class="modal-bg dn">
  <div class="modal-box" style="max-width:580px;width:96%">
    <div class="modal-header" style="background:linear-gradient(135deg,#dc2626,#9333ea);color:#fff;border-radius:12px 12px 0 0;display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.25rem">
      <h3 style="color:#fff;margin:0;font-size:1.05rem"><i class="fa fa-shield-halved"></i> Admin Dashboard — HOD Attendance Override</h3>
      <button onclick="closeModal('overrideModal_admin')" style="background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:1.1rem"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" style="max-height:78vh;overflow-y:auto;padding:1.25rem">
      <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:.5rem 1rem;margin-bottom:1rem;font-size:.82rem;color:#991b1b;display:flex;align-items:center;gap:.5rem">
        <i class="fa fa-user-shield"></i>
        <span><strong>Admin</strong> — You can only override <strong>HOD</strong> attendance records. Faculty and Student records are outside your override scope.</span>
      </div>
      <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#0284c7;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-user-gear"></i> Modifier (Admin)</div>
        <div class="fg">
          <label style="font-size:.8rem;font-weight:600">Admin ID <span style="color:#ef4444">*</span></label>
          <input id="adm_facultyId" placeholder="Your Admin ID" style="font-weight:600"/>
        </div>
      </div>
      <div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#7c3aed;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-crosshairs"></i> Target HOD Record</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">HOD ID <span style="color:#ef4444">*</span></label>
            <input id="adm_hodId" placeholder="e.g. HOD001" style="font-family:monospace;font-weight:600;text-transform:uppercase"/>
          </div>
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Department <span style="color:#ef4444">*</span></label>
            <select id="adm_dept">
              <option value="">— Select —</option>
              <option value="CSE">CSE</option><option value="IT">IT</option>
              <option value="ECE">ECE</option><option value="EEE">EEE</option>
              <option value="MECH">MECH</option><option value="CIVIL">CIVIL</option>
              <option value="AIDS">AIDS</option><option value="AIML">AIML</option>
            </select>
          </div>
        </div>
        <div class="fg" style="margin-top:.6rem">
          <label style="font-size:.79rem;font-weight:600">Date <span style="color:#ef4444">*</span></label>
          <input type="date" id="adm_date"/>
        </div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-pen-to-square"></i> Override Action & Justification</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Action <span style="color:#ef4444">*</span></label>
            <select id="adm_action" style="font-weight:600">
              <option value="mark_present">Mark Present</option>
              <option value="mark_absent">Mark Absent</option>
              <option value="on_duty">On Duty (OD)</option>
              <option value="medical_leave">Medical Leave</option>
              <option value="casual_leave">Casual Leave</option>
            </select>
          </div>
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Category</label>
            <select id="adm_category">
              <option value="administrative">Administrative</option>
              <option value="meeting">Official Meeting</option>
              <option value="inspection">AICTE/Anna Univ Inspection</option>
              <option value="emergency">Emergency</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>
        <div class="fg" style="margin-top:.6rem">
          <label style="font-size:.79rem;font-weight:600">Reason / Justification <span style="color:#ef4444">*</span></label>
          <textarea id="adm_reason" rows="2" placeholder="Official justification for this override (required for audit log)..." style="font-size:.82rem"></textarea>
        </div>
      </div>
    </div>
    <div class="modal-footer" style="border-top:1px solid #e2e8f0;padding:.9rem 1.25rem;display:flex;justify-content:flex-end;gap:.75rem">
      <button class="btn-secondary" onclick="closeModal('overrideModal_admin')"><i class="fa fa-xmark"></i> Cancel</button>
      <button class="btn-primary" onclick="submitAdminOverride()" style="background:linear-gradient(135deg,#dc2626,#9333ea)"><i class="fa fa-check"></i> Apply Override</button>
    </div>
  </div>
</div>

<!-- ── HOD → Faculty Override Modal ───────────────────────── -->
<div id="overrideModal_hod" class="modal-bg dn">
  <div class="modal-box" style="max-width:580px;width:96%">
    <div class="modal-header" style="background:linear-gradient(135deg,#7c3aed,#2563eb);color:#fff;border-radius:12px 12px 0 0;display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.25rem">
      <h3 style="color:#fff;margin:0;font-size:1.05rem"><i class="fa fa-user-tie"></i> HOD Dashboard — Faculty Attendance Override</h3>
      <button onclick="closeModal('overrideModal_hod')" style="background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:1.1rem"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" style="max-height:78vh;overflow-y:auto;padding:1.25rem">
      <div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:8px;padding:.5rem 1rem;margin-bottom:1rem;font-size:.82rem;color:#6b21a8;display:flex;align-items:center;gap:.5rem">
        <i class="fa fa-user-tie"></i>
        <span><strong>HOD</strong> — You can only override <strong>Faculty</strong> in your department. Student and HOD records are outside your scope.</span>
      </div>
      <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#0284c7;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-user-check"></i> Modifier (HOD)</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.8rem;font-weight:600">HOD ID <span style="color:#ef4444">*</span></label>
            <input id="hod_facultyId" placeholder="Your HOD ID" style="font-weight:600"/>
          </div>
          <div class="fg">
            <label style="font-size:.8rem;font-weight:600">Your Dept <span style="color:#ef4444">*</span></label>
            <select id="hod_dept">
              <option value="">— Select —</option>
              <option value="CSE">CSE</option><option value="IT">IT</option>
              <option value="ECE">ECE</option><option value="EEE">EEE</option>
              <option value="MECH">MECH</option><option value="CIVIL">CIVIL</option>
              <option value="AIDS">AIDS</option><option value="AIML">AIML</option>
            </select>
          </div>
        </div>
      </div>
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#16a34a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-chalkboard-user"></i> Target Faculty Record</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Faculty ID <span style="color:#ef4444">*</span></label>
            <input id="hod_targetFacId" placeholder="e.g. FAC001" style="font-family:monospace;font-weight:600;text-transform:uppercase"/>
          </div>
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Date <span style="color:#ef4444">*</span></label>
            <input type="date" id="hod_date"/>
          </div>
        </div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-pen-to-square"></i> Override Action & Justification</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Action <span style="color:#ef4444">*</span></label>
            <select id="hod_action" style="font-weight:600">
              <option value="mark_present">Mark Present</option>
              <option value="mark_absent">Mark Absent</option>
              <option value="on_duty">On Duty (OD)</option>
              <option value="medical_leave">Medical Leave</option>
              <option value="casual_leave">Casual Leave</option>
            </select>
          </div>
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Category</label>
            <select id="hod_category">
              <option value="academic">Academic Duty</option>
              <option value="exam_duty">Exam Invigilation Duty</option>
              <option value="evaluation">Valuation / Paper Correction</option>
              <option value="conference">Conference / FDP</option>
              <option value="medical">Medical</option>
              <option value="personal">Personal Leave</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>
        <div class="fg" style="margin-top:.6rem">
          <label style="font-size:.79rem;font-weight:600">Reason / Justification <span style="color:#ef4444">*</span></label>
          <textarea id="hod_reason" rows="2" placeholder="HOD justification for this override (required for audit log)..." style="font-size:.82rem"></textarea>
        </div>
      </div>
    </div>
    <div class="modal-footer" style="border-top:1px solid #e2e8f0;padding:.9rem 1.25rem;display:flex;justify-content:flex-end;gap:.75rem">
      <button class="btn-secondary" onclick="closeModal('overrideModal_hod')"><i class="fa fa-xmark"></i> Cancel</button>
      <button class="btn-primary" onclick="submitHodOverride()" style="background:linear-gradient(135deg,#7c3aed,#2563eb)"><i class="fa fa-check"></i> Apply Override</button>
    </div>
  </div>
</div>

<!-- ── FACULTY → Student Override Modal ───────────────────── -->
<div id="overrideModal_faculty" class="modal-bg dn">
  <div class="modal-box" style="max-width:580px;width:96%">
    <div class="modal-header" style="background:linear-gradient(135deg,#16a34a,#0891b2);color:#fff;border-radius:12px 12px 0 0;display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.25rem">
      <h3 style="color:#fff;margin:0;font-size:1.05rem"><i class="fa fa-chalkboard-user"></i> Faculty Dashboard — Student Attendance Override</h3>
      <button onclick="closeModal('overrideModal_faculty')" style="background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:1.1rem"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" style="max-height:78vh;overflow-y:auto;padding:1.25rem">
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:.5rem 1rem;margin-bottom:1rem;font-size:.82rem;color:#166534;display:flex;align-items:center;gap:.5rem">
        <i class="fa fa-graduation-cap"></i>
        <span><strong>Faculty</strong> — You can only override <strong>Student</strong> attendance for assigned classes and periods.</span>
      </div>
      <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#0284c7;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-user-check"></i> Modifier (Faculty)</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.8rem;font-weight:600">Faculty ID <span style="color:#ef4444">*</span></label>
            <input id="fac_facultyId" placeholder="Your Faculty ID" style="font-weight:600"/>
          </div>
          <div class="fg">
            <label style="font-size:.8rem;font-weight:600">Department <span style="color:#ef4444">*</span></label>
            <select id="fac_dept">
              <option value="">— Select —</option>
              <option value="CSE">CSE</option><option value="IT">IT</option>
              <option value="ECE">ECE</option><option value="EEE">EEE</option>
              <option value="MECH">MECH</option><option value="CIVIL">CIVIL</option>
              <option value="AIDS">AIDS</option><option value="AIML">AIML</option>
            </select>
          </div>
        </div>
      </div>
      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#1d4ed8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-user-graduate"></i> Target Student Record</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Student ID or Register No. <span style="color:#ef4444">*</span></label>
            <input id="fac_studentId" placeholder="e.g. STU001 or 2101..." style="font-family:monospace;font-weight:600"/>
          </div>
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Date <span style="color:#ef4444">*</span></label>
            <input type="date" id="fac_date"/>
          </div>
        </div>
        <div class="fg" style="margin-top:.6rem">
          <label style="font-size:.79rem;font-weight:600">Period <span style="color:#ef4444">*</span></label>
          <select id="fac_period" style="font-weight:600">
            <option value="Period_1">Period 1 (08:30 - 09:20)</option>
            <option value="Period_2">Period 2 (09:20 - 10:10)</option>
            <option value="Period_3">Period 3 (10:25 - 11:15)</option>
            <option value="Period_4">Period 4 (11:15 - 12:05)</option>
            <option value="Period_5">Period 5 (12:55 - 01:45)</option>
            <option value="Period_6">Period 6 (01:45 - 02:35)</option>
            <option value="Period_7">Period 7 (02:45 - 03:35)</option>
          </select>
        </div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem">
        <div style="font-size:.72rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem"><i class="fa fa-pen-to-square"></i> Override Action & Justification</div>
        <div class="fg-2">
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Action <span style="color:#ef4444">*</span></label>
            <select id="fac_action" style="font-weight:600">
              <option value="mark_present">Mark Present</option>
              <option value="mark_absent">Mark Absent</option>
              <option value="on_duty">On Duty (OD)</option>
              <option value="medical_leave">Medical Leave</option>
            </select>
          </div>
          <div class="fg">
            <label style="font-size:.79rem;font-weight:600">Category</label>
            <select id="fac_category">
              <option value="medical">Medical Certificate Submitted</option>
              <option value="od_sports">Sports OD</option>
              <option value="od_symposium">Symposium / Conference OD</option>
              <option value="od_placement">Placement / Interview OD</option>
              <option value="biometric_error">Biometric Face Not Recognized</option>
              <option value="late_entry">Late Entry Allowed</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>
        <div class="fg" style="margin-top:.6rem">
          <label style="font-size:.79rem;font-weight:600">Reason / Justification <span style="color:#ef4444">*</span></label>
          <textarea id="fac_reason" rows="2" placeholder="Teacher justification (required for audit log)..." style="font-size:.82rem"></textarea>
        </div>
      </div>
    </div>
    <div class="modal-footer" style="border-top:1px solid #e2e8f0;padding:.9rem 1.25rem;display:flex;justify-content:flex-end;gap:.75rem">
      <button class="btn-secondary" onclick="closeModal('overrideModal_faculty')"><i class="fa fa-xmark"></i> Cancel</button>
      <button class="btn-primary" onclick="submitFacultyOverride()" style="background:linear-gradient(135deg,#16a34a,#0891b2)"><i class="fa fa-check"></i> Apply Override</button>
    </div>
  </div>
</div>

<!-- Faculty Attendance Modal -->
<div id="facAttModal" class="modal-bg dn">
  <div class="modal-box" style="max-width:540px;width:96%">
    <div class="modal-header" style="background:linear-gradient(135deg,#0891b2,#0284c7);color:#fff;border-radius:12px 12px 0 0;display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.25rem">
      <h3 style="color:#fff;margin:0;font-size:1.05rem" id="facAttModalTitle"><i class="fa fa-calendar-check"></i> Record Faculty Attendance</h3>
      <button onclick="closeModal('facAttModal')" style="background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:1.1rem"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" style="padding:1.25rem">
      <input type="hidden" id="fac_att_fid"/>
      <div class="fg-2">
        <div class="fg">
          <label>Status <span style="color:#ef4444">*</span></label>
          <select id="fac_att_status">
            <option value="present">Present</option>
            <option value="absent">Absent</option>
            <option value="late">Late</option>
            <option value="od">On Duty (OD)</option>
            <option value="leave">Leave</option>
          </select>
        </div>
        <div class="fg">
          <label>Arrival Time</label>
          <input type="time" id="fac_att_time" value="09:00"/>
        </div>
      </div>
      <div class="fg">
        <label>Reason <span class="hint">(for absent/late/leave)</span></label>
        <textarea id="fac_att_reason" rows="2" placeholder="Enter reason..."></textarea>
      </div>
    </div>
    <div class="modal-footer" style="border-top:1px solid #e2e8f0;padding:.9rem 1.25rem;display:flex;justify-content:flex-end;gap:.75rem">
      <button class="btn-secondary" onclick="closeModal('facAttModal')">Cancel</button>
      <button class="btn-primary" onclick="saveFacultyAttendance()" style="background:linear-gradient(135deg,#0891b2,#0284c7)"><i class="fa fa-save"></i> Save</button>
    </div>
  </div>
</div>

<!-- Info Modal (Student / Faculty Detail View) -->
<div id="infoModal" class="modal-bg dn">
  <div class="modal-box" style="max-width:560px;width:96%">
    <div class="modal-header">
      <h3 id="infoModalTitle"><i class="fa fa-circle-info"></i> Details</h3>
      <button onclick="closeModal('infoModal')"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" id="infoModalBody" style="max-height:70vh;overflow-y:auto"></div>
    <div class="modal-footer" id="infoModalFooter">
      <button class="btn-primary" onclick="closeModal('infoModal')">Close</button>
    </div>
  </div>
</div>

<!-- HOD Modal -->
<div id="hodModal" class="modal-bg dn">
  <div class="modal-box" style="max-width:600px;width:96%">
    <div class="modal-header" style="background:linear-gradient(135deg,#0891b2,#0284c7);color:#fff;border-radius:12px 12px 0 0;display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.25rem">
      <h3 style="color:#fff;margin:0;font-size:1.05rem" id="hodModalTitle"><i class="fa fa-user-tie"></i> Add HOD</h3>
      <button onclick="closeModal('hodModal')" style="background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:1.1rem"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" style="padding:1.25rem;max-height:75vh;overflow-y:auto">
      <input type="hidden" id="hm_hod_id"/>
      <div class="fg-2">
        <div class="fg">
          <label>Department <span style="color:#ef4444">*</span></label>
          <select id="hm_dept">
            <option value="">— Select —</option>
            <option value="CSE">CSE</option><option value="IT">IT</option>
            <option value="ECE">ECE</option><option value="EEE">EEE</option>
            <option value="MECH">MECH</option><option value="CIVIL">CIVIL</option>
            <option value="AIDS">AIDS</option><option value="AIML">AIML</option>
          </select>
        </div>
        <div class="fg">
          <label>Full Name <span style="color:#ef4444">*</span></label>
          <input id="hm_name" placeholder="Dr. Firstname Lastname"/>
        </div>
      </div>
      <div class="fg-2">
        <div class="fg">
          <label>Email <span style="color:#ef4444">*</span></label>
          <input id="hm_email" type="email" placeholder="hod.dept@college.edu"/>
        </div>
        <div class="fg">
          <label>Phone</label>
          <input id="hm_phone" placeholder="9876543210"/>
        </div>
      </div>
      <div class="fg-2">
        <div class="fg">
          <label>Cabin / Room</label>
          <input id="hm_cabin" placeholder="e.g. Admin Block - 204"/>
        </div>
        <div class="fg">
          <label>Specialization</label>
          <input id="hm_spec" placeholder="e.g. Distributed Systems"/>
        </div>
      </div>
      <div class="fg-2">
        <div class="fg">
          <label>Date of Joining</label>
          <input id="hm_doj" type="date"/>
        </div>
        <div class="fg">
          <label>Qualification</label>
          <input id="hm_qual" placeholder="e.g. Ph.D., M.E."/>
        </div>
      </div>
    </div>
    <div class="modal-footer" style="border-top:1px solid #e2e8f0;padding:.9rem 1.25rem;display:flex;justify-content:flex-end;gap:.75rem">
      <button class="btn-secondary" onclick="closeModal('hodModal')"><i class="fa fa-xmark"></i> Cancel</button>
      <button class="btn-primary" onclick="saveHod()" style="background:linear-gradient(135deg,#0891b2,#0284c7)"><i class="fa fa-save"></i> Save HOD</button>
    </div>
  </div>
</div>

<!-- HOD Attendance Modal -->
<div id="hodAttModal" class="modal-bg dn">
  <div class="modal-box" style="max-width:540px;width:96%">
    <div class="modal-header" style="background:linear-gradient(135deg,#0891b2,#0284c7);color:#fff;border-radius:12px 12px 0 0;display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.25rem">
      <h3 style="color:#fff;margin:0;font-size:1.05rem" id="hodAttModalTitle"><i class="fa fa-calendar-check"></i> Record HOD Attendance</h3>
      <button onclick="closeModal('hodAttModal')" style="background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:1.1rem"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" style="padding:1.25rem">
      <input type="hidden" id="hod_att_fid"/>
      <div class="fg-2">
        <div class="fg">
          <label>Status <span style="color:#ef4444">*</span></label>
          <select id="hod_att_status">
            <option value="present">Present</option>
            <option value="absent">Absent</option>
            <option value="late">Late</option>
            <option value="od">On Duty (OD)</option>
            <option value="leave">Leave</option>
          </select>
        </div>
        <div class="fg">
          <label>Arrival Time</label>
          <input type="time" id="hod_att_time" value="09:00"/>
        </div>
      </div>
      <div class="fg">
        <label>Reason <span class="hint">(for absent/late/leave)</span></label>
        <textarea id="hod_att_reason" rows="2" placeholder="Enter reason..."></textarea>
      </div>
    </div>
    <div class="modal-footer" style="border-top:1px solid #e2e8f0;padding:.9rem 1.25rem;display:flex;justify-content:flex-end;gap:.75rem">
      <button class="btn-secondary" onclick="closeModal('hodAttModal')">Cancel</button>
      <button class="btn-primary" onclick="saveHodAttendance()" style="background:linear-gradient(135deg,#0891b2,#0284c7)"><i class="fa fa-save"></i> Save</button>
    </div>
  </div>
</div>

<!-- HOD Attendance Detail Modal -->
<div id="hodAttDetailModal" class="modal-bg dn">
  <div class="modal-box" style="max-width:700px;width:96%">
    <div class="modal-header">
      <h3 id="hodAttDetailTitle"><i class="fa fa-calendar-days"></i> HOD Attendance Log</h3>
      <button onclick="closeModal('hodAttDetailModal')"><i class="fa fa-xmark"></i></button>
    </div>
    <div class="modal-body" id="hodAttDetailBody" style="max-height:65vh;overflow-y:auto"></div>
    <div class="modal-footer">
      <button class="btn-primary" onclick="closeModal('hodAttDetailModal')">Close</button>
    </div>
  </div>
</div>
`;

/**
 * Injects shared modals into container or body if not already present
 */
export function initModals() {
  let target = document.getElementById('sharedModalsContainer');
  if (!target) {
    target = document.createElement('div');
    target.id = 'sharedModalsContainer';
    document.body.appendChild(target);
  }
  // Inject markup
  target.innerHTML = SHARED_MODALS_HTML;
  console.log('[Modals] 10 Shared Enterprise Modals mounted successfully.');
}

// Auto-run if DOM is already loaded or attach listener
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModals);
  } else {
    initModals();
  }
}

export default initModals;
