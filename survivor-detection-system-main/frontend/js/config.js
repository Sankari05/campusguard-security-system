/* ==========================================================================
   RIDGEWATCH Centralized API & Client Configuration
   Single source of truth for backend URL resolution and storage.
   ========================================================================== */

(function () {
  "use strict";

  const STORAGE_KEY = "ridgewatch.apiBase";

  function getDefaultApiBase() {
    if (typeof window !== "undefined" && window.location) {
      const host = window.location.hostname || "127.0.0.1";
      const port = window.location.port;
      if (port === "8000") {
        return window.location.origin.replace(/\/+$/, "");
      }
      return `http://${host}:8000`;
    }
    return "http://127.0.0.1:8000";
  }

  function getApiBase() {
    try {
      const stored = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
      if (stored && typeof stored === "string" && stored.trim() !== "") {
        return stored.trim().replace(/\/+$/, "");
      }
    } catch (err) {
      // Storage access blocked or unavailable
    }
    return getDefaultApiBase();
  }

  function setApiBase(url) {
    try {
      if (typeof localStorage === "undefined") return;
      if (url && typeof url === "string" && url.trim() !== "") {
        const clean = url.trim().replace(/\/+$/, "");
        localStorage.setItem(STORAGE_KEY, clean);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch (err) {
      console.warn("RidgeWatchConfig: Failed to write to localStorage", err);
    }
  }

  const RidgeWatchConfig = {
    getApiBase: getApiBase,
    setApiBase: setApiBase,
    getDefaultApiBase: getDefaultApiBase,
    STORAGE_KEY: STORAGE_KEY,
  };

  if (typeof window !== "undefined") {
    window.RidgeWatchConfig = RidgeWatchConfig;
  }
  if (typeof globalThis !== "undefined") {
    globalThis.RidgeWatchConfig = RidgeWatchConfig;
  }
})();
