/* ==========================================================================
   RIDGEWATCH Testing Module — Shared Utilities & Client
   Direct, unauthenticated testing client for simulation & control operations.
   ========================================================================== */

(() => {
  "use strict";

  function apiBase() {
    return RidgeWatchConfig.getApiBase();
  }

  // ------------------------------------------------------------------ //
  // Direct fetch helper for testing controls (no authentication)
  // ------------------------------------------------------------------ //

  async function testingFetch(path, options = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      options.headers || {}
    );

    const res = await fetch(`${apiBase()}${path}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let detail = `Request failed with status ${res.status}`;
      try {
        const err = await res.json();
        if (err && err.detail) detail = err.detail;
      } catch (_) {}
      throw new Error(detail);
    }

    return res.json();
  }

  // ------------------------------------------------------------------ //
  // Date & Time formatting helpers
  // ------------------------------------------------------------------ //

  const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function parseDateObj(isoStr) {
    if (!isoStr) return null;
    const d = new Date(isoStr);
    return isNaN(d.getTime()) ? null : d;
  }

  function formatDate(isoStr) {
    const d = parseDateObj(isoStr);
    if (!d) return isoStr || "—";
    const day = String(d.getDate()).padStart(2, "0");
    const month = MONTH_NAMES[d.getMonth()];
    const year = d.getFullYear();
    return `${day} ${month} ${year}`;
  }

  function formatTime(isoStr) {
    const d = parseDateObj(isoStr);
    if (!d) return "—";
    let hours = d.getHours();
    const minutes = String(d.getMinutes()).padStart(2, "0");
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12;
    hours = hours ? hours : 12;
    const strHours = String(hours).padStart(2, "0");
    return `${strHours}:${minutes} ${ampm}`;
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return "—";
    const d = parseDateObj(isoStr);
    if (!d) return isoStr;
    return `${formatDate(isoStr)}, ${formatTime(isoStr)}`;
  }

  // ------------------------------------------------------------------ //
  // Canonical disaster scenarios catalog
  // ------------------------------------------------------------------ //

  const FALLBACK_DISASTER_SCENARIOS = [
    { id: "earthquake", scenario_id: "earthquake", name: "Earthquake", icon: "🌋", category: "Geophysical" },
    { id: "tsunami", scenario_id: "tsunami", name: "Tsunami", icon: "🌊", category: "Hydrological" },
    { id: "flood", scenario_id: "flood", name: "Flood", icon: "💧", category: "Hydrological" },
    { id: "cyclone", scenario_id: "cyclone", name: "Cyclone", icon: "🌪️", category: "Meteorological" },
    { id: "landslide", scenario_id: "landslide", name: "Landslide", icon: "⛰️", category: "Geological" },
    { id: "building_collapse", scenario_id: "building_collapse", name: "Building Collapse", icon: "🏚️", category: "Structural" },
    { id: "urban_fire", scenario_id: "urban_fire", name: "Fire / Urban Fire", icon: "🔥", category: "Thermal" },
    { id: "wildfire", scenario_id: "wildfire", name: "Forest Fire / Wildfire", icon: "🌲", category: "Thermal" },
    { id: "industrial_accident", scenario_id: "industrial_accident", name: "Industrial Accident", icon: "🏭", category: "Industrial" },
    { id: "chemical_leak", scenario_id: "chemical_leak", name: "Chemical / Toxic Gas Leak", icon: "☣️", category: "CBRN / HazMat" },
    { id: "dam_failure", scenario_id: "dam_failure", name: "Dam Failure / Dam Break", icon: "🌊", category: "Hydrological" },
    { id: "avalanche", scenario_id: "avalanche", name: "Avalanche", icon: "❄️", category: "Cryospheric" },
    { id: "drought", scenario_id: "drought", name: "Drought", icon: "☀️", category: "Climatological" },
    { id: "heatwave", scenario_id: "heatwave", name: "Extreme Heat / Heatwave", icon: "🌡️", category: "Climatological" },
    { id: "cloudburst", scenario_id: "cloudburst", name: "Cloudburst", icon: "⛈️", category: "Meteorological" },
    { id: "stampede", scenario_id: "stampede", name: "Stampede / Mass Gathering", icon: "👥", category: "Crowd" },
    { id: "transport_accident", scenario_id: "transport_accident", name: "Major Road / Transport Accident", icon: "🚌", category: "Transportation" },
    { id: "infrastructure_entrapment", scenario_id: "infrastructure_entrapment", name: "Infrastructure Trapped-Person", icon: "🚇", category: "Specialized" },
    { id: "multi_hazard", scenario_id: "multi_hazard", name: "Multi-Hazard Disaster", icon: "⚡", category: "Compound Disasters" },
  ];

  async function fetchDisasterScenarios() {
    try {
      const data = await testingFetch("/disaster-scenarios");
      if (data && data.scenarios && data.scenarios.length) {
        return data.scenarios;
      }
    } catch (_) {}
    return FALLBACK_DISASTER_SCENARIOS;
  }

  // ------------------------------------------------------------------ //
  // Shared testing utilities object
  // ------------------------------------------------------------------ //

  const TestingCommon = {
    apiBase,
    testingFetch,
    adminFetch: testingFetch,
    formatDate,
    formatTime,
    formatDateTime,
    fetchDisasterScenarios,
    FALLBACK_DISASTER_SCENARIOS,
    requireAdminOrRedirect: () => "testing-active",
    wireHeaderAuthToggle: () => {},
    logoutAdmin: () => {},
  };

  window.TestingCommon = TestingCommon;
  window.AdminCommon = TestingCommon; // legacy compatibility alias
})();
