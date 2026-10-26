/**
 * frontend/js/components/modal.js
 * ===============================
 * Accessible and reusable Dialog / Modal controller with ESC key & backdrop dismiss.
 */

// Active modal stack
const activeModals = [];

/**
 * Open a modal by its DOM ID
 */
export function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (!el) {
    console.warn(`[Modal] Element with ID "${modalId}" not found.`);
    return;
  }

  el.classList.remove('dn');
  el.classList.add('modal-active');
  activeModals.push(modalId);

  // Auto-focus first input if available
  const firstInput = el.querySelector('input, select, textarea');
  if (firstInput) {
    setTimeout(() => firstInput.focus(), 100);
  }
}

/**
 * Close a modal by its DOM ID
 */
export function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (!el) return;

  el.classList.add('dn');
  el.classList.remove('modal-active');

  const idx = activeModals.indexOf(modalId);
  if (idx !== -1) {
    activeModals.splice(idx, 1);
  }
}

// Global ESC key listener to close topmost modal
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && activeModals.length > 0) {
    const topmost = activeModals[activeModals.length - 1];
    closeModal(topmost);
  }
});

// Backdrop click listener
document.addEventListener('click', (e) => {
  if (e.target && e.target.classList.contains('modal-bg') && !e.target.classList.contains('dn')) {
    closeModal(e.target.id);
  }
});

export default {
  openModal,
  closeModal,
};
