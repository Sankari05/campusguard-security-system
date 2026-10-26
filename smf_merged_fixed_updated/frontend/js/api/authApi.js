/**
 * frontend/js/api/authApi.js
 * ==========================
 * Authentication & Password Recovery Domain API Client.
 */

import { apiRequest } from './client.js';
import { Storage } from '../utils/storage.js';

export const AuthApi = {
  /**
   * Authenticate user with role credentials
   */
  async login(email, password, role = 'admin', facId = '', portal = '') {
    const payload = {
      email,
      password,
      role,
      fac_id: facId || '',
      portal: portal || role || '',
    };

    const data = await apiRequest('/api/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (data.token) {
      Storage.setToken(data.token);
      Storage.setRole(data.role || role);
      Storage.setUser(data.user || { email, role });
    }

    return data;
  },

  /**
   * Clears session and logs out
   */
  logout() {
    Storage.clearAuth();
    if (typeof window.showLoginScreen === 'function') {
      window.showLoginScreen();
    } else {
      window.location.reload();
    }
  },

  /**
   * Request OTP code for forgot-password recovery
   */
  async sendOtp(email) {
    return await apiRequest('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /**
   * Verify OTP and reset password
   */
  async resetPassword(email, otp, newPassword) {
    return await apiRequest('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({
        email,
        otp,
        new_password: newPassword,
      }),
    });
  },

  /**
   * Fetch current authenticated user info
   */
  async getCurrentUser() {
    return await apiRequest('/api/auth/me');
  },
};

export default AuthApi;
