/**
 * frontend/js/utils/storage.js
 * ============================
 * Safe LocalStorage & SessionStorage wrapper with JSON serialization,
 * error handling for private browsing / storage quotas, and auth helpers.
 */

const STORAGE_KEYS = {
  TOKEN: 'access_token',
  ROLE: 'user_role',
  USER: 'user_profile',
  FAC_ID: 'faculty_id',
  THEME: 'theme_mode',
};

export const Storage = {
  /**
   * Set a key in localStorage with automatic JSON serialization
   */
  set(key, value) {
    try {
      const serialized = typeof value === 'string' ? value : JSON.stringify(value);
      localStorage.setItem(key, serialized);
      return true;
    } catch (e) {
      console.warn('[Storage] Failed to set item:', key, e);
      return false;
    }
  },

  /**
   * Get an item from localStorage with automatic JSON parsing
   */
  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      if (item === null) return defaultValue;
      try {
        return JSON.parse(item);
      } catch {
        return item;
      }
    } catch (e) {
      console.warn('[Storage] Failed to read item:', key, e);
      return defaultValue;
    }
  },

  /**
   * Remove an item from localStorage
   */
  remove(key) {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (e) {
      return false;
    }
  },

  /**
   * Clear all storage keys
   */
  clear() {
    try {
      localStorage.clear();
      return true;
    } catch (e) {
      return false;
    }
  },

  // ── Auth Specific Shortcuts ────────────────────────────────
  getToken() {
    return this.get(STORAGE_KEYS.TOKEN);
  },

  setToken(token) {
    return this.set(STORAGE_KEYS.TOKEN, token);
  },

  getRole() {
    return this.get(STORAGE_KEYS.ROLE, 'admin');
  },

  setRole(role) {
    return this.set(STORAGE_KEYS.ROLE, role);
  },

  getUser() {
    return this.get(STORAGE_KEYS.USER, {});
  },

  setUser(user) {
    return this.set(STORAGE_KEYS.USER, user);
  },

  clearAuth() {
    this.remove(STORAGE_KEYS.TOKEN);
    this.remove(STORAGE_KEYS.ROLE);
    this.remove(STORAGE_KEYS.USER);
    this.remove(STORAGE_KEYS.FAC_ID);
  },
};

export default Storage;
