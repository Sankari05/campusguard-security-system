/**
 * frontend/js/api/attendanceApi.js
 * ================================
 * Attendance Marking, Idempotency Guard, Camera Sessions, and Overrides API Client.
 */

import { apiRequest } from './client.js';

export const AttendanceApi = {
  /**
   * Mark attendance with Idempotency Guard
   */
  async markAttendance(studentId, period = 'Period_1', date = null) {
    const payload = {
      student_id: studentId,
      period,
      ...(date ? { date } : {}),
    };

    return await apiRequest('/api/attendance/mark', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch today's marked attendance roster
   */
  async getToday(period = '') {
    const q = period ? `?period=${encodeURIComponent(period)}` : '';
    return await apiRequest(`/api/attendance/today${q}`);
  },

  /**
   * Fetch institutional attendance percentage summary
   */
  async getSummary(days = 30) {
    return await apiRequest(`/api/attendance/summary?days=${days}`);
  },

  /**
   * Start AI camera attendance session
   */
  async startSession(payload = {}) {
    return await apiRequest('/api/role/session/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Stop active camera recognition thread
   */
  async stopSession() {
    return await apiRequest('/api/role/session/stop', {
      method: 'POST',
      body: '{}',
    });
  },

  /**
   * Get live session metrics (FPS, active period, marked count)
   */
  async getSessionStatus() {
    return await apiRequest('/api/role/session/status');
  },

  /**
   * Submit manual attendance override
   */
  async submitOverride(overrideData) {
    return await apiRequest('/api/attendance/override', {
      method: 'POST',
      body: JSON.stringify(overrideData),
    });
  },

  /**
   * Fetch override audit log
   */
  async getOverrideLog(limit = 200) {
    return await apiRequest(`/api/override/log?limit=${limit}`);
  },

  /**
   * Fetch low attendance alert list
   */
  async getLowAttendanceAlerts(threshold = 75, days = 180) {
    return await apiRequest(`/api/alerts/low-attendance?threshold=${threshold}&days=${days}`);
  },
};

export default AttendanceApi;
