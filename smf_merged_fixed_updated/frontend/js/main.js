/**
 * frontend/js/main.js
 * ===================
 * Enterprise Modular Frontend Architecture Entrypoint for EduTrack Pro.
 * Assembles and exports all domain APIs, UI components, and utility helpers.
 * Binds clean global bridges for seamless backward-compatibility.
 */

// ── 1. Utilities ─────────────────────────────────────────────
import { Storage } from './utils/storage.js';
import {
  validateName,
  validateRollNumber,
  validateEmail,
  calculateAge,
  validateDateOfBirth,
} from './utils/validators.js';
import {
  formatDate,
  formatTime,
  formatRelativeTime,
  formatPercentage,
  capitalize,
} from './utils/formatters.js';

// ── 2. UI Components ─────────────────────────────────────────
import { showToast, toast } from './components/toast.js';
import { openModal, closeModal } from './components/modal.js';
import { CameraStreamController } from './components/cameraStream.js';
import { animateCounter, updateKpiCard } from './components/kpiCard.js';
import { initLayout, getSidebarHtml, getTopbarHtml } from './components/layout.js';
import { initModals, SHARED_MODALS_HTML } from './components/modals.js';

// ── 3. Domain API Clients ────────────────────────────────────
import {
  apiClient,
  apiRequest,
  ApiError,
  NetworkError,
  TimeoutError,
  ValidationError,
  RateLimitError,
} from './api/client.js';
import { AuthApi } from './api/authApi.js';
import { AttendanceApi } from './api/attendanceApi.js';
import { StudentApi } from './api/studentApi.js';

// ── Export Everything Cleanly for ES6 Modules ────────────────
export {
  Storage,
  validateName,
  validateRollNumber,
  validateEmail,
  calculateAge,
  validateDateOfBirth,
  formatDate,
  formatTime,
  formatRelativeTime,
  formatPercentage,
  capitalize,
  showToast,
  toast,
  openModal,
  closeModal,
  CameraStreamController,
  animateCounter,
  updateKpiCard,
  apiRequest,
  ApiError,
  AuthApi,
  AttendanceApi,
  StudentApi,
};

// ── Enterprise Namespace ─────────────────────────────────────
export const EduTrack = {
  version: '9.6.0',
  storage: Storage,
  utils: {
    validators: {
      validateName,
      validateRollNumber,
      validateEmail,
      calculateAge,
      validateDateOfBirth,
    },
    formatters: { formatDate, formatTime, formatRelativeTime, formatPercentage, capitalize },
  },
  components: {
    showToast,
    toast,
    openModal,
    closeModal,
    CameraStreamController,
    animateCounter,
    updateKpiCard,
    initLayout,
    getSidebarHtml,
    getTopbarHtml,
    initModals,
    SHARED_MODALS_HTML,
  },
  layout: {
    init: initLayout,
    initModals: initModals,
    getSidebar: getSidebarHtml,
    getTopbar: getTopbarHtml,
  },
  api: {
    client: apiClient,
    request: apiRequest,
    auth: AuthApi,
    attendance: AttendanceApi,
    student: StudentApi,
    errors: {
      ApiError,
      NetworkError,
      TimeoutError,
      ValidationError,
      RateLimitError,
    },
  },
};

// ── Global Window Bridge for 100% Backward Compatibility ─────
if (typeof window !== 'undefined') {
  window.EduTrack = EduTrack;

  // Global UI shortcuts for HTML onclick handlers
  window.showToast = window.showToast || showToast;
  window.toast = window.toast || toast;
  window.openModal = window.openModal || openModal;
  window.closeModal = window.closeModal || closeModal;
  window.animateCounter = window.animateCounter || animateCounter;

  // Global validation shortcuts
  window.validateName = window.validateName || validateName;
  window.calculateAge = window.calculateAge || calculateAge;
  window.validateDateOfBirth = window.validateDateOfBirth || validateDateOfBirth;

  // Global API shortcuts
  window.apiClient = apiClient;
  window.apiRequest = apiRequest;
  window.EduApi = {
    client: apiClient,
    auth: AuthApi,
    attendance: AttendanceApi,
    student: StudentApi,
    request: apiRequest,
  };

  console.log('🚀 [EduTrack Pro] Enterprise ES6 Modular Frontend Engine Initialized (v9.6.0).');
}

export default EduTrack;
