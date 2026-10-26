import axios from 'axios';

// Base Axios instance pointing to the Spring Boot REST Backend
const apiClient = axios.create({
  baseURL: 'http://localhost:8080/api',
  timeout: 4000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to attach JWT auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('campusguard_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Fallback Mock Data Store (ensures full interactive demo even before Spring Boot starts)
export const initialMockState = {
  students: [
    {
      rollNumber: '22CS101',
      name: 'Karthik Subramanian',
      department: 'Computer Science (B.Tech)',
      yearOfStudy: 3,
      hostelOrDayScholar: 'HOSTEL',
      roomOrBusRoute: 'B-Block Room 204',
      parentPhone: '+91 98456 12340',
      photoUrl: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80',
      isSuspended: false,
    },
    {
      rollNumber: '22CS102',
      name: 'Priya Anbarasan',
      department: 'Computer Science (B.Tech)',
      yearOfStudy: 3,
      hostelOrDayScholar: 'DAY_SCHOLAR',
      roomOrBusRoute: 'College Bus #14 (Tambaram)',
      parentPhone: '+91 98456 12341',
      photoUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
      isSuspended: false,
    },
    {
      rollNumber: '23ME045',
      name: 'Vigneshwaran K',
      department: 'Mechanical Engineering',
      yearOfStudy: 2,
      hostelOrDayScholar: 'HOSTEL',
      roomOrBusRoute: 'A-Block Room 112',
      parentPhone: '+91 98456 12342',
      photoUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80',
      isSuspended: false,
    },
    {
      rollNumber: '21EC088',
      name: 'Sneha Murali',
      department: 'Electronics & Comm (ECE)',
      yearOfStudy: 4,
      hostelOrDayScholar: 'DAY_SCHOLAR',
      roomOrBusRoute: 'College Bus #08 (Velachery)',
      parentPhone: '+91 98456 12343',
      photoUrl: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80',
      isSuspended: false,
    }
  ],
  gateLogs: [],
  outPasses: [
    {
      id: 101,
      passCode: 'OP-4592',
      studentRollNumber: '22CS101',
      studentName: 'Karthik Subramanian',
      department: 'Computer Science',
      reason: 'Need to visit Hardware shop for final year IoT hardware project components',
      destination: 'Ritchie Street, Chennai',
      outTimeExpected: 'Today 04:00 PM',
      inTimeExpected: 'Today 08:30 PM',
      status: 'APPROVED_BY_HOD',
      approvedBy: 'Prof. Meenakshi (HOD CSE)',
      parentConsentVerified: true,
      createdAt: 'Today 01:15 PM'
    },
    {
      id: 102,
      passCode: 'OP-7731',
      studentRollNumber: '23ME045',
      studentName: 'Vigneshwaran K',
      department: 'Mechanical Engg',
      reason: 'Medical checkup at Apollo Hospital',
      destination: 'Greams Road, Chennai',
      outTimeExpected: 'Today 05:00 PM',
      inTimeExpected: 'Today 09:00 PM',
      status: 'PENDING',
      approvedBy: null,
      parentConsentVerified: true,
      createdAt: 'Today 02:30 PM'
    }
  ],
  visitors: [
    {
      id: 201,
      passNumber: 'VP-8821',
      visitorName: 'Narayanan R',
      phoneNumber: '98401 23456',
      purpose: 'Meeting Principal regarding Scholarship',
      personToMeet: 'Dr. Sundaram (Admin)',
      departmentToVisit: 'Administration Office',
      idProofType: 'Aadhaar Card',
      idProofNumber: 'XXXX-XXXX-4921',
      checkInTime: '11:15 AM',
      status: 'ACTIVE',
      badgeNumber: 'Badge #12',
      vehicleNumber: 'TN 09 BZ 4421'
    },
    {
      id: 202,
      passNumber: 'VP-8820',
      visitorName: 'Gopinath (Lab Equipment Vendor)',
      phoneNumber: '97890 55123',
      purpose: 'Delivering Physics Lab Microscopes',
      personToMeet: 'Dr. Ramesh (Physics HOD)',
      departmentToVisit: 'Science Block Lab 2',
      idProofType: 'Driving Licence',
      idProofNumber: 'DL-TN-02-2019',
      checkInTime: '10:30 AM',
      status: 'CHECKED_OUT',
      badgeNumber: 'Badge #07',
      vehicleNumber: 'TN 02 AY 1009'
    }
  ],
  parcels: [
    {
      id: 301,
      courierCompany: 'Amazon',
      trackingNumber: 'AMZ-4491-002',
      recipientName: 'Prof. Meenakshi',
      departmentOrHostel: 'CSE Department Room 302',
      recipientPhone: '98765 00002',
      receivedAt: '10:45 AM',
      status: 'WAITING_COLLECTION',
      handoverOtp: '4182',
      receivedByWatchman: 'Ramasamy'
    },
    {
      id: 302,
      courierCompany: 'Flipkart',
      trackingNumber: 'FKT-8900-112',
      recipientName: 'Karthik Subramanian',
      departmentOrHostel: 'Hostel Block B - Room 204',
      recipientPhone: '98456 12340',
      receivedAt: '11:30 AM',
      status: 'WAITING_COLLECTION',
      handoverOtp: '9034',
      receivedByWatchman: 'Ramasamy'
    }
  ],
  stats: {
    totalOnCampus: 1420,
    entriesToday: 486,
    exitsToday: 312,
    activeVisitors: 28,
    pendingOutPasses: 9,
    parcelsAtGate: 14,
    lateEntriesToday: 6
  }
};

// LocalStorage helpers for QR Smart Gate Pass System
const PASSES_STORAGE_KEY = 'campusguard_all_passes';

function getStoredPasses() {
  try {
    const raw = localStorage.getItem(PASSES_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn('Error reading stored passes:', e);
  }
  // Default seed passes for immediate testing of automatic live screen & all conditions:
  const seedPasses = [
    {
      id: 500,
      visitorType: 'STUDENT',
      visitorName: 'Example Student',
      identifier: '23CSE001',
      phoneNumber: '+91 98456 99881',
      department: 'CSE',
      reason: 'College bus missed',
      additionalDetails: 'Bus #14 breakdown at Tambaram junction',
      passNumber: 'GP-1024',
      otp: '654321',
      createdAt: new Date().toISOString(),
      arrivalTime: '9:30 AM',
      otpExpiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      passStatus: 'GENERATED',
      approvalStatus: 'APPROVAL_PENDING',
      checkInStatus: 'WAITING_AT_GATE',
      status: 'PENDING_APPROVAL',
      policyAlert: 'Arrived after 09:00 AM cutoff. Requires watchman verification or HOD clearance.'
    },
    {
      id: 501,
      visitorType: 'STUDENT',
      visitorName: 'Karthik Subramanian',
      identifier: '22CS101',
      phoneNumber: '+91 98456 12340',
      department: 'Computer Science (B.Tech)',
      reason: 'Missed College Bus #14 (Tambaram Route) due to traffic',
      additionalDetails: 'Attending 2nd period OS Lab',
      passNumber: 'GP-2026-4011',
      otp: '741258', // Valid demo OTP
      createdAt: new Date().toISOString(),
      arrivalTime: '9:15 AM',
      otpExpiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      passStatus: 'GENERATED',
      approvalStatus: 'APPROVAL_PENDING',
      checkInStatus: 'WAITING_AT_GATE',
      status: 'PENDING_APPROVAL',
      policyAlert: 'Late arrival - Attending 2nd period OS Lab'
    },
    {
      id: 502,
      visitorType: 'PARENT',
      visitorName: 'Senthil Nathan & Selvi',
      identifier: 'Student: Priya (22CS102)',
      phoneNumber: '+91 98456 12341',
      department: 'Computer Science',
      reason: 'Parent-Teacher Meeting with HOD & Tuition Fee Submission',
      additionalDetails: 'Prior appointment scheduled with HOD at 11:30 AM',
      passNumber: 'GP-2026-4012',
      otp: '852369',
      createdAt: new Date().toISOString(),
      arrivalTime: '11:15 AM',
      otpExpiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      passStatus: 'GENERATED',
      approvalStatus: 'APPROVAL_PENDING',
      checkInStatus: 'WAITING_AT_GATE',
      status: 'PENDING_APPROVAL',
      policyAlert: 'Office Visitor - Requires HOD / Admin Office clearance'
    },
    {
      id: 503,
      visitorType: 'STAFF',
      visitorName: 'Dr. R. Manivannan',
      identifier: 'STF-8821',
      phoneNumber: '+91 94441 55678',
      department: 'Mechanical Engineering',
      reason: 'Guest Lecture on Advanced Robotics for 3rd Year Mech',
      additionalDetails: 'Invited by Dean Academics',
      passNumber: 'GP-2026-3098',
      otp: '123456',
      createdAt: new Date(Date.now() - 3600000).toISOString(),
      arrivalTime: '09:05 AM',
      otpExpiresAt: new Date(Date.now() + 14 * 60 * 1000).toISOString(),
      passStatus: 'GENERATED',
      approvalStatus: 'APPROVED',
      checkInStatus: 'INSIDE_CAMPUS',
      status: 'APPROVED',
      checkInTime: '09:15 AM',
      verifiedByWatchmanId: 'WM-01',
      verifiedByWatchmanName: 'Ramasamy (Main Gate Security)',
      policyAlert: 'Recognized Faculty - Prior Approved'
    },
    {
      id: 504,
      visitorType: 'OTHERS',
      visitorName: 'Gopinath (Vendor)',
      identifier: '+91 97890 55123',
      phoneNumber: '+91 97890 55123',
      department: 'Science Block Lab 2',
      reason: 'Delivering Physics Lab Microscopes & Glassware',
      personToMeet: 'Dr. Ramesh (Physics HOD)',
      passNumber: 'GP-2026-2001',
      otp: '999999',
      createdAt: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
      arrivalTime: '08:45 AM',
      otpExpiresAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
      passStatus: 'GENERATED',
      approvalStatus: 'APPROVAL_PENDING',
      checkInStatus: 'WAITING_AT_GATE',
      status: 'EXPIRED',
      policyAlert: 'Expired pass - 15 minute validity exceeded'
    }
  ];
  try {
    localStorage.setItem(PASSES_STORAGE_KEY, JSON.stringify(seedPasses));
  } catch {}
  return seedPasses;
}

function saveStoredPasses(passes) {
  try {
    localStorage.setItem(PASSES_STORAGE_KEY, JSON.stringify(passes));
  } catch (e) {
    console.warn('Error saving stored passes:', e);
  }
}

// LocalStorage helpers for Smart Digital Shift Handover
const HANDOVERS_STORAGE_KEY = 'campusguard_shift_handovers';
const HANDOVER_TASKS_STORAGE_KEY = 'campusguard_handover_tasks';

function getStoredHandovers() {
  try {
    const raw = localStorage.getItem(HANDOVERS_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn('Error reading stored handovers:', e);
  }
  const seedHandovers = [
    {
      id: 1001,
      handoverCode: 'HO-2026-8812',
      shiftName: 'Morning Shift (06:00 AM - 02:00 PM)',
      gateLocation: 'Main Gate 1',
      outgoingWatchmanId: 'WM-01',
      outgoingWatchmanName: 'Ramasamy (Main Gate Security)',
      incomingWatchmanId: 'WM-02',
      incomingWatchmanName: 'Murugan (Gate Guard - Shift B)',
      handoverTime: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
      handoverNotes: 'Principal instructed that final year IoT project students have lab permission till 08:30 PM. Gate barrier sensor was dusted and cleaned. 4 walkie talkies on charger.',
      status: 'PENDING_ACKNOWLEDGEMENT',
      totalPendingTasks: 4,
      unresolvedTasksCount: 3,
      supervisorSignedBy: null,
      supervisorSignedAt: null
    }
  ];
  try {
    localStorage.setItem(HANDOVERS_STORAGE_KEY, JSON.stringify(seedHandovers));
  } catch {}
  return seedHandovers;
}

function saveStoredHandovers(handovers) {
  try {
    localStorage.setItem(HANDOVERS_STORAGE_KEY, JSON.stringify(handovers));
  } catch (e) {
    console.warn('Error saving handovers:', e);
  }
}

function getStoredHandoverTasks() {
  try {
    const raw = localStorage.getItem(HANDOVER_TASKS_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn('Error reading stored handover tasks:', e);
  }
  const seedTasks = [
    {
      id: 2001,
      taskCode: 'TSK-VIS-501',
      handoverCode: 'HO-2026-8812',
      category: 'VISITORS',
      title: 'Karthik Subramanian (22CS101) - Inward Pass Active',
      description: 'Entered campus at 09:15 AM for OS Lab. Expected departure before 08:30 PM.',
      sourceReferenceId: 'GP-2026-4011',
      status: 'OPEN',
      priority: 'HIGH',
      nextRequiredAction: 'Verify student ID card and check out at Gate 1 upon departure.',
      createdAt: new Date(Date.now() - 3600000).toISOString(),
      lastUpdatedAt: new Date(Date.now() - 3600000).toISOString(),
      resolvedBy: null,
      resolvedAt: null,
      resolutionNotes: null
    },
    {
      id: 2002,
      taskCode: 'TSK-PCL-301',
      handoverCode: 'HO-2026-8812',
      category: 'PARCELS',
      title: 'Amazon Courier AMZ-4491-002 for Prof. Meenakshi',
      description: 'CSE Department package arrived at 10:45 AM. Stored in Gate Desk Locker #2.',
      sourceReferenceId: 'AMZ-4491-002',
      status: 'OPEN',
      priority: 'MEDIUM',
      nextRequiredAction: 'Verify 4-digit handover OTP 4182 before delivering to professor or lab assistant.',
      createdAt: new Date(Date.now() - 7200000).toISOString(),
      lastUpdatedAt: new Date(Date.now() - 7200000).toISOString(),
      resolvedBy: null,
      resolvedAt: null,
      resolutionNotes: null
    },
    {
      id: 2003,
      taskCode: 'TSK-INC-201',
      handoverCode: 'HO-2026-8812',
      category: 'INCIDENTS',
      title: 'College Bus #14 Traffic Delay & Late Entry Flag',
      description: 'Late arrival recorded for 6 students due to Tambaram highway jam. Warden notified.',
      sourceReferenceId: 'INC-2026-08',
      status: 'IN_PROGRESS',
      priority: 'MEDIUM',
      nextRequiredAction: 'Obtain evening transport log from bus supervisor at 04:30 PM.',
      createdAt: new Date(Date.now() - 10800000).toISOString(),
      lastUpdatedAt: new Date(Date.now() - 1800000).toISOString(),
      resolvedBy: null,
      resolvedAt: null,
      resolutionNotes: null
    },
    {
      id: 2004,
      taskCode: 'TSK-EQP-401',
      handoverCode: 'HO-2026-8812',
      category: 'EQUIPMENT',
      title: 'Gate 1 ANPR Camera & Boom Barrier Checklist',
      description: 'Auto-detect camera cleaned; boom barrier hydraulic test successful. 4 radios on charger.',
      sourceReferenceId: 'EQP-BAR-01',
      status: 'RESOLVED',
      priority: 'LOW',
      nextRequiredAction: 'Night shift guard to check infrared night-vision mode at 10:00 PM.',
      createdAt: new Date(Date.now() - 14400000).toISOString(),
      lastUpdatedAt: new Date(Date.now() - 1800000).toISOString(),
      resolvedBy: 'Ramasamy (Main Gate Security)',
      resolvedAt: new Date(Date.now() - 1800000).toISOString(),
      resolutionNotes: 'Boom barrier tested 15 cycles. Working smoothly.'
    }
  ];
  try {
    localStorage.setItem(HANDOVER_TASKS_STORAGE_KEY, JSON.stringify(seedTasks));
  } catch {}
  return seedTasks;
}

function saveStoredHandoverTasks(tasks) {
  try {
    localStorage.setItem(HANDOVER_TASKS_STORAGE_KEY, JSON.stringify(tasks));
  } catch (e) {
    console.warn('Error saving handover tasks:', e);
  }
}

// Smart API wrapper: Try backend with Axios, fallback seamlessly to local mock store
export const api = {
  // Auth
  async login(credentials) {
    const payload = {
      username_or_email: credentials.username_or_email || credentials.usernameOrEmail || credentials.username,
      password: credentials.password,
      role: credentials.role
    };
    try {
      const res = await apiClient.post('/auth/login', payload);
      if (res.data && res.data.token) {
        localStorage.setItem('campusguard_token', res.data.token);
      }
      return res.data;
    } catch {
      // Mock login response
      const role = credentials.role || 'WATCHMAN';
      const user = {
        token: 'mock-jwt-token-campusguard-' + Date.now(),
        id: 1,
        username: credentials.usernameOrEmail || credentials.username || 'security_officer',
        email: (credentials.usernameOrEmail || credentials.username || 'guard') + '@college.edu',
        fullName: role === 'ADMIN' ? 'Dr. Sundaram (College Admin)' :
                  role === 'FACULTY' ? 'Prof. Meenakshi (HOD CSE)' :
                  role === 'STUDENT' ? 'Karthik Subramanian' : 'Ramasamy (Main Gate Security)',
        role: role,
        department: role === 'STUDENT' || role === 'FACULTY' ? 'Computer Science' : 'Security'
      };
      return user;
    }
  },

  async verifyMfa(data) {
    try {
      const res = await apiClient.post('/auth/verify-mfa', data);
      return res.data;
    } catch (err) {
      if (err.response && err.response.data) {
        throw new Error(err.response.data.detail || err.response.data.error || 'Invalid 2-step verification code');
      }
      return {
        token: 'mock-jwt-token-campusguard-mfa-' + Date.now(),
        id: 99,
        username: 'admin',
        role: 'ADMIN',
        fullName: 'Dr. Sundaram (College Admin)',
        department: 'Management'
      };
    }
  },

  async forgotPassword(data) {
    try {
      const res = await apiClient.post('/auth/forgot-password', data);
      return res.data;
    } catch {
      const demoOtp = '824912';
      return {
        success: true,
        message: 'Verification code sent to registered contact.',
        demoOtp: demoOtp
      };
    }
  },

  async resetPassword(data) {
    try {
      const res = await apiClient.post('/auth/reset-password', data);
      return res.data;
    } catch {
      return {
        success: true,
        message: 'Password successfully reset! You can now log in.'
      };
    }
  },

  async logout() {
    try {
      const res = await apiClient.post('/auth/logout');
      return res.data;
    } catch (e) {
      console.warn('Backend logout failed or offline:', e);
      return { success: true };
    }
  },

  // Gate Lookup
  async lookupStudent(rollNumber) {
    try {
      const res = await apiClient.get(`/gate/lookup-student/${rollNumber}`);
      return res.data;
    } catch {
      const found = initialMockState.students.find(
        (s) => s.rollNumber.toLowerCase() === rollNumber.trim().toLowerCase()
      );
      if (found) return found;
      // Default generated student
      return {
        rollNumber: rollNumber.toUpperCase(),
        name: 'Student ' + rollNumber.toUpperCase(),
        department: 'Engineering Department',
        yearOfStudy: 3,
        hostelOrDayScholar: 'HOSTEL',
        roomOrBusRoute: 'Block B - Room 204',
        parentPhone: '+91 98765 43210',
        photoUrl: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150&auto=format&fit=crop&q=80',
        isSuspended: false
      };
    }
  },

  // Log Entry
  async logGateEntry(entry) {
    try {
      const res = await apiClient.post('/gate/check-in', entry);
      return res.data;
    } catch {
      return {
        id: Date.now(),
        ...entry,
        entryTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        status: entry.status || 'APPROVED'
      };
    }
  },

  // OutPasses
  async getOutPasses() {
    try {
      const res = await apiClient.get('/outpass/list');
      return res.data;
    } catch {
      return initialMockState.outPasses;
    }
  },

  async applyOutPass(data) {
    try {
      const res = await apiClient.post('/outpass/apply', data);
      return res.data;
    } catch {
      return {
        id: Date.now(),
        passCode: 'OP-' + Math.floor(1000 + Math.random() * 9000),
        ...data,
        status: 'PENDING',
        createdAt: 'Just now'
      };
    }
  },

  async verifyOutPassCode(code) {
    try {
      const res = await apiClient.post(`/outpass/verify-code/${code}`);
      return res.data;
    } catch {
      return {
        valid: true,
        message: 'Pass Verified! Gate Opened for Student.',
        pass: {
          passCode: code,
          studentName: 'Karthik Subramanian',
          studentRollNumber: '22CS101',
          department: 'Computer Science',
          destination: 'Chennai Tech Expo'
        }
      };
    }
  },

  // QR Smart Gate Pass System API
  async selfRegisterVisitor(passData) {
    try {
      const res = await apiClient.post('/visitors/self-register', passData);
      return res.data;
    } catch {
      const passes = getStoredPasses();
      const passNumber = passData.passNumber || ('GP-' + Math.floor(1000 + Math.random() * 9000));
      const otp = String(Math.floor(100000 + Math.random() * 900000));
      const now = new Date();
      const arrivalTime = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const expiresAt = new Date(now.getTime() + 15 * 60 * 1000).toISOString();

      let defaultApproval = 'APPROVAL_PENDING';
      let policyAlert = 'Awaiting security review and gate clearance';

      if (passData.visitorType === 'STUDENT') {
        defaultApproval = 'APPROVAL_PENDING';
        policyAlert = 'Student entry request logged. Review arrival time & reason.';
      } else if (passData.visitorType === 'STAFF') {
        defaultApproval = 'APPROVED';
        policyAlert = 'Recognized college faculty / staff.';
      } else if (passData.visitorType === 'PARENT') {
        defaultApproval = 'APPROVAL_PENDING';
        policyAlert = 'Parent visitor. Requires Admin Office or HOD clearance.';
      } else {
        defaultApproval = 'APPROVAL_PENDING';
        policyAlert = 'External visitor / vendor. Requires department clearance.';
      }

      const newPass = {
        id: Date.now(),
        ...passData,
        passNumber,
        otp,
        createdAt: now.toISOString(),
        arrivalTime,
        otpExpiresAt: expiresAt,
        passStatus: 'GENERATED',
        approvalStatus: passData.approvalStatus || defaultApproval,
        checkInStatus: 'WAITING_AT_GATE',
        status: defaultApproval === 'APPROVED' ? 'APPROVED' : 'PENDING_APPROVAL',
        policyAlert: passData.policyAlert || policyAlert
      };

      passes.unshift(newPass);
      saveStoredPasses(passes);

      // Real-time broadcast for live screen (0ms delay)
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('campusguard_pass_created', { detail: newPass }));
      }

      return {
        success: true,
        message: 'Digital Gate Pass generated successfully!',
        passNumber,
        otp,
        expiresAt,
        visitorPass: newPass
      };
    }
  },

  // Real-time automatic live screen feed
  async getLiveGatePassRequests() {
    const passes = getStoredPasses();
    // Return all waiting passes at gate, sorted newest first
    return passes.filter(
      (p) => p.checkInStatus === 'WAITING_AT_GATE' || p.status === 'PENDING_APPROVAL' || p.status === 'PENDING_OTP'
    );
  },

  // Watchman 1-click allow entry without manual OTP typing
  async allowPassEntry(id, payload = {}) {
    const passes = getStoredPasses();
    const pass = passes.find((p) => p.id === Number(id) || p.id === id);
    const checkInTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const watchmanId = payload.watchmanId || 'WM-01';
    const watchmanName = payload.watchmanName || 'Ramasamy (Main Gate Security)';

    if (pass) {
      pass.status = 'APPROVED';
      pass.approvalStatus = 'APPROVED';
      pass.checkInStatus = 'INSIDE_CAMPUS';
      pass.checkInTime = checkInTime;
      pass.verifiedByWatchmanId = watchmanId;
      pass.verifiedByWatchmanName = watchmanName;
      saveStoredPasses(passes);
    }

    // Persist to permanent digital gate logs
    try {
      const rawLogs = localStorage.getItem('campusguard_gatelogs');
      const logs = rawLogs ? JSON.parse(rawLogs) : [];
      logs.unshift({
        id: Date.now(),
        direction: 'IN',
        rollOrId: pass ? (pass.identifier || pass.passNumber) : 'VISITOR',
        personName: pass ? pass.visitorName : 'Visitor',
        category: pass ? pass.visitorType : 'VISITOR',
        purpose: pass ? (pass.reason || pass.additionalDetails || 'Campus Entry') : 'Gate Pass',
        entryTime: checkInTime,
        status: 'APPROVED',
        verifiedBy: `${watchmanName} (${watchmanId})`
      });
      localStorage.setItem('campusguard_gatelogs', JSON.stringify(logs));
    } catch (e) {
      console.warn('Error saving gate log:', e);
    }

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('campusguard_pass_updated', { detail: pass }));
    }

    return {
      success: true,
      message: 'Gate Entry Approved & Barrier Opened!',
      visitorPass: pass
    };
  },

  // Mark pass as pending college policy approval
  async setPassApprovalPending(id, payload = {}) {
    const passes = getStoredPasses();
    const pass = passes.find((p) => p.id === Number(id) || p.id === id);
    if (pass) {
      pass.approvalStatus = 'APPROVAL_PENDING';
      if (payload.policyAlert) pass.policyAlert = payload.policyAlert;
      saveStoredPasses(passes);
    }
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('campusguard_pass_updated', { detail: pass }));
    }
    return { success: true, visitorPass: pass };
  },

  // Reject invalid or unauthorized entry
  async rejectPassEntry(id, payload = {}) {
    const passes = getStoredPasses();
    const pass = passes.find((p) => p.id === Number(id) || p.id === id);
    if (pass) {
      pass.status = 'REJECTED';
      pass.approvalStatus = 'REJECTED';
      pass.checkInStatus = 'REJECTED';
      pass.policyAlert = payload.reason || 'Entry denied by security.';
      saveStoredPasses(passes);
    }
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('campusguard_pass_updated', { detail: pass }));
    }
    return { success: true, visitorPass: pass };
  },

  // Secondary/optional security verification: manual OTP verify
  async verifyVisitorOtp(otp) {
    const cleanOtp = String(otp).trim();
    try {
      const res = await apiClient.post('/visitors/verify-otp', { otp: cleanOtp });
      return res.data;
    } catch (err) {
      if (err.response && err.response.data && err.response.data.error) {
        return { success: false, error: err.response.data.error };
      }

      const passes = getStoredPasses();
      const found = passes.find((p) => String(p.otp).trim() === cleanOtp);

      if (!found) {
        return {
          success: false,
          error: 'Invalid OTP. No visitor pass found with this code.'
        };
      }

      if (found.checkInStatus === 'INSIDE_CAMPUS' || found.status === 'APPROVED') {
        return {
          success: false,
          error: `This OTP (${cleanOtp}) has already been used and verified at ${found.checkInTime || 'earlier'}${found.verifiedByWatchmanName ? ' by ' + found.verifiedByWatchmanName : ''}. Duplicate use is prohibited.`
        };
      }

      if (found.otpExpiresAt && new Date() > new Date(found.otpExpiresAt)) {
        found.status = 'EXPIRED';
        saveStoredPasses(passes);
        return {
          success: false,
          error: 'This Gate Pass OTP has expired (15-minute time limit). Please ask visitor to submit a fresh request.'
        };
      }

      return {
        success: true,
        message: 'OTP Verified Successfully!',
        visitorPass: found
      };
    }
  },

  // Alias for backward compatibility
  async confirmVisitorEntry(id, payload = {}) {
    return this.allowPassEntry(id, payload);
  },

  async getActiveVisitors() {
    try {
      const res = await apiClient.get('/visitors/active');
      return res.data;
    } catch {
      const passes = getStoredPasses();
      return passes.filter((p) => p.status === 'APPROVED' && p.checkInStatus === 'INSIDE_CAMPUS');
    }
  },

  async checkOutVisitorPass(id) {
    try {
      const res = await apiClient.put(`/visitors/${id}/checkout`);
      return res.data;
    } catch {
      const passes = getStoredPasses();
      const pass = passes.find((p) => p.id === Number(id) || p.id === id);
      if (pass) {
        pass.status = 'CHECKED_OUT';
        pass.checkInStatus = 'CHECKED_OUT';
        pass.checkOutTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        saveStoredPasses(passes);
      }
      return { success: true, visitorPass: pass };
    }
  },

  // Legacy visitor creator (backward compatibility)
  async createVisitor(visitor) {
    return this.selfRegisterVisitor({
      visitorType: 'OTHERS',
      visitorName: visitor.visitorName,
      phoneNumber: visitor.phoneNumber,
      reason: visitor.purpose,
      personToMeet: visitor.personToMeet,
      department: visitor.departmentToVisit,
      ...visitor
    });
  },

  // ==========================================
  // SMART DIGITAL SHIFT HANDOVER API
  // ==========================================

  // Feature A & C: Get current active or latest handover
  async getCurrentShiftHandover() {
    try {
      const res = await apiClient.get('/handovers/current');
      if (res.data && res.data.hasActiveHandover) {
        return res.data;
      }
    } catch {}

    const handovers = getStoredHandovers();
    const tasks = getStoredHandoverTasks();

    if (handovers.length === 0) {
      return { hasActiveHandover: false };
    }

    const latest = handovers[0];
    const relatedTasks = tasks.filter((t) => t.handoverCode === latest.handoverCode);

    return {
      hasActiveHandover: true,
      handover: latest,
      tasks: relatedTasks
    };
  },

  // Feature E: Get all handovers for supervisor review
  async getAllShiftHandovers() {
    try {
      const res = await apiClient.get('/handovers/list');
      return res.data;
    } catch {
      return getStoredHandovers();
    }
  },

  // Feature D: Get all unresolved tasks across shifts
  async getUnresolvedHandoverTasks() {
    try {
      const res = await apiClient.get('/handovers/unresolved-tasks');
      return res.data;
    } catch {
      const tasks = getStoredHandoverTasks();
      return tasks.filter((t) => t.status !== 'RESOLVED');
    }
  },

  // Feature B: Auto-detect pending tasks from existing modules (Visitors, Parcels, Incidents, Equipment)
  async generateShiftPendingTasks() {
    const existingTasks = getStoredHandoverTasks();
    const unresolvedExisting = existingTasks.filter((t) => t.status !== 'RESOLVED');
    const detectedTasks = [];

    // 1. Visitors Module: Visitors currently inside campus or awaiting check-in
    try {
      const passes = getStoredPasses();
      const activeInside = passes.filter((p) => p.checkInStatus === 'INSIDE_CAMPUS' || p.status === 'APPROVED');
      activeInside.forEach((v) => {
        const taskCode = `TSK-VIS-${v.id}`;
        if (!existingTasks.some((t) => t.taskCode === taskCode)) {
          detectedTasks.push({
            id: Date.now() + Math.random(),
            taskCode,
            category: 'VISITORS',
            title: `Visitor on Campus: ${v.visitorName} (${v.identifier || v.visitorType})`,
            description: `Admitted at ${v.checkInTime || 'earlier'} for: ${v.reason || 'Campus Visit'}. Dept: ${v.department || 'Campus'}`,
            sourceReferenceId: v.passNumber || `GP-${v.id}`,
            status: 'OPEN',
            priority: v.visitorType === 'STUDENT' ? 'HIGH' : 'MEDIUM',
            nextRequiredAction: 'Verify checkout and badge return when departing Gate 1.',
            createdAt: new Date().toISOString(),
            lastUpdatedAt: new Date().toISOString()
          });
        }
      });
    } catch {}

    // 2. Parcels Module: Parcels waiting at gate desk
    try {
      const rawParcels = localStorage.getItem('campusguard_parcels');
      const parcels = rawParcels ? JSON.parse(rawParcels) : initialMockState.parcels;
      const waitingParcels = parcels.filter((p) => p.status === 'WAITING_COLLECTION');
      waitingParcels.forEach((p) => {
        const taskCode = `TSK-PCL-${p.id}`;
        if (!existingTasks.some((t) => t.taskCode === taskCode)) {
          detectedTasks.push({
            id: Date.now() + Math.random(),
            taskCode,
            category: 'PARCELS',
            title: `Uncollected Parcel: ${p.courierCompany} for ${p.recipientName}`,
            description: `Tracking #${p.trackingNumber}. Destination: ${p.departmentOrHostel}. Handover OTP: ${p.handoverOtp}`,
            sourceReferenceId: p.trackingNumber,
            status: 'OPEN',
            priority: 'MEDIUM',
            nextRequiredAction: `Verify 4-digit handover OTP ${p.handoverOtp} upon collection.`,
            createdAt: new Date().toISOString(),
            lastUpdatedAt: new Date().toISOString()
          });
        }
      });
    } catch {}

    // 3. Incidents & SOS Module
    try {
      const rawSos = localStorage.getItem('campusguard_activesos');
      if (rawSos) {
        const sos = JSON.parse(rawSos);
        const taskCode = `TSK-INC-${sos.id}`;
        if (!existingTasks.some((t) => t.taskCode === taskCode)) {
          detectedTasks.push({
            id: Date.now() + Math.random(),
            taskCode,
            category: 'INCIDENTS',
            title: `Active SOS: ${sos.reason || 'Gate Emergency Alert'}`,
            description: `Triggered at ${sos.time || 'earlier'} by ${sos.reportedBy || 'Security'}. Follow up required.`,
            sourceReferenceId: `SOS-${sos.id}`,
            status: 'IN_PROGRESS',
            priority: 'HIGH',
            nextRequiredAction: 'Ensure incident resolution confirmation with Campus Supervisor.',
            createdAt: new Date().toISOString(),
            lastUpdatedAt: new Date().toISOString()
          });
        }
      }
    } catch {}

    // 4. Equipment Checklist
    if (!existingTasks.some((t) => t.taskCode === 'TSK-EQP-01')) {
      detectedTasks.push({
        id: Date.now() + Math.random(),
        taskCode: 'TSK-EQP-01',
        category: 'EQUIPMENT',
        title: 'Gate 1 Automated Boom Barrier & Sensor Check',
        description: 'Verify optical sensor alignment and test manual bypass key.',
        sourceReferenceId: 'EQP-BOOM-01',
        status: 'OPEN',
        priority: 'MEDIUM',
        nextRequiredAction: 'Conduct 5-cycle barrier test during shift start.',
        createdAt: new Date().toISOString(),
        lastUpdatedAt: new Date().toISOString()
      });
    }
    if (!existingTasks.some((t) => t.taskCode === 'TSK-EQP-02')) {
      detectedTasks.push({
        id: Date.now() + Math.random(),
        taskCode: 'TSK-EQP-02',
        category: 'EQUIPMENT',
        title: 'Walkie-Talkies & Security Torches Inventory',
        description: '4 UHF radios and 2 rechargeable searchlights at gate counter.',
        sourceReferenceId: 'EQP-RADIO-4X',
        status: 'RESOLVED',
        priority: 'LOW',
        nextRequiredAction: 'Keep on charging dock when not on perimeter rounds.',
        createdAt: new Date().toISOString(),
        lastUpdatedAt: new Date().toISOString(),
        resolvedBy: 'Ramasamy (WM-01)',
        resolvedAt: new Date().toISOString(),
        resolutionNotes: 'All 4 radios tested with clear audio.'
      });
    }

    return [...unresolvedExisting, ...detectedTasks];
  },

  // Feature B: Create Handover
  async createShiftHandover(payload) {
    try {
      const res = await apiClient.post('/handovers/create', payload);
      return res.data;
    } catch (err) {
      if (err.response && err.response.data && err.response.data.error) {
        return { success: false, error: err.response.data.error };
      }

      const handovers = getStoredHandovers();
      const existingTasks = getStoredHandoverTasks();

      // Duplicate check: check if an unacknowledged handover already exists
      const existingPending = handovers.find(
        (h) => h.status === 'PENDING_ACKNOWLEDGEMENT' && h.outgoingWatchmanId === payload.outgoingWatchmanId
      );
      if (existingPending) {
        return {
          success: false,
          error: `A pending handover (${existingPending.handoverCode}) is already awaiting acknowledgement from ${existingPending.incomingWatchmanName}.`
        };
      }

      const handoverCode = 'HO-2026-' + Math.floor(1000 + Math.random() * 9000);
      const newHandover = {
        id: Date.now(),
        handoverCode,
        shiftName: payload.shiftName || 'Morning Shift (06:00 AM - 02:00 PM)',
        gateLocation: payload.gateLocation || 'Main Gate 1',
        outgoingWatchmanId: payload.outgoingWatchmanId || 'WM-01',
        outgoingWatchmanName: payload.outgoingWatchmanName || 'Ramasamy (Main Gate Security)',
        incomingWatchmanId: payload.incomingWatchmanId || 'WM-02',
        incomingWatchmanName: payload.incomingWatchmanName || 'Murugan (Gate Guard - Shift B)',
        handoverTime: new Date().toISOString(),
        handoverNotes: payload.handoverNotes || '',
        status: 'PENDING_ACKNOWLEDGEMENT',
        totalPendingTasks: (payload.tasks || []).length,
        unresolvedTasksCount: (payload.tasks || []).filter((t) => t.status !== 'RESOLVED').length,
        supervisorSignedBy: null,
        supervisorSignedAt: null
      };

      // Save/update tasks with this handoverCode
      const updatedTasks = [...existingTasks];
      (payload.tasks || []).forEach((t) => {
        const idx = updatedTasks.findIndex((et) => et.taskCode === t.taskCode);
        if (idx >= 0) {
          updatedTasks[idx] = { ...updatedTasks[idx], ...t, handoverCode, lastUpdatedAt: new Date().toISOString() };
        } else {
          updatedTasks.push({
            ...t,
            handoverCode,
            createdAt: t.createdAt || new Date().toISOString(),
            lastUpdatedAt: new Date().toISOString()
          });
        }
      });

      handovers.unshift(newHandover);
      saveStoredHandovers(handovers);
      saveStoredHandoverTasks(updatedTasks);

      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('campusguard_handover_created', { detail: newHandover }));
      }

      return {
        success: true,
        message: 'Shift Handover created successfully. Awaiting acknowledgement.',
        handover: newHandover
      };
    }
  },

  // Feature C: Incoming Watchman Acknowledges Handover
  async acknowledgeShiftHandover(id, payload = {}) {
    try {
      const res = await apiClient.post(`/handovers/${id}/acknowledge`, payload);
      return res.data;
    } catch {
      const handovers = getStoredHandovers();
      const handover = handovers.find((h) => h.id === Number(id) || h.id === id);

      if (handover) {
        handover.status = 'ACKNOWLEDGED';
        handover.acknowledgedAt = new Date().toISOString();
        handover.acknowledgedByWatchmanId = payload.watchmanId || 'WM-02';
        handover.acknowledgedByWatchmanName = payload.watchmanName || 'Murugan (Gate Guard - Shift B)';
        saveStoredHandovers(handovers);
      }

      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('campusguard_handover_acknowledged', { detail: handover }));
      }

      return {
        success: true,
        message: 'Handover acknowledged! Shift transfer complete. All unresolved tasks remain active.',
        handover
      };
    }
  },

  // Feature D: Update Task Status with History & Audit
  async updateHandoverTaskStatus(taskCode, payload = {}) {
    try {
      const res = await apiClient.put(`/handovers/tasks/${taskCode}/status`, payload);
      return res.data;
    } catch {
      const tasks = getStoredHandoverTasks();
      const task = tasks.find((t) => t.taskCode === taskCode);

      if (task) {
        task.status = payload.status || 'RESOLVED';
        task.lastUpdatedAt = new Date().toISOString();
        if (payload.status === 'RESOLVED') {
          task.resolvedBy = payload.resolvedBy || 'Ramasamy (Main Gate Security)';
          task.resolvedAt = new Date().toISOString();
          task.resolutionNotes = payload.notes || 'Task resolved during duty.';
        }
        saveStoredHandoverTasks(tasks);

        // Update unresolved count on latest handover
        const handovers = getStoredHandovers();
        if (handovers.length > 0) {
          handovers[0].unresolvedTasksCount = tasks.filter((t) => t.status !== 'RESOLVED').length;
          saveStoredHandovers(handovers);
        }
      }

      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('campusguard_task_updated', { detail: task }));
      }

      return {
        success: true,
        task
      };
    }
  },

  // Feature E: Supervisor Sign-off
  async supervisorSignOffHandover(id, payload = {}) {
    try {
      const res = await apiClient.post(`/handovers/${id}/supervisor-signoff`, payload);
      return res.data;
    } catch {
      const handovers = getStoredHandovers();
      const handover = handovers.find((h) => h.id === Number(id) || h.id === id);

      if (handover) {
        handover.supervisorSignedBy = payload.supervisorName || 'Dr. Sundaram (Chief Security Officer)';
        handover.supervisorSignedAt = new Date().toISOString();
        handover.supervisorNotes = payload.supervisorNotes || 'Shift handover verified and approved.';
        handover.status = 'SUPERVISOR_REVIEWED';
        saveStoredHandovers(handovers);
      }

      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('campusguard_handover_updated', { detail: handover }));
      }

      return {
        success: true,
        message: 'Supervisor sign-off recorded.',
        handover
      };
    }
  },

  // Stats
  async getStats() {
    try {
      const res = await apiClient.get('/gate/stats');
      return res.data;
    } catch {
      return initialMockState.stats;
    }
  },

  // ── SmartWatchman AI Pillars Extensions ─────────────────────────
  // Maintenance (Pillar 3)
  async getMaintenanceReports(status) {
    try {
      const res = await apiClient.get('/maintenance/', { params: { status } });
      return res.data;
    } catch {
      return [
        { id: 1, ticket_number: 'MNT-261025-F4A8', category: 'ELECTRICAL', title: 'North Gate Floodlight Not Working', description: 'Short circuit after light rain. Floodlight flickering.', location: 'North Gate Bay 1', urgency: 'HIGH', status: 'IN_PROGRESS', reported_by: 'Ramasamy (Main Gate Security)', created_at: new Date().toISOString() },
        { id: 2, ticket_number: 'MNT-261025-2497', category: 'VOICE_REPORT', title: 'Voice Report: Property Damage at Block B', description: 'Spoken via Voice NLP by Watchman Ramasamy: "Block B-la gate damage irukku, vehicle number TN09CA1234 hit panniduchu."', location: 'Block B', urgency: 'HIGH', status: 'OPEN', reported_by: 'Watchman Ramasamy', created_at: new Date().toISOString() },
        { id: 3, ticket_number: 'MNT-261025-F6D0', category: 'HARDWARE', title: 'North Gate Floodlight Not Working', description: 'Short circuit after light rain. Floodlight flickering.', location: 'North Gate Bay 1', urgency: 'HIGH', status: 'IN_PROGRESS', reported_by: 'Ramasamy (Main Gate Security)', created_at: new Date().toISOString() },
        { id: 4, ticket_number: 'MNT-261025-4933', category: 'HVAC', title: 'AC Not Cooling in Computer Lab', description: 'AC unit not cooling properly. Room temperature high.', location: 'Computer Lab - Block C', urgency: 'MEDIUM', status: 'OPEN', reported_by: 'Faculty (Computer Science)', created_at: new Date().toISOString() },
        { id: 5, ticket_number: 'MNT-261025-A1C7', category: 'GATE_BARRIER', title: 'Gate Barrier Malfunction', description: 'Automatic barrier not opening. Manual check required.', location: 'Main Gate 1', urgency: 'MEDIUM', status: 'IN_PROGRESS', reported_by: 'Security Team', created_at: new Date().toISOString() },
        { id: 6, ticket_number: 'MNT-261025-B8E2', category: 'PLUMBING', title: 'Water Leakage in Library', description: 'Pipe leakage near reading hall. Fixed by maintenance team.', location: 'Library - Ground Floor', urgency: 'LOW', status: 'RESOLVED', reported_by: 'Library Staff', created_at: new Date().toISOString() },
        { id: 7, ticket_number: 'MNT-261025-9910', category: 'VOICE_REPORT', title: 'Voice Report: Property Damage at Block B', description: 'Spoken via Voice NLP by Watchman Ramasamy: "Block B-la gate damage irukku, vehicle number TN09CA1234 hit panniduchu."', location: 'Block B', urgency: 'HIGH', status: 'OPEN', reported_by: 'Watchman Ramasamy', created_at: new Date().toISOString() },
        { id: 8, ticket_number: 'MNT-261025-75DD', category: 'ELECTRICAL', title: 'North Gate Floodlight Not Working', description: 'Short circuit after light rain. Floodlight flickering.', location: 'North Gate Bay 1', urgency: 'HIGH', status: 'IN_PROGRESS', reported_by: 'Ramasamy (Main Gate Security)', created_at: new Date().toISOString() }
      ];
    }
  },

  async createMaintenanceReport(payload) {
    try {
      const res = await apiClient.post('/maintenance/', payload);
      return res.data;
    } catch {
      return { id: Date.now(), ticket_number: `MNT-${Date.now().toString().slice(-6)}`, ...payload, status: 'OPEN', created_at: new Date().toISOString() };
    }
  },

  async updateMaintenanceStatus(id, payload) {
    try {
      const res = await apiClient.patch(`/maintenance/${id}/status`, payload);
      return res.data;
    } catch {
      return { id, ...payload, resolved_at: payload.status === 'RESOLVED' ? new Date().toISOString() : null };
    }
  },

  // Parking (Pillar 6)
  async getParkingSlots(zone) {
    try {
      const res = await apiClient.get('/parking/slots', { params: { zone } });
      return res.data;
    } catch {
      return [
        { id: 1, slot_code: 'ST-01', zone: 'STAFF', slot_type: 'FOUR_WHEELER', is_occupied: true, vehicle_number: 'TN09CA1234', driver_name: 'Dr. Sundaram (Principal)', is_unauthorized: false, last_updated: new Date().toISOString() },
        { id: 2, slot_code: 'ST-02', zone: 'STAFF', slot_type: 'FOUR_WHEELER', is_occupied: false, vehicle_number: null, is_unauthorized: false, last_updated: new Date().toISOString() },
        { id: 3, slot_code: 'A-01', zone: 'ZONE_A', slot_type: 'FOUR_WHEELER', is_occupied: true, vehicle_number: 'KA01MJ7766', driver_name: 'Unknown Visitor', is_unauthorized: true, last_updated: new Date().toISOString() },
        { id: 4, slot_code: 'A-02', zone: 'ZONE_A', slot_type: 'EV_CHARGING', is_occupied: false, vehicle_number: null, is_unauthorized: false, last_updated: new Date().toISOString() },
        { id: 5, slot_code: 'TW-01', zone: 'ZONE_B', slot_type: 'TWO_WHEELER', is_occupied: true, vehicle_number: 'TN11Q1122', driver_name: 'Student Rep', is_unauthorized: false, last_updated: new Date().toISOString() }
      ];
    }
  },

  async getParkingSummary() {
    try {
      const res = await apiClient.get('/parking/summary');
      return res.data;
    } catch {
      return { total_slots: 24, occupied_slots: 15, available_slots: 9, unauthorized_count: 1 };
    }
  },

  async occupyParkingSlot(id, payload) {
    try {
      const res = await apiClient.post(`/parking/slots/${id}/occupy`, payload);
      return res.data;
    } catch {
      return { id, ...payload, is_occupied: true, last_updated: new Date().toISOString() };
    }
  },

  async vacateParkingSlot(id) {
    try {
      const res = await apiClient.post(`/parking/slots/${id}/vacate`);
      return res.data;
    } catch {
      return { id, is_occupied: false, vehicle_number: null, last_updated: new Date().toISOString() };
    }
  },

  // Patrol Checkpoints (Pillar 10)
  async getPatrolCheckpoints() {
    try {
      const res = await apiClient.get('/patrol/checkpoints');
      return res.data;
    } catch {
      return [
        { id: 1, checkpoint_code: 'CP-GATE', name: 'Main Gate & Visitor Bay', zone: 'ZONE_GATE', location_description: 'Barrier post & ANPR camera lens', qr_token: 'QR-GATE-7701', order_seq: 1, is_active: true },
        { id: 2, checkpoint_code: 'CP-PARK', name: 'Faculty & Visitor Parking Lot', zone: 'ZONE_PARKING', location_description: 'Perimeter fence & illumination posts', qr_token: 'QR-PARK-7702', order_seq: 2, is_active: true },
        { id: 3, checkpoint_code: 'CP-LABS', name: 'Engineering Research Labs', zone: 'ZONE_LABS', location_description: 'Ground floor mechanical labs & hazardous store', qr_token: 'QR-LABS-7703', order_seq: 3, is_active: true },
        { id: 4, checkpoint_code: 'CP-LIB', name: 'Central University Library', zone: 'ZONE_LIBRARY', location_description: 'Library rear fire exit & server room', qr_token: 'QR-LIB-7704', order_seq: 4, is_active: true }
      ];
    }
  },

  async getPatrolStatus() {
    try {
      const res = await apiClient.get('/patrol/status');
      return res.data;
    } catch {
      return { total_checkpoints: 4, completed_today: 8, missed_count: 0, next_due_checkpoint: 'Faculty & Visitor Parking Lot', next_due_time: 'In 25 mins' };
    }
  },

  async scanPatrolCheckpoint(payload) {
    try {
      const res = await apiClient.post('/patrol/scan', payload);
      return res.data;
    } catch {
      return { id: Date.now(), ...payload, status: 'COMPLETED', scanned_at: new Date().toISOString() };
    }
  },

  // Lost and Found (Pillar 9)
  async getLostItems(status) {
    try {
      const res = await apiClient.get('/lost-found/lost', { params: { status } });
      return res.data;
    } catch {
      return [
        { id: 1, item_name: 'Blue Dell Laptop Pouch', category: 'ELECTRONICS', description: 'With 65W power adapter', lost_location: 'Central Library 2nd Floor', date_lost: new Date().toISOString(), reported_by_name: 'Vigneshwaran K', contact_phone: '+91 98456 12342', status: 'LOST' }
      ];
    }
  },

  async getFoundItems(status) {
    try {
      const res = await apiClient.get('/lost-found/found', { params: { status } });
      return res.data;
    } catch {
      return [
        { id: 1, item_code: 'FND-8821A', item_name: 'Dell Laptop Charger 65W', category: 'ELECTRONICS', description: 'Black adapter found near library table 14', found_location: 'Library Table 14', found_at: new Date().toISOString(), stored_at: 'Main Gate Locker #3', status: 'UNCLAIMED' }
      ];
    }
  },

  async reportLostItem(payload) {
    try {
      const res = await apiClient.post('/lost-found/lost', payload);
      return res.data;
    } catch {
      return { id: Date.now(), ...payload, status: 'LOST', date_lost: new Date().toISOString() };
    }
  },

  async registerFoundItem(payload) {
    try {
      const res = await apiClient.post('/lost-found/found', payload);
      return res.data;
    } catch {
      return { id: Date.now(), item_code: `FND-${Date.now().toString().slice(-5)}`, ...payload, status: 'UNCLAIMED', found_at: new Date().toISOString() };
    }
  },

  async claimFoundItem(id, payload) {
    try {
      const res = await apiClient.post(`/lost-found/found/${id}/claim`, payload);
      return res.data;
    } catch {
      return { id, ...payload, status: 'RETURNED', returned_at: new Date().toISOString() };
    }
  },

  async getSmartItemMatches() {
    try {
      const res = await apiClient.get('/lost-found/matches');
      return res.data;
    } catch {
      return [
        { lost_id: 1, found_id: 1, item_name: 'Blue Dell Laptop Pouch ≈ Dell Laptop Charger', category: 'ELECTRONICS', confidence_score: 0.94, suggested_action: 'Notify student Vigneshwaran K (+91 98456 12342) to inspect Locker #3' }
      ];
    }
  },

  // Duty Attendance & Work Log (Pillar 7)
  async clockInDuty(payload) {
    try {
      const res = await apiClient.post('/duty/clock-in', payload);
      return res.data;
    } catch {
      return { id: Date.now(), ...payload, clock_in: new Date().toISOString(), is_active: true, total_patrols_done: 3, total_incidents_handled: 0 };
    }
  },

  async clockOutDuty(payload) {
    try {
      const res = await apiClient.post('/duty/clock-out', payload);
      return res.data;
    } catch {
      return { id: 1, ...payload, clock_out: new Date().toISOString(), is_active: false };
    }
  },

  async getCurrentDuty(guardId) {
    try {
      const res = await apiClient.get(`/duty/current/${guardId}`);
      return res.data;
    } catch {
      return { guard_id: guardId, guard_name: 'Ramasamy (Main Gate Security)', shift_name: 'Morning Shift (06:00 AM - 02:00 PM)', gate_assigned: 'Main Campus Gate', clock_in: new Date(Date.now() - 4 * 3600000).toISOString(), is_active: true, total_patrols_done: 4, total_incidents_handled: 1 };
    }
  },

  // Zone Risk & Weather Alerts (Pillars 8 & 11)
  async getZoneMonitoring() {
    try {
      const res = await apiClient.get('/zone-risk/zones');
      return res.data;
    } catch {
      return [
        { id: 1, zone_code: 'ZONE_PARKING', zone_name: 'North Campus Parking Lot', risk_level: 'HIGH', repeated_complaints_count: 4, attention_needed: true, recommendation: 'Drainage waterlogging advisory. Inspect storm drains every 45 minutes.', weather_hazard: 'Waterlogging Risk', last_inspected_at: new Date().toISOString() },
        { id: 2, zone_code: 'ZONE_GATE', zone_name: 'Main Gate & Perimeter Barrier', risk_level: 'LOW', repeated_complaints_count: 0, attention_needed: false, recommendation: 'All ANPR cameras and RFID sensors optimal.', weather_hazard: 'Normal', last_inspected_at: new Date().toISOString() },
        { id: 3, zone_code: 'ZONE_HOSTEL', zone_name: 'Hostel Rear Complex & Sports Ground', risk_level: 'MODERATE', repeated_complaints_count: 2, attention_needed: true, recommendation: 'Overdue curfew checks; increase night perimeter sweep.', weather_hazard: 'Normal', last_inspected_at: new Date().toISOString() }
      ];
    }
  },

  async inspectZone(zoneId, resolvedIssues = false) {
    try {
      const res = await apiClient.post(`/zone-risk/zones/${zoneId}/inspect`, null, { params: { resolved_issues: resolvedIssues } });
      return res.data;
    } catch {
      return { id: zoneId, last_inspected_at: new Date().toISOString(), attention_needed: false, risk_level: 'LOW' };
    }
  },

  async getWeatherTelemetry() {
    try {
      const res = await apiClient.get('/zone-risk/weather-telemetry');
      return res.data;
    } catch {
      return {
        temperature_celsius: 27.4,
        condition: 'Monsoon Rain Warning',
        rainfall_probability: 85,
        wind_speed_kmh: 34.2,
        hazard_level: 'WARNING',
        hazard_title: 'Heavy Monsoon Precipitation & Waterlogging Alert',
        affected_zones: ['Open North Parking Lot', 'Main Gate Drainage Canal', 'Hostel Rear Perimeter Gate'],
        safety_checklist: [
          'Inspect North Parking drains to prevent vehicle water submersion.',
          'Verify CCTV camera lens weather-shielding at Main Gate.',
          'Ensure emergency solar lanterns and raincoats are issued at Watchman Kiosk.',
          'Double-check emergency contact numbers for PWD and campus electrician.'
        ]
      };
    }
  },

  // ── Cognitive AI Guard Co-Pilot (Phase 2) ─────────────────────────
  async recordSituationCard(payload) {
    try {
      const res = await apiClient.post('/copilot/situation', payload);
      return res.data;
    } catch {
      return { id: Date.now(), ...payload, recorded_at: new Date().toISOString(), pattern_alert_triggered: payload.status === 'SUSPICIOUS' || payload.status === 'EMERGENCY' };
    }
  },

  async getSituationPatternAlerts() {
    try {
      const res = await apiClient.get('/copilot/situation/patterns');
      return res.data;
    } catch {
      return [
        { location: 'North Parking Bay', count_today: 3, current_status: 'SUSPICIOUS', alert_message: '⚠️ North Parking Bay – Situation Changed 3 Times Today. Early Inspection Recommended.', last_updated: new Date().toISOString() }
      ];
    }
  },

  async getLatestSituations() {
    try {
      const res = await apiClient.get('/copilot/situation/latest');
      return res.data;
    } catch {
      return [
        { id: 1, location: 'North Parking Bay', status: 'ATTENTION_NEEDED', notes: 'Loose boundary fence', recorded_by: 'Ramasamy', recorded_at: new Date(Date.now() - 3600000).toISOString() },
        { id: 2, location: 'Main Gate Ingress', status: 'NORMAL', notes: 'Smooth vehicle flow', recorded_by: 'Ramasamy', recorded_at: new Date(Date.now() - 7200000).toISOString() }
      ];
    }
  },

  async sendVoiceIncident(payload) {
    try {
      const res = await apiClient.post('/copilot/voice-incident', payload);
      return res.data;
    } catch {
      const isVeh = payload.transcript.includes('TN') || payload.transcript.includes('vehicle');
      return {
        ticket_number: `MNT-${Date.now().toString().slice(-6)}`,
        incident_type: 'GATE_BARRIER_DAMAGE',
        category: 'GATE_BARRIER',
        location: 'Block B Entrance',
        urgency: 'HIGH',
        detected_vehicle: isVeh ? 'TN09CA1234' : null,
        description: `Spoken via Voice NLP: "${payload.transcript}"`,
        raw_transcript: payload.transcript,
        automated_actions: ['Created Maintenance Ticket', 'Dispatched automated alert to Facility Team']
      };
    }
  },

  async getPrioritizedTasks() {
    try {
      const res = await apiClient.get('/copilot/tasks/prioritized');
      return res.data;
    } catch {
      return {
        do_first: [
          { id: 'PARK-1', title: 'Unauthorized Vehicle in Slot A-03', task_type: 'UNAUTHORIZED_PARKING', priority_bucket: 'DO_FIRST', location: 'Zone A Parking', urgency_level: 'CRITICAL', suggested_action: 'Clamp vehicle or contact driver', created_at: '10:45 AM' },
          { id: 'MNT-1', title: 'North Gate Barrier Sensor Malfunction', task_type: 'CRITICAL_MAINTENANCE', priority_bucket: 'DO_FIRST', location: 'North Gate', urgency_level: 'HIGH', suggested_action: 'Dispatch technician', created_at: '11:15 AM' }
        ],
        do_next: [
          { id: 'OUT-101', title: 'Curfew Overdue: Student 22CS101 (Karthik)', task_type: 'OVERDUE_OUTPASS', priority_bucket: 'DO_NEXT', location: 'Campus Gate', urgency_level: 'HIGH', suggested_action: 'Call hostel warden', created_at: '11:30 AM' },
          { id: 'MNT-2', title: 'Drainage Clog near Bay 2', task_type: 'GATE_DEFECT', priority_bucket: 'DO_NEXT', location: 'North Parking', urgency_level: 'MEDIUM', suggested_action: 'Inspect drain', created_at: '09:00 AM' }
        ],
        routine: [
          { id: 'PATROL-1', title: 'Scheduled Round: Engineering Labs', task_type: 'PATROL_DUE', priority_bucket: 'ROUTINE', location: 'ZONE_LABS', urgency_level: 'LOW', suggested_action: 'Scan QR Checkpoint', created_at: '12:00 PM' },
          { id: 'PARCEL-1', title: '3 Deliveries in Gate Locker', task_type: 'PARCEL_WAITING', priority_bucket: 'ROUTINE', location: 'Main Gate', urgency_level: 'LOW', suggested_action: 'Student ID pickup', created_at: '10:00 AM' }
        ],
        total_active_count: 6
      };
    }
  },

  async getCarryForwardTasks() {
    try {
      const res = await apiClient.get('/copilot/carry-forward');
      return res.data;
    } catch {
      return {
        has_carry_forward: true,
        total_pending: 2,
        previous_shift_guard: 'Murugan (Shift B)',
        pending_tasks: [
          { id: 'MNT-1', task_name: 'Main Gate Barrier Sensor Flickering', category: 'MAINTENANCE', shift_origin: 'Shift B (Night)', urgency: 'HIGH', status: 'OPEN', description: 'Sensor sometimes misses low clearance vehicles.' },
          { id: 'HT-2', task_name: 'Follow up on Uncollected Laptop Parcel #4412', category: 'PARCELS', shift_origin: 'Shift B (Night)', urgency: 'MEDIUM', status: 'PENDING', description: 'Student promised to collect at 09:00 AM.' }
        ]
      };
    }
  },

  async getSectorProfiles() {
    try {
      const res = await apiClient.get('/copilot/sectors');
      return res.data;
    } catch {
      return [
        {
          sector_id: 'COLLEGE',
          name: 'Higher Education & Campus',
          icon: 'GraduationCap',
          description: 'Engineered for universities, engineering colleges, and residential schools with active student, faculty, and parent traffic.',
          primary_entity: 'Students & Faculty Members',
          gate_pass_name: 'Student Digital Outpass',
          key_workflows: [
            'Hosteler Late-Entry Curfew Enforcement',
            'Parent/Guardian OTP Pickup Verification',
            'Campus Bus Fleet Ingress & Boarding Validation',
            'Laboratory Equipment Inter-Dept Transfer'
          ],
          compliance_rules: [
            'Curfew cutoff strictly locked at 08:30 PM',
            'Unaccompanied visitor requires Faculty Host approval',
            'Day-scholar late arrival (>09:00 AM) auto-reported to HOD'
          ],
          stat_labels: {
            primary_count: 'Enrolled Students on Campus',
            movement_count: 'Active Outpasses',
            overdue_count: 'Curfew Violations'
          },
          sample_pass_preview: {
            pass_type: 'Student Gate Pass',
            holder: 'Karthik Subramanian (22CS101)',
            destination: 'Hardware Tech Exhibition',
            valid_until: '08:30 PM Today',
            verification: 'HOD + Warden Digital Sign-off'
          }
        },
        {
          sector_id: 'FACTORY',
          name: 'Industrial Manufacturing & Logistics Hub',
          icon: 'Factory',
          description: 'Designed for factories, processing plants, and warehouses managing material dispatch, contract laborers, and heavy commercial vehicles.',
          primary_entity: 'Contract Workers & Freight Trucks',
          gate_pass_name: 'Material Gate Pass (RGP / NRGP)',
          key_workflows: [
            'Returnable Gate Pass (RGP) Tracking & Expiry Alerts',
            'Non-Returnable (NRGP) Finished Goods Dispatch Clearance',
            'Weighbridge Gross/Tare Weight Recording & Hazmat Inspection',
            'Daily Contract Labor Biometric Shift Muster'
          ],
          compliance_rules: [
            'No commercial vehicle departs without verified Store Manager digital stamp',
            'Mandatory PPE helmet & high-vis safety jacket gate check',
            'Flammable / chemical carrier hazmat documentation audit'
          ],
          stat_labels: {
            primary_count: 'Contract Laborers On-Site',
            movement_count: 'Active Commercial Vehicles',
            overdue_count: 'Pending Material RGPs'
          },
          sample_pass_preview: {
            pass_type: 'Returnable Gate Pass (RGP-9042)',
            holder: 'CNC Lathe Motor for Rewinding',
            destination: 'Apex Precision Services, Ambattur',
            valid_until: '48 Hours (Return Expected)',
            verification: 'Plant Head + QC Approved'
          }
        },
        {
          sector_id: 'HOSPITAL',
          name: 'Healthcare Facility & Medical Hub',
          icon: 'HeartPulse',
          description: 'Specialized for multi-specialty hospitals, emergency centers, and clinical facilities requiring 24/7 uninterrupted patient care and visitor restrictions.',
          primary_entity: 'Patients, Attendants & Medical Staff',
          gate_pass_name: 'Patient Attendant 24/7 Gate Badge',
          key_workflows: [
            'Emergency Ambulance Green Corridor Instant Barrier Clearance',
            'ICU / NICU Restrictive Visitor Pass Limitation (Max 1 Attendant)',
            'Bio-Hazardous Medical Waste Pickup Tracking',
            'Doctor / Specialist Priority Parking & Emergency Bay'
          ],
          compliance_rules: [
            'Ambulance sirens grant instant automatic barrier opening within 2 seconds',
            'Visiting hours (04:00 PM - 07:00 PM) strictly enforced for general wards',
            'No visitor entry to sterile zones without sanitization badge'
          ],
          stat_labels: {
            primary_count: 'Active In-Patients / Visitors',
            movement_count: 'Ambulance Ingress Today',
            overdue_count: 'Expired Attendant Passes'
          },
          sample_pass_preview: {
            pass_type: 'ICU Attendant Gate Badge',
            holder: 'Attendant: Meena R. (Pt. ID #4421 - Bed 302)',
            destination: '3rd Floor Cardiac ICU',
            valid_until: 'Discharge Date',
            verification: 'Duty Resident Doctor Badge'
          }
        },
        {
          sector_id: 'OFFICE',
          name: 'Corporate Tech Park & IT Facility',
          icon: 'Building2',
          description: 'Optimized for IT enterprises, corporate towers, and SEZs with strict confidentiality, client visits, and vendor NDAs.',
          primary_entity: 'Employees, Vendors & Client Guests',
          gate_pass_name: 'Vendor / Guest Visitor Badge',
          key_workflows: [
            'Pre-Scheduled QR Code Self-Check-in Kiosk',
            'Server Room & R&D Lab Escorted Security Access',
            'Contractor Laptop Serial Number & Asset Ingress Tagging',
            'Courier & E-Commerce Centralized Mailroom Ingestion'
          ],
          compliance_rules: [
            'Host employee must accept push notification before visitor badge prints',
            'Photography strictly prohibited sticker applied on visitor cameras',
            'Client NDA acknowledgment required during kiosk registration'
          ],
          stat_labels: {
            primary_count: 'Badged Employees Inside',
            movement_count: 'Registered Guests Today',
            overdue_count: 'Unreturned Visitor Badges'
          },
          sample_pass_preview: {
            pass_type: 'Client Executive Day Pass',
            holder: 'Sunil Nair (AWS Enterprise Architect)',
            destination: 'Tower B, Level 6 Cloud Center',
            valid_until: '06:00 PM Today',
            verification: 'Host: VP Engineering Approved'
          }
        },
        {
          sector_id: 'SOCIETY',
          name: 'Gated Residential Community & Township',
          icon: 'Home',
          description: 'Tailored for apartment complexes, villa communities, and townships prioritizing resident privacy, domestic staff logging, and parcel safety.',
          primary_entity: 'Residents, Domestic Staff & Delivery Drivers',
          gate_pass_name: 'Resident Guest Pass / Daily Help Entry',
          key_workflows: [
            'Resident In-App 1-Tap Entry Approval (Call / Notification)',
            'Maid, Cook, and Driver Daily Passcode Check-in',
            'Contactless Delivery Drop-off at Guard Parcel Locker',
            'Intercom Verification for Unannounced Visitors'
          ],
          compliance_rules: [
            'Delivery agents restricted to clubhouse parcel holding bay after 09:00 PM',
            'Commercial vehicles prohibited from parking in resident basement bays',
            'Late night loud music / construction complaints logged directly to security'
          ],
          stat_labels: {
            primary_count: 'Occupied Apartments',
            movement_count: 'Daily Domestic Staff Present',
            overdue_count: 'Unclaimed Parcels'
          },
          sample_pass_preview: {
            pass_type: 'Resident Visitor Pass',
            holder: 'Anand Mohan (Guest for Flat A-402)',
            destination: 'Tower A, Flat 402',
            valid_until: 'Midnight Today',
            verification: 'Resident 1-Tap App Approval'
          }
        }
      ];
    }
  },

  async getGateCongestionAnalytics() {
    try {
      const res = await apiClient.get('/copilot/analytics/congestion');
      return res.data;
    } catch {
      return {
        current_ingress_rate_per_hour: 380,
        current_egress_rate_per_hour: 45,
        peak_hours: ['08:00 AM - 09:30 AM (Morning Rush)', '04:30 PM - 05:45 PM (Dispersal)'],
        congestion_level: 'MODERATE',
        active_lanes: 2,
        recommended_lanes: 3,
        staffing_forecast: 'Deploy 1 additional reserve watchman to Main Gate 1 during 08:00-09:30 AM window to maintain sub-4s clearance.',
        automation_efficiency_boost: '92.8% clearance time reduction vs manual register',
        avg_processing_time_anpr_sec: 3.2,
        avg_processing_time_manual_sec: 45.0,
        hourly_distribution: [
          { hour: '06:00 AM', inflow: 42, outflow: 8, avg_clearance_seconds: 3.1 },
          { hour: '07:00 AM', inflow: 95, outflow: 18, avg_clearance_seconds: 3.4 },
          { hour: '08:00 AM', inflow: 380, outflow: 45, avg_clearance_seconds: 4.2 },
          { hour: '09:00 AM', inflow: 410, outflow: 62, avg_clearance_seconds: 4.6 },
          { hour: '10:00 AM', inflow: 110, outflow: 78, avg_clearance_seconds: 3.2 },
          { hour: '11:00 AM', inflow: 85, outflow: 92, avg_clearance_seconds: 3.0 },
          { hour: '12:00 PM', inflow: 120, outflow: 145, avg_clearance_seconds: 3.3 },
          { hour: '01:00 PM', inflow: 150, outflow: 160, avg_clearance_seconds: 3.5 },
          { hour: '02:00 PM', inflow: 75, outflow: 90, avg_clearance_seconds: 3.0 },
          { hour: '03:00 PM', inflow: 95, outflow: 110, avg_clearance_seconds: 3.1 },
          { hour: '04:00 PM', inflow: 115, outflow: 310, avg_clearance_seconds: 3.9 },
          { hour: '05:00 PM', inflow: 82, outflow: 395, avg_clearance_seconds: 4.4 },
          { hour: '06:00 PM', inflow: 65, outflow: 220, avg_clearance_seconds: 3.5 },
          { hour: '07:00 PM', inflow: 45, outflow: 85, avg_clearance_seconds: 3.0 },
          { hour: '08:00 PM', inflow: 35, outflow: 40, avg_clearance_seconds: 3.0 }
        ]
      };
    }
  },

  // ── GuardMate Multi-Tenant Enterprise Platform Methods ──────────────────
  async registerOrganization(data) {
    const res = await apiClient.post('/organizations/register', data);
    return res.data;
  },

  async getSupportedOrgTypes() {
    try {
      const res = await apiClient.get('/organizations/types');
      return res.data;
    } catch {
      return [
        { type: "COLLEGE", title: "College & University Campuses", icon: "🎓", tagline: "Campus Curfew & Out-Pass Security" },
        { type: "HOSPITAL", title: "Hospitals & Healthcare Facilities", icon: "🏥", tagline: "Emergency Ambulance Bay & Ward Security" },
        { type: "APARTMENT", title: "Gated Communities & Residential Towers", icon: "🏢", tagline: "Courier Desk & Intercom Approvals" },
        { type: "FACTORY", title: "Industrial Plants & Warehouses", icon: "🏭", tagline: "Material RGP & Weighbridge Audit" },
        { type: "OFFICE", title: "Corporate Tech Parks & High-Rises", icon: "🏛️", tagline: "Turnstile Badges & NDA Kiosks" }
      ];
    }
  },

  async getSuperAdminOrganizations(statusFilter) {
    const url = statusFilter ? `/super-admin/organizations?status=${statusFilter}` : '/super-admin/organizations';
    const res = await apiClient.get(url);
    return res.data;
  },

  async approveOrganization(orgId, data = {}) {
    const res = await apiClient.post(`/super-admin/organizations/${orgId}/approve`, data);
    return res.data;
  },

  async rejectOrganization(orgId, reason) {
    const res = await apiClient.post(`/super-admin/organizations/${orgId}/reject`, { reason });
    return res.data;
  },

  async getTenantSetup() {
    const res = await apiClient.get('/tenant/setup');
    return res.data;
  },

  async addTenantGate(gateData) {
    const res = await apiClient.post('/tenant/gates', gateData);
    return res.data;
  },

  async addTenantShift(shiftData) {
    const res = await apiClient.post('/tenant/shifts', shiftData);
    return res.data;
  },

  async getTenantGuards() {
    const res = await apiClient.get('/tenant/guards');
    return res.data;
  },

  async createTenantGuard(guardData) {
    const res = await apiClient.post('/tenant/guards', guardData);
    return res.data;
  },

  async getTenantTelemetry() {
    const res = await apiClient.get('/tenant/telemetry');
    return res.data;
  },

  async getWatchmanAdaptiveProfile() {
    const res = await apiClient.get('/watchman/profile');
    return res.data;
  },

  async reportSecurityIncident(incidentData) {
    const res = await apiClient.post('/watchman/incidents', incidentData);
    return res.data;
  },

  async getSecurityIncidents() {
    const res = await apiClient.get('/watchman/incidents');
    return res.data;
  }
};

export default apiClient;

