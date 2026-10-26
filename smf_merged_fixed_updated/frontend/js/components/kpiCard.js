/**
 * frontend/js/components/kpiCard.js
 * =================================
 * Interactive KPI Cards with smooth numeric counter animations and trend badges.
 */

/**
 * Animate a numeric value from start to end with cubic easing
 */
export function animateCounter(elementId, targetValue, duration = 800) {
  const el = document.getElementById(elementId);
  if (!el) return;

  const startValue = parseFloat(el.textContent.replace(/[^0-9.-]/g, '')) || 0;
  const target = parseFloat(targetValue) || 0;
  const isPercent = String(targetValue).includes('%');
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-out cubic
    const ease = 1 - Math.pow(1 - progress, 3);
    const current = Math.floor(startValue + (target - startValue) * ease);

    el.textContent = isPercent ? `${current}%` : current.toLocaleString();

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      el.textContent = isPercent ? `${target}%` : target.toLocaleString();
    }
  }

  requestAnimationFrame(update);
}

/**
 * Updates a KPI card element with value and optional status class
 */
export function updateKpiCard(id, value, statusClass = '') {
  const el = document.getElementById(id);
  if (!el) return;

  animateCounter(id, value);

  if (statusClass) {
    el.className = `kpi-val ${statusClass}`;
  }
}

export default {
  animateCounter,
  updateKpiCard,
};
