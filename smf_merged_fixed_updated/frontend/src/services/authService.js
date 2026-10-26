/**
 * frontend/src/services/authService.js
 * Session state, credentials authentication, and role persistence
 */

import { api } from './api';

export const authService = {
  async login(username, password, role = 'admin') {
    // Matches FastAPI OAuth2PasswordRequestForm or JSON body
    const body = { username, password, role };
    const res = await api.post('/auth/login', body);

    if (res && (res.access_token || res.token)) {
      const token = res.access_token || res.token;
      const user = res.user || { username, role, name: res.name || username.toUpperCase() };

      sessionStorage.setItem('_token', token);
      sessionStorage.setItem('_role', role);
      sessionStorage.setItem('_portal', role);
      sessionStorage.setItem('_user', JSON.stringify(user));
      return { token, user };
    }

    throw new Error(res.detail || 'Authentication failed');
  },

  getCurrentUser() {
    try {
      const userStr = sessionStorage.getItem('_user');
      const token = sessionStorage.getItem('_token');
      const role = sessionStorage.getItem('_role') || 'admin';
      if (!token) return null;
      return userStr ? JSON.parse(userStr) : { username: 'admin', role };
    } catch (e) {
      return null;
    }
  },

  logout() {
    sessionStorage.removeItem('_token');
    sessionStorage.removeItem('_role');
    sessionStorage.removeItem('_portal');
    sessionStorage.removeItem('_user');
    window.location.reload();
  },

  isAuthenticated() {
    return !!sessionStorage.getItem('_token');
  },
};
