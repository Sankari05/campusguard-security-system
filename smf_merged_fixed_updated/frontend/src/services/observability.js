/**
 * frontend/src/services/observability.js
 * Browser-side Crash Reporting & Sentry Client Hook
 */

export function initFrontendObservability() {
  if (typeof window === 'undefined') return;

  // Global window unhandled error listener
  window.addEventListener('error', (event) => {
    console.error(
      '[Browser Observability] Unhandled error captured:',
      event.error || event.message
    );
    _reportCrash({
      type: 'javascript_error',
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      stack: event.error?.stack || null,
      url: window.location.href,
      timestamp: new Date().toISOString(),
    });
  });

  // Global unhandled promise rejection listener
  window.addEventListener('unhandledrejection', (event) => {
    console.error('[Browser Observability] Unhandled rejection captured:', event.reason);
    _reportCrash({
      type: 'unhandled_rejection',
      message: event.reason?.message || String(event.reason),
      stack: event.reason?.stack || null,
      url: window.location.href,
      timestamp: new Date().toISOString(),
    });
  });
}

function _reportCrash(payload) {
  try {
    // If Sentry browser SDK is loaded on window
    if (window.Sentry && typeof window.Sentry.captureException === 'function') {
      window.Sentry.captureException(new Error(payload.message), { extra: payload });
    }

    // Fire non-blocking beacon to backend error logging endpoint
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/client-error', JSON.stringify(payload));
    }
  } catch (e) {
    // Fail silently in reporting to avoid cascading failures
  }
}
