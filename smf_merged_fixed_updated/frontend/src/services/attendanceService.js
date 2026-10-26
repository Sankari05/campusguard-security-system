/**
 * frontend/src/services/attendanceService.js
 * Domain service for attendance records, overrides, and reports
 */

import { api } from './api';

export const attendanceService = {
  async getOverrides() {
    try {
      const data = await api.get('/admin/overrides');
      return Array.isArray(data) ? data : data.overrides || [];
    } catch (e) {
      return [];
    }
  },

  async createOverride(payload) {
    return await api.post('/admin/overrides', payload);
  },

  async getReportsAnalytics(dept = '', days = 30) {
    try {
      const query = `?days=${days}${dept ? `&dept=${encodeURIComponent(dept)}` : ''}`;
      return await api.get(`/reports/analytics${query}`);
    } catch (e) {
      return { total_records: 0, present_count: 0, absent_count: 0, attendance_rate: 0 };
    }
  },

  async getSessionStatus() {
    try {
      return await api.get('/session/status');
    } catch (e) {
      return { active: false, subject: '', faculty: '' };
    }
  },
};
