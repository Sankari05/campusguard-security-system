/**
 * frontend/src/services/studentService.js
 * Domain service for student roster, stats, and registration
 */

import { api } from './api';

export const studentService = {
  async getStudents(params = {}) {
    const query = new URLSearchParams(params).toString();
    const endpoint = `/admin/students${query ? `?${query}` : ''}`;
    try {
      const data = await api.get(endpoint);
      return Array.isArray(data) ? data : data.students || [];
    } catch (e) {
      console.warn('Fallback to /students endpoint:', e);
      const data = await api.get('/students');
      return Array.isArray(data) ? data : data.students || [];
    }
  },

  async getStudentStats() {
    try {
      return await api.get('/admin/students/stats');
    } catch (e) {
      return { total: 0, active: 0, department_breakdown: {} };
    }
  },

  async addStudent(studentData) {
    return await api.post('/students', studentData);
  },
};
