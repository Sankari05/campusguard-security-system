/**
 * frontend/js/components/toast.js
 * ===============================
 * Enterprise Floating Toast Notifications with FontAwesome icons and smooth animations.
 */

const ICONS = {
  success: 'fa-circle-check',
  error: 'fa-circle-exclamation',
  warn: 'fa-triangle-exclamation',
  warning: 'fa-triangle-exclamation',
  info: 'fa-circle-info',
};

/**
 * Ensures the toast container element exists in the DOM
 */
function getOrCreateContainer() {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-atomic', 'true');
    document.body.appendChild(container);
  }
  return container;
}

/**
 * Trigger an interactive toast notification
 * @param {string} message - Text message to display
 * @param {'success'|'error'|'warn'|'info'} type - Toast type
 * @param {number} duration - Display time in ms (default 4000ms)
 */
export function showToast(message, type = 'info', duration = 4000) {
  const container = getOrCreateContainer();
  const iconClass = ICONS[type] || ICONS.info;

  const toastEl = document.createElement('div');
  toastEl.className = `toast ${type === 'warn' ? 'warning' : type}`;
  toastEl.innerHTML = `
    <i class="fa ${iconClass}"></i>
    <span class="toast-msg">${message}</span>
  `;

  // Click to dismiss immediately
  toastEl.addEventListener('click', () => {
    toastEl.classList.add('toast-out');
    setTimeout(() => toastEl.remove(), 250);
  });

  container.appendChild(toastEl);

  // Auto-dismiss timer
  setTimeout(() => {
    if (toastEl.parentNode) {
      toastEl.classList.add('toast-out');
      setTimeout(() => toastEl.remove(), 300);
    }
  }, duration);

  return toastEl;
}

// Backward compatibility helper
export const toast = showToast;
export default showToast;
