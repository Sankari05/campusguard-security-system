/**
 * frontend/js/utils/formatters.js
 * ===============================
 * Presentation and data formatting utilities for dashboard, tables, and reports.
 */

/**
 * Format ISO date string or Date object to DD/MM/YYYY
 */
export function formatDate(dateInput) {
  if (!dateInput) return '—';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

/**
 * Format time to 12-hour AM/PM format
 */
export function formatTime(dateInput) {
  if (!dateInput) return '—';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Human-readable relative time (e.g., "Just now", "10 mins ago")
 */
export function formatRelativeTime(dateInput) {
  if (!dateInput) return '—';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);

  if (diffSec < 30) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return formatDate(d);
}

/**
 * Formats attendance percentage with color class
 */
export function formatPercentage(val) {
  const num = parseFloat(val) || 0;
  const formatted = num.toFixed(1) + '%';
  let badgeClass = 'status-danger';
  if (num >= 85) badgeClass = 'status-good';
  else if (num >= 75) badgeClass = 'status-warning';

  return {
    value: formatted,
    numeric: num,
    badgeClass,
  };
}

/**
 * Capitalizes string cleanly
 */
export function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export default {
  formatDate,
  formatTime,
  formatRelativeTime,
  formatPercentage,
  capitalize,
};
