/**
 * frontend/js/api/studentApi.js
 * =============================
 * Student Lifecycle, Enrollment, and Academic Cascades API Client.
 */

import { apiRequest } from './client.js';

export const StudentApi = {
  /**
   * Fetch complete student roster
   */
  async getAll() {
    return await apiRequest('/api/students');
  },

  /**
   * Fetch single student profile by ID
   */
  async getById(studentId) {
    return await apiRequest(`/api/students/${studentId}`);
  },

  /**
   * Add a new student record
   */
  async add(studentData) {
    return await apiRequest('/api/students', {
      method: 'POST',
      body: JSON.stringify(studentData),
    });
  },

  /**
   * Delete student record by ID
   */
  async delete(studentId) {
    return await apiRequest(`/api/students/${studentId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Get student enrollment stats & department counts
   */
  async getStats() {
    return await apiRequest('/api/admin/students/stats');
  },

  /**
   * Department courses cascade
   */
  async getDeptCourses(dept) {
    return await apiRequest(`/api/departments/${encodeURIComponent(dept)}/courses`);
  },

  /**
   * Course years & sections cascade
   */
  async getYearSections(dept, course, year) {
    return await apiRequest(
      `/api/departments/${encodeURIComponent(dept)}/courses/${encodeURIComponent(course)}/years/${encodeURIComponent(year)}/sections`
    );
  },
};

export default StudentApi;
