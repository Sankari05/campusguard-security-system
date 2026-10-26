import React, { useState, useEffect } from "react";

// URL of the Face Recognition / EduTrack Central Backend (Port 8000)
const API_BASE = "http://localhost:8000";

export default function StudentGatePassVerify() {
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [recentExits, setRecentExits] = useState([]);
  const [exitLoading, setExitLoading] = useState(false);

  // Fetch recent exits when component mounts
  useEffect(() => {
    fetchRecentExits();
  }, []);

  const fetchRecentExits = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/recent-exits`);
      const data = await res.json();
      if (data && data.exits) {
        setRecentExits(data.exits);
      }
    } catch (err) {
      console.warn("Could not load recent exits:", err);
    }
  };

  const handleVerify = async (e) => {
    if (e) e.preventDefault();
    const cleanOtp = otp.trim();
    if (!cleanOtp) {
      setErrorMsg("Please enter the 6-digit OTP told by the student.");
      return;
    }

    setLoading(true);
    setErrorMsg("");
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ otp: cleanOtp }),
      });
      const data = await res.json();

      if (!res.ok) {
        setErrorMsg(data.detail || "Verification failed on server.");
      } else {
        setResult(data);
        if (!data.valid) {
          setErrorMsg(data.message || "Invalid or Unapproved Gate Pass.");
        }
      }
    } catch (err) {
      setErrorMsg("Could not connect to EduTrack API (http://localhost:8000). Ensure EduTrack server is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmExit = async () => {
    if (!result || !result.pass_id) return;
    setExitLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/mark-exit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pass_id: result.pass_id,
          guard_id: "Main Gate Guard",
          remarks: "Verified via OTP & allowed exit",
        }),
      });
      const data = await res.json();
      if (data.success) {
        alert(`✅ Student exit logged successfully for ${result.student_name}!`);
        setResult(null);
        setOtp("");
        fetchRecentExits();
      } else {
        alert("Failed to mark exit: " + (data.message || "Unknown error"));
      }
    } catch (err) {
      alert("Error contacting server: " + err.message);
    } finally {
      setExitLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={styles.shieldIcon}>🛡️</div>
          <div>
            <h1 style={styles.title}>Main Gate · Student Pass Verification</h1>
            <p style={styles.subtitle}>
              Verify student Gate Pass OTP and grant departure authorization.
            </p>
          </div>
        </div>
      </div>

      <div style={styles.grid}>
        {/* Left Column: Verification Form & Results */}
        <div style={styles.mainCol}>
          {/* OTP Input Card */}
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>🔑 Enter Student OTP or Scan QR</h3>
            <form onSubmit={handleVerify} style={{ marginTop: "14px" }}>
              <div style={styles.inputGroup}>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="e.g. 745743"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  style={styles.otpInput}
                  autoFocus
                />
                <button
                  type="submit"
                  disabled={loading || !otp}
                  style={{
                    ...styles.verifyBtn,
                    opacity: loading || !otp ? 0.6 : 1,
                  }}
                >
                  {loading ? "Checking..." : "Verify Gate Pass"}
                </button>
              </div>
              <p style={styles.hint}>
                Student gets this 6-digit OTP on their Student Portal once HOD & Class Incharge approve.
              </p>
            </form>

            {/* Error Message */}
            {errorMsg && (
              <div style={styles.errorBox}>
                <span style={{ fontSize: "1.2rem", marginRight: "8px" }}>⚠️</span>
                <span>{errorMsg}</span>
              </div>
            )}
          </div>

          {/* Verification Result: GRANTED */}
          {result && result.valid && (
            <div style={styles.successCard}>
              <div style={styles.successBanner}>
                <span>✅ GATE PASS APPROVED — ALLOW EXIT</span>
              </div>

              <div style={styles.profileSection}>
                {/* Student Photo */}
                <div style={styles.photoWrap}>
                  <img
                    src={`${API_BASE}${result.avatar_url}`}
                    alt={result.student_name}
                    style={styles.avatarImg}
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.src = "https://ui-avatars.com/api/?name=" + encodeURIComponent(result.student_name) + "&background=0D9488&color=fff&size=128";
                    }}
                  />
                  <span style={styles.verifiedBadge}>Verified ID</span>
                </div>

                {/* Student Details */}
                <div style={{ flex: 1 }}>
                  <h2 style={styles.studentName}>{result.student_name}</h2>
                  <div style={styles.studentReg}>Register No: <strong>{result.register_number || result.student_id}</strong></div>
                  <div style={styles.metaRow}>
                    <span style={styles.metaBadge}>Dept: {result.department}</span>
                    <span style={styles.metaBadge}>Pass Type: {result.pass_type}</span>
                    <span style={styles.metaBadge}>Out Time: {result.out_time}</span>
                  </div>
                  <div style={styles.reasonBox}>
                    <strong>Reason for Exit:</strong> {result.reason}
                  </div>
                </div>
              </div>

              {/* Approval Info */}
              <div style={styles.approvalGrid}>
                <div style={styles.approvalBox}>
                  <div style={styles.apprTitle}>Class Incharge Approval</div>
                  <div style={styles.apprName}>✓ {result.faculty_name || "Faculty Incharge"}</div>
                  <div style={styles.apprTime}>{result.faculty_time || "Approved"}</div>
                </div>
                <div style={styles.approvalBox}>
                  <div style={styles.apprTitle}>Final HOD Approval</div>
                  <div style={styles.apprName}>✓ {result.hod_name || "Head of Department"}</div>
                  <div style={styles.apprTime}>{result.hod_time || "Approved"}</div>
                </div>
              </div>

              {/* Action Button: Confirm Exit */}
              <div style={{ marginTop: "20px", textAlign: "right" }}>
                <button
                  type="button"
                  onClick={handleConfirmExit}
                  disabled={exitLoading}
                  style={styles.exitBtn}
                >
                  {exitLoading ? "Recording Exit..." : "🚪 Confirm Exit & Open Gate"}
                </button>
              </div>
            </div>
          )}

          {/* Verification Result: DENIED */}
          {result && !result.valid && (
            <div style={styles.deniedCard}>
              <div style={styles.deniedBanner}>
                <span>⛔ PERMISSION DENIED — DO NOT ALLOW EXIT</span>
              </div>
              <p style={{ marginTop: "14px", fontSize: "1rem", color: "#991b1b" }}>
                <strong>Reason:</strong> {result.message}
              </p>
              {result.student_name && (
                <p style={{ color: "#7f1d1d", fontSize: "0.88rem", marginTop: "6px" }}>
                  Student: {result.student_name} ({result.register_number})
                </p>
              )}
              <div style={styles.deniedInstruction}>
                Instruct student to return to class or check their approval status with Class Incharge / HOD.
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Recent Gate Exits */}
        <div style={styles.sideCol}>
          <div style={styles.card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={styles.cardTitle}>📋 Recent Departures</h3>
              <button onClick={fetchRecentExits} style={styles.refreshBtn}>↻ Refresh</button>
            </div>

            <div style={{ marginTop: "12px", maxHeight: "450px", overflowY: "auto" }}>
              {recentExits.length === 0 ? (
                <p style={{ color: "#9ca3af", fontSize: "0.85rem", textAlign: "center", padding: "20px 0" }}>
                  No exits logged today yet.
                </p>
              ) : (
                recentExits.map((item) => (
                  <div key={item.id} style={styles.exitRow}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "0.88rem", color: "#1f2937" }}>
                        {item.name || item.student_id}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                        {item.register_number} · {item.department}
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span style={styles.exitBadge}>EXITED</span>
                      <div style={{ fontSize: "0.72rem", color: "#4b5563", marginTop: "2px" }}>
                        {item.exited_at ? (item.exited_at.split("T")[1] || item.exited_at) : "Done"}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Visual Styles ──────────────────────────────────────────
const styles = {
  container: {
    padding: "24px 32px",
    background: "#f8fafc",
    minHeight: "100vh",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  },
  header: {
    marginBottom: "24px",
  },
  shieldIcon: {
    width: "48px",
    height: "48px",
    borderRadius: "12px",
    background: "#0284c7",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "24px",
    boxShadow: "0 4px 12px rgba(2,132,199,0.25)",
  },
  title: {
    fontSize: "1.5rem",
    fontWeight: 800,
    color: "#0f172a",
    margin: 0,
  },
  subtitle: {
    fontSize: "0.875rem",
    color: "#64748b",
    margin: "4px 0 0",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 340px",
    gap: "24px",
  },
  mainCol: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  sideCol: {},
  card: {
    background: "#ffffff",
    borderRadius: "14px",
    padding: "20px 24px",
    boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
    border: "1px solid #e2e8f0",
  },
  cardTitle: {
    fontSize: "1.05rem",
    fontWeight: 700,
    color: "#1e293b",
    margin: 0,
  },
  inputGroup: {
    display: "flex",
    gap: "12px",
    alignItems: "center",
  },
  otpInput: {
    flex: 1,
    padding: "14px 18px",
    fontSize: "1.6rem",
    fontWeight: 800,
    letterSpacing: "8px",
    textAlign: "center",
    borderRadius: "10px",
    border: "2px solid #cbd5e1",
    background: "#f8fafc",
    outline: "none",
    color: "#0f172a",
    fontFamily: "monospace",
  },
  verifyBtn: {
    padding: "14px 28px",
    fontSize: "1rem",
    fontWeight: 700,
    background: "#0284c7",
    color: "#fff",
    border: "none",
    borderRadius: "10px",
    cursor: "pointer",
    boxShadow: "0 2px 8px rgba(2,132,199,0.3)",
    transition: "all 0.15s ease",
    whiteSpace: "nowrap",
  },
  hint: {
    fontSize: "0.78rem",
    color: "#94a3b8",
    marginTop: "8px",
  },
  errorBox: {
    marginTop: "14px",
    padding: "10px 14px",
    background: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: "8px",
    color: "#dc2626",
    fontSize: "0.88rem",
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
  },
  successCard: {
    background: "#ffffff",
    border: "2px solid #10b981",
    borderRadius: "16px",
    padding: "24px",
    boxShadow: "0 8px 24px rgba(16,185,129,0.12)",
  },
  successBanner: {
    background: "#10b981",
    color: "#ffffff",
    padding: "10px 18px",
    borderRadius: "8px",
    fontWeight: 800,
    fontSize: "0.95rem",
    letterSpacing: "0.04em",
    textAlign: "center",
  },
  profileSection: {
    display: "flex",
    gap: "20px",
    marginTop: "20px",
    alignItems: "flex-start",
  },
  photoWrap: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  avatarImg: {
    width: "100px",
    height: "100px",
    borderRadius: "14px",
    objectFit: "cover",
    border: "3px solid #10b981",
  },
  verifiedBadge: {
    marginTop: "6px",
    fontSize: "0.7rem",
    fontWeight: 700,
    color: "#059669",
    background: "#ecfdf5",
    padding: "2px 8px",
    borderRadius: "20px",
  },
  studentName: {
    fontSize: "1.35rem",
    fontWeight: 800,
    color: "#0f172a",
    margin: "0 0 4px",
  },
  studentReg: {
    fontSize: "0.9rem",
    color: "#475569",
    marginBottom: "10px",
  },
  metaRow: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
    marginBottom: "10px",
  },
  metaBadge: {
    background: "#f1f5f9",
    color: "#334155",
    padding: "3px 10px",
    borderRadius: "6px",
    fontSize: "0.78rem",
    fontWeight: 600,
  },
  reasonBox: {
    background: "#f8fafc",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "0.85rem",
    color: "#334155",
    border: "1px solid #e2e8f0",
  },
  approvalGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "12px",
    marginTop: "16px",
    paddingTop: "14px",
    borderTop: "1px solid #e2e8f0",
  },
  approvalBox: {
    background: "#f0fdf4",
    border: "1px solid #bbf7d0",
    borderRadius: "8px",
    padding: "10px 12px",
  },
  apprTitle: {
    fontSize: "0.72rem",
    fontWeight: 700,
    color: "#166534",
    textTransform: "uppercase",
  },
  apprName: {
    fontSize: "0.85rem",
    fontWeight: 700,
    color: "#15803d",
    marginTop: "2px",
  },
  apprTime: {
    fontSize: "0.72rem",
    color: "#4ade80",
  },
  exitBtn: {
    background: "#10b981",
    color: "#ffffff",
    border: "none",
    padding: "12px 26px",
    fontSize: "0.95rem",
    fontWeight: 700,
    borderRadius: "10px",
    cursor: "pointer",
    boxShadow: "0 4px 12px rgba(16,185,129,0.3)",
  },
  deniedCard: {
    background: "#ffffff",
    border: "2px solid #ef4444",
    borderRadius: "16px",
    padding: "24px",
    boxShadow: "0 8px 24px rgba(239,68,68,0.12)",
  },
  deniedBanner: {
    background: "#ef4444",
    color: "#ffffff",
    padding: "10px 18px",
    borderRadius: "8px",
    fontWeight: 800,
    fontSize: "0.95rem",
    letterSpacing: "0.04em",
    textAlign: "center",
  },
  deniedInstruction: {
    marginTop: "12px",
    padding: "10px 14px",
    background: "#fff1f2",
    borderRadius: "8px",
    fontSize: "0.82rem",
    color: "#9f1239",
    fontWeight: 600,
  },
  refreshBtn: {
    background: "none",
    border: "1px solid #cbd5e1",
    padding: "4px 8px",
    borderRadius: "6px",
    fontSize: "0.78rem",
    color: "#64748b",
    cursor: "pointer",
  },
  exitRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 0",
    borderBottom: "1px solid #f1f5f9",
  },
  exitBadge: {
    background: "#e0f2fe",
    color: "#0369a1",
    fontSize: "0.68rem",
    fontWeight: 800,
    padding: "2px 6px",
    borderRadius: "4px",
  },
};
