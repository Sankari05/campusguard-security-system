/* ==========================================================================
   RIDGEWATCH — Hardware Station Telemetry & Sensor Monitoring
   Pure frontend, read-only.
   Natively matched with RIDGEWATCH White + Blue Design System.
   ========================================================================== */

(() => {
  "use strict";

  // ------------------------------------------------------------------ //
  // Configuration & Metadata
  // ------------------------------------------------------------------ //

  const POLL_MS = 4000;

  const HARDWARE_META = {
    heart_rate_radar:     { name: "TI IWR6843AOP Radar",        tech: "mmWave Micro-Doppler",       role: "Breathing & pulse rate detection",     icon: "📡", port: "UART / RADAR_TX/RX", power: "3.3V DC" },
    thermal_imaging:      { name: "FLIR Lepton 3.5 LWIR",       tech: "Long-Wave Infrared",         role: "Human body heat signature",            icon: "🌡️", port: "VoSPI / I2C (0x2A)",  power: "3.3V DC" },
    acoustic:             { name: "INMP441 MEMS Mic Array",     tech: "Digital Acoustic MEMS",      role: "Distress calls & tapping detection",   icon: "🎙️", port: "I2S Audio Bus",       power: "3.3V DC" },
    co2:                  { name: "Winsen MH-Z19C NDIR CO2",    tech: "Non-Dispersive Infrared",    role: "Exhaled air pocket concentration",     icon: "💨", port: "UART / CO2_TX/RX",     power: "5.0V DC" },
    pir_motion:           { name: "Panasonic PaPIRs Motion",    tech: "Infrared Motion Trigger",    role: "Kinematic survivor movement",          icon: "👁️", port: "GPIO Interrupt (Pin 22)", power: "3.3V DC" },
    rgb_camera:           { name: "Sony IMX708 Camera Module",  tech: "Visible Spectrum Optical",   role: "Visual classification & bounding box", icon: "📷", port: "MIPI CSI-2 (CAM0)",    power: "3.3V DC" },
    imu_tilt:             { name: "InvenSense MPU-6050 Tilt",   tech: "MEMS Inclinometer",          role: "Structural shift & angular tilt",      icon: "📐", port: "I2C (0x68)",          power: "3.3V DC" },
    imu_vibration:        { name: "InvenSense MPU-6050 Vib",    tech: "Piezo Accelerometer",        role: "Ground shock & seismic vibration",     icon: "📳", port: "I2C (0x69)",          power: "3.3V DC" },
    water_level:          { name: "Radar/Ultrasonic Water Level & Pressure", tech: "Non-Contact Ranging & Hydrostatic", role: "Flood water depth & non-contact pressure", icon: "💧", port: "UART / ADC CH1",    power: "5.0V DC" },
    water_flow:           { name: "ADCP Doppler Flow Velocity", tech: "Acoustic Doppler Sensor",    role: "Flood current speed & hydraulic force",icon: "🌊", port: "RS-485 Modbus / CH2",   power: "12.0V DC" },
    gas_concentration:    { name: "MQ-135 / BME680 Gas",        tech: "Multi-Gas MOX / PID",        role: "Toxic gas concentration (PPM)",        icon: "☣️", port: "Analog ADC CH3",      power: "5.0V DC" },
    smoke_density:        { name: "PMS5003 Laser Smoke Chamber",tech: "Laser Optical Scattering",   role: "Particulate obscuration density",      icon: "🌫️", port: "UART / SMOKE_RX",     power: "5.0V DC" },
    barometric_pressure:  { name: "Bosch BMP280 Barometer",     tech: "Digital Piezoresistive",     role: "Atmospheric pressure & cyclone drop",  icon: "⏱️", port: "I2C (0x76)",          power: "3.3V DC" },
    rainfall_intensity:   { name: "RG-11 Optical Rain Gauge",   tech: "Infrared Disdrometer",       role: "Precipitation rate & volume",         icon: "🌧️", port: "Pulse / Digital GPIO", power: "5.0V DC" },
    soil_moisture:        { name: "FDR Soil Saturation Probe",  tech: "Frequency Domain Saturation",role: "Slope saturation & liquefaction",      icon: "🌱", port: "Analog ADC CH0",      power: "3.3V DC" },
    temperature:          { name: "Sensirion SHT31 Temp",       tech: "Precision Semiconductor",    role: "Ambient temperature & hypothermia",    icon: "🌡️", port: "I2C (0x44)",          power: "3.3V DC" },
    humidity:             { name: "Sensirion SHT31 Humidity",   tech: "Capacitive Polymer",         role: "Atmospheric relative humidity",        icon: "💧", port: "I2C (0x44)",          power: "3.3V DC" },
    gps:                  { name: "u-blox NEO-M9N Multi-GNSS",  tech: "Multi-Constellation L1/L5",  role: "3D coordinates, fix & kinematics",     icon: "🛰️", port: "UART / GPS_TX/RX",     power: "3.3V DC" },
  };

  const SENSOR_RANGE = {
    heart_rate_radar:     { unit: "bpm",    min: 0,   max: 110 },
    thermal_imaging:      { unit: "°C",     min: -5,  max: 45 },
    acoustic:             { unit: "dB",     min: 0,   max: 70 },
    co2:                  { unit: "ppm",    min: 400, max: 2500 },
    pir_motion:           { unit: "",       min: 0,   max: 1 },
    rgb_camera:           { unit: "",       min: 0,   max: 1 },
    imu_tilt:             { unit: "°",      min: 0,   max: 30 },
    imu_vibration:        { unit: "g",      min: 0,   max: 1 },
    water_level:          { unit: "cm",     min: 0,   max: 200 },
    water_flow:           { unit: "m/s",    min: 0,   max: 3.0 },
    gas_concentration:    { unit: "ppm",    min: 0,   max: 500 },
    smoke_density:        { unit: "%",      min: 0,   max: 100 },
    barometric_pressure:  { unit: "hPa",    min: 900, max: 1050 },
    rainfall_intensity:   { unit: "mm/hr",  min: 0,   max: 100 },
    soil_moisture:        { unit: "%",      min: 0,   max: 100 },
    temperature:          { unit: "°C",     min: -40, max: 85 },
    humidity:             { unit: "%",      min: 0,   max: 100 },
    gps:                  { unit: "sats",   min: 0,   max: 20 },
  };

  const SENSOR_ORDER = [
    "water_level", "rainfall_intensity", "water_flow", "heart_rate_radar", "thermal_imaging",
    "acoustic", "co2", "pir_motion", "rgb_camera", "imu_tilt", "imu_vibration",
    "gas_concentration", "smoke_density", "barometric_pressure", "soil_moisture",
    "temperature", "humidity", "gps"
  ];

  const EDGE_STAGES = [
    { id: "sensors", title: "Sensor Kit",       sub: "18 channels per victim node" },
    { id: "esp32",   title: "ESP32-S3",         sub: "Data validation + packaging" },
    { id: "pi",      title: "Raspberry Pi 5",   sub: "Edge AI fusion & SPS" },
    { id: "comm",    title: "LoRa / 4G-5G",     sub: "Alert & dispatch mesh" },
    { id: "team",    title: "Rescue Team",      sub: "Field intervention" },
  ];

  const TRIAGE_COLORS = {
    HIGH: "#e0311f",
    MEDIUM: "#e8850a",
    LOW: "#d4a90a",
    NO_VITAL_SIGNS: "#8998b8",
    SAFE: "#16a34a",
  };
  const TRIAGE_EMOJI = {
    HIGH: "🔴",
    MEDIUM: "🟠",
    LOW: "🟡",
    NO_VITAL_SIGNS: "⚪",
    SAFE: "🟢",
  };

  // ------------------------------------------------------------------ //
  // Application State
  // ------------------------------------------------------------------ //

  const state = {
    get apiBase() { return RidgeWatchConfig.getApiBase(); },
    selectedVictimId: null,
    selectedSensorKey: null,
    latestVictims: [],
    latestQueue: [],
    latestTeamMembers: [],
    scenarioRunning: false,
    profile: null,
    currentFilter: "ALL", // ALL | PRIMARY | SUPPORTING | STANDBY | ALERTS | OFFLINE
    searchQuery: "",
    viewMode: "GRID", // GRID | TABLE
    cachedTelemetries: {
      slopeNodes: null,
      cameras: null,
      thermal: null,
      correlation: null,
      rainfall: null,
      pressure: null,
      gasSmoke: null,
      temperature: null,
      humidity: null,
      gps: null,
      gpsHealth: null,
    }
  };

  // ------------------------------------------------------------------ //
  // DOM Elements
  // ------------------------------------------------------------------ //

  const el = {
    headerScenario: document.getElementById("hwHeaderScenario"),
    scenarioMetaSub: document.getElementById("hwScenarioMetaSub"),
    systemStatusText: document.getElementById("hwSystemStatusText"),
    headerTotal: document.getElementById("hwHeaderTotal"),
    headerOnline: document.getElementById("hwHeaderOnline"),
    headerAlerts: document.getElementById("hwHeaderAlerts"),
    headerDegraded: document.getElementById("hwHeaderDegraded"),
    
    // Scenario Role Boxes
    cntRolePrimary: document.getElementById("cntRolePrimary"),
    cntRoleSupporting: document.getElementById("cntRoleSupporting"),
    cntRoleStandby: document.getElementById("cntRoleStandby"),
    rolePrimaryTags: document.getElementById("hwRolePrimaryTags"),
    roleSupportingTags: document.getElementById("hwRoleSupportingTags"),
    roleStandbyTags: document.getElementById("hwRoleStandbyTags"),

    // KPI Cards
    kpiTotal: document.getElementById("hwKpiTotal"),
    kpiOnline: document.getElementById("hwKpiOnline"),
    kpiActive: document.getElementById("hwKpiActive"),
    kpiActiveSub: document.getElementById("hwKpiActiveSub"),
    kpiStandby: document.getElementById("hwKpiStandby"),
    kpiStandbySub: document.getElementById("hwKpiStandbySub"),
    kpiAlerts: document.getElementById("hwKpiAlerts"),
    kpiAlertsCard: document.getElementById("hwKpiAlertsCard"),

    // Controls
    victimTabs: document.getElementById("hwVictimTabs"),
    filterPills: document.getElementById("hwFilterPills"),
    btnViewGrid: document.getElementById("btnViewGrid"),
    btnViewTable: document.getElementById("btnViewTable"),
    searchInput: document.getElementById("hwSearchInput"),
    searchClear: document.getElementById("hwSearchClear"),
    cntFilterAll: document.getElementById("cntFilterAll"),
    cntFilterPrimary: document.getElementById("cntFilterPrimary"),
    cntFilterSupporting: document.getElementById("cntFilterSupporting"),
    cntFilterStandby: document.getElementById("cntFilterStandby"),
    cntFilterAlerts: document.getElementById("cntFilterAlerts"),
    cntFilterOffline: document.getElementById("cntFilterOffline"),

    // Main Displays
    sensorGrid: document.getElementById("hwSensorGrid"),
    tableContainer: document.getElementById("hwTableContainer"),
    tableBody: document.getElementById("hwTableBody"),

    // Visual Intelligence Section
    rgbStatusText: document.getElementById("hwRgbStatusText"),
    rgbDetectionState: document.getElementById("hwRgbDetectionState"),
    rgbConfidence: document.getElementById("hwRgbConfidence"),
    rgbPersonCount: document.getElementById("hwRgbPersonCount"),
    rgbClarity: document.getElementById("hwRgbClarity"),

    thermalStatusText: document.getElementById("hwThermalStatusText"),
    thermalBodyTemp: document.getElementById("hwThermalBodyTemp"),
    thermalDelta: document.getElementById("hwThermalDelta"),
    thermalSignatures: document.getElementById("hwThermalSignatures"),
    thermalHotspot: document.getElementById("hwThermalHotspot"),

    // Detail Modal / Drawer
    detailOverlay: document.getElementById("hwDetailOverlay"),
    detailIcon: document.getElementById("hwDetailIcon"),
    detailName: document.getElementById("hwDetailName"),
    detailBigVal: document.getElementById("hwDetailBigVal"),
    detailHealthBadge: document.getElementById("hwDetailHealthBadge"),
    detailTrendVal: document.getElementById("hwDetailTrendVal"),
    detailRoleVal: document.getElementById("hwDetailRoleVal"),
    detailModelVal: document.getElementById("hwDetailModelVal"),
    detailProtocolVal: document.getElementById("hwDetailProtocolVal"),
    detailPowerVal: document.getElementById("hwDetailPowerVal"),
    detailRateVal: document.getElementById("hwDetailRateVal"),
    detailConfVal: document.getElementById("hwDetailConfVal"),
    detailDoctrineVal: document.getElementById("hwDetailDoctrineVal"),
    btnDetailClose: document.getElementById("btnDetailClose"),

    // Accordions
    pipelineSvg: document.getElementById("hwPipelineSvg"),
    pipelineSub: document.getElementById("hwPipelineSub"),
    dispatchStrip: document.getElementById("hwDispatchStrip"),

    // Statusbar
    statusMessage: document.getElementById("hwStatusMessage"),
    statusPoll: document.getElementById("hwStatusPoll"),
  };

  // ------------------------------------------------------------------ //
  // API Helpers
  // ------------------------------------------------------------------ //

  class ApiError extends Error {
    constructor(status, detail) {
      super(detail || `HTTP ${status}`);
      this.status = status;
    }
  }

  async function apiGet(path) {
    const res = await fetch(state.apiBase + path, { method: "GET" });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str == null ? "" : String(str);
    return d.innerHTML;
  }

  function formatSensorValue(v, range) {
    if (v == null || isNaN(v)) return "0.0";
    if (range.max <= 1) return Number(v).toFixed(2);
    return Number(v).toFixed(1);
  }

  // ------------------------------------------------------------------ //
  // Main Polling Loop
  // ------------------------------------------------------------------ //

  async function poll() {
    try {
      const victimsRes = await apiGet("/victims");
      state.latestVictims = victimsRes.victims || [];

      const queueRes = await apiGet("/queue");
      state.latestQueue = queueRes.queue || [];

      state.latestTeamMembers = (await apiGet("/rescue-team/members-status").catch(() => ({}))).members || [];
      state.profile = await apiGet("/scenario/sensor-profile").catch(() => null);

      // Fetch dedicated subsystem stations in parallel
      const [slope, cam, thm, rain, baro, gas, temp, humid, gps, gpsHealth, flood, evac] = await Promise.all([
        apiGet("/hazards/landslide/nodes").catch(() => null),
        apiGet("/sensors/cameras").catch(() => null),
        apiGet("/sensors/thermal").catch(() => null),
        apiGet("/sensors/rainfall/current").catch(() => null),
        apiGet("/sensors/pressure/current").catch(() => null),
        apiGet("/sensors/gas-smoke/current").catch(() => null),
        apiGet("/sensors/temperature/current").catch(() => null),
        apiGet("/sensors/humidity/current").catch(() => null),
        apiGet("/sensors/gps/current").catch(() => null),
        apiGet("/sensors/gps/health").catch(() => null),
        apiGet("/flood-intelligence/current").catch(() => null),
        apiGet("/evacuation/recommendations").catch(() => null),
      ]);

      state.cachedTelemetries = {
        slopeNodes: slope,
        cameras: cam,
        thermal: thm,
        rainfall: rain,
        pressure: baro,
        gasSmoke: gas,
        temperature: temp,
        humidity: humid,
        gps: gps,
        gpsHealth: gpsHealth,
        flood: flood,
        evac: evac,
      };

      if (state.selectedVictimId) {
        state.cachedTelemetries.correlation = await apiGet(`/sensors/camera-thermal/correlation?victim_id=${encodeURIComponent(state.selectedVictimId)}`).catch(() => null);
      }

      state.scenarioRunning = true;

      if (!state.selectedVictimId || !state.latestVictims.some(v => v.victim_id === state.selectedVictimId)) {
        state.selectedVictimId = state.latestVictims.length ? state.latestVictims[0].victim_id : null;
      }

      if (el.statusMessage) el.statusMessage.textContent = "Live Telemetry Connected — White + Blue Hardware Console Active.";
      if (el.systemStatusText) el.systemStatusText.textContent = "SYSTEM ONLINE";

      renderHeaderAndSummary();
      renderScenarioBreakdown();
      renderVictimTabs();
      renderSensorGridOrTable();
      renderVisualIntelligence();
      renderFloodIntelligence();
      renderPipeline();
      renderDispatchStrip();

      // If detail modal is open, refresh its data
      if (state.selectedSensorKey && !el.detailOverlay.hidden) {
        renderDetailModal(state.selectedSensorKey);
      }

    } catch (e) {
      state.scenarioRunning = false;
      renderIdleState(e);
    }

    if (el.statusPoll) {
      el.statusPoll.textContent = `poll: ${new Date().toLocaleTimeString([], { hour12: false })}`;
    }
    setTimeout(poll, POLL_MS);
  }

  // ------------------------------------------------------------------ //
  // Data Extractor for Each Sensor Modality
  // ------------------------------------------------------------------ //

  function extractSensorData(sensorKey) {
    const meta = HARDWARE_META[sensorKey] || { name: sensorKey, tech: "Hardware Sensor", role: "", icon: "📡", port: "Native", power: "3.3V DC" };
    const range = SENSOR_RANGE[sensorKey] || { unit: "", min: 0, max: 100 };
    const victim = state.latestVictims.find(v => v.victim_id === state.selectedVictimId) || state.latestVictims[0] || {};
    const reading = (victim.sensors && victim.sensors[sensorKey]) || null;
    const cache = state.cachedTelemetries || {};
    const prof = state.profile || {};

    let role = "STANDBY";
    let weight = 0.0;
    if (prof.primary_sensors && prof.primary_sensors.includes(sensorKey)) {
      role = "PRIMARY";
    } else if (prof.supporting_sensors && prof.supporting_sensors.includes(sensorKey)) {
      role = "SUPPORTING";
    } else if (prof.inactive_sensors && prof.inactive_sensors.includes(sensorKey)) {
      role = "STANDBY";
    }

    if (prof.sensor_matrix) {
      const row = prof.sensor_matrix.find(r => r.sensor_type === sensorKey);
      if (row) {
        if (row.role) role = row.role;
        if (row.weight != null) weight = row.weight;
      }
    }

    let val = reading ? reading.value : 0.0;
    let unit = (reading && reading.unit) || range.unit || "";
    let trend = (reading && reading.trend) || "STABLE";
    let isAlert = false;
    let alertMsg = "";
    let status = (victim.sensor_node_online === false) ? "OFFLINE" : (role === "STANDBY" ? "NOMINAL" : "ONLINE");
    let rateOfChange = (reading && reading.rate_of_change != null) ? reading.rate_of_change : 0.0;
    let confidence = reading && reading.confidence != null ? reading.confidence : 0.98;
    let baseline = "—";
    let extraData = null;

    // Subsystem Domain Enrichment
    if (sensorKey === "rainfall_intensity" && cache.rainfall && cache.rainfall.rainfall) {
      const r = cache.rainfall.rainfall;
      val = r.rainfall_rate_mm_h != null ? r.rainfall_rate_mm_h : val;
      unit = "mm/h";
      trend = r.trend || trend;
      rateOfChange = r.rate_of_change || rateOfChange;
      confidence = r.confidence || confidence;
      status = r.status || status;
      if (val >= 25.0 || r.classification === "EXTREME" || r.classification === "HEAVY") {
        isAlert = true;
        alertMsg = `⚠️ Heavy Rain (${val.toFixed(1)} mm/h)`;
      }
      extraData = {
        cumulative_mm: r.cumulative_rainfall_mm != null ? r.cumulative_rainfall_mm.toFixed(1) : "0.0",
        classification: r.classification || "NOMINAL",
        severity: r.severity || "LOW",
      };
    } else if (sensorKey === "barometric_pressure" && cache.pressure && cache.pressure.pressure) {
      const p = cache.pressure.pressure;
      val = p.pressure_hpa != null ? p.pressure_hpa : val;
      unit = "hPa";
      trend = p.trend || trend;
      rateOfChange = p.rate_of_change || rateOfChange;
      baseline = p.baseline_hpa != null ? `${p.baseline_hpa.toFixed(1)} hPa` : "1013.2 hPa";
      confidence = p.confidence || confidence;
      status = p.status || status;
      if (val < 990.0 || p.drop_severity === "CRITICAL") {
        isAlert = true;
        alertMsg = `🌪️ Cyclonic Drop (${val.toFixed(1)} hPa)`;
      }
      extraData = {
        drop_severity: p.drop_severity || "NORMAL",
      };
    } else if (sensorKey === "gas_concentration" && cache.gasSmoke && cache.gasSmoke.gas_smoke) {
      const gs = cache.gasSmoke.gas_smoke;
      val = gs.gas_concentration_ppm != null ? gs.gas_concentration_ppm : val;
      unit = "PPM";
      status = gs.status || status;
      if (val >= 100.0 || gs.gas_level === "CRITICAL" || gs.gas_level === "ELEVATED") {
        isAlert = true;
        alertMsg = `☣️ Toxic Gas Alert (${val.toFixed(1)} PPM)`;
      }
      extraData = {
        gas_level: gs.gas_level || "NORMAL",
        scba_required: val >= 100.0,
      };
    } else if (sensorKey === "smoke_density" && cache.gasSmoke && cache.gasSmoke.gas_smoke) {
      const gs = cache.gasSmoke.gas_smoke;
      val = gs.smoke_density_pct != null ? gs.smoke_density_pct : val;
      unit = "%";
      status = gs.status || status;
      if (val >= 40.0 || gs.smoke_level === "HIGH") {
        isAlert = true;
        alertMsg = `🔥 Heavy Smoke (${val.toFixed(1)}%)`;
      }
      extraData = {
        smoke_level: gs.smoke_level || "LOW",
      };
    } else if (sensorKey === "temperature" && cache.temperature && cache.temperature.temperature) {
      const t = cache.temperature.temperature;
      val = (t.temperature_c != null ? t.temperature_c : t.ambient_temp_c) != null ? (t.temperature_c != null ? t.temperature_c : t.ambient_temp_c) : val;
      unit = "°C";
      trend = t.trend || trend;
      rateOfChange = t.rate_of_change || rateOfChange;
      confidence = t.confidence || confidence;
      status = t.status || status;
      if (val >= 45.0) {
        isAlert = true;
        alertMsg = `🔥 Extreme Heat (${val.toFixed(1)}°C)`;
      } else if (val <= 0.0) {
        isAlert = true;
        alertMsg = `❄️ Freezing Risk (${val.toFixed(1)}°C)`;
      }
    } else if (sensorKey === "humidity" && cache.humidity && cache.humidity.humidity) {
      const h = cache.humidity.humidity;
      val = h.humidity_pct != null ? h.humidity_pct : val;
      unit = "%";
      trend = h.trend || trend;
      rateOfChange = h.rate_of_change || rateOfChange;
      confidence = h.confidence || confidence;
      status = h.status || status;
    } else if (sensorKey === "soil_moisture" && cache.slopeNodes && cache.slopeNodes.nodes) {
      const nodes = Object.values(cache.slopeNodes.nodes);
      if (nodes.length > 0) {
        val = Math.max(...nodes.map(n => n.soil_moisture_pct || 0));
        unit = "%";
        trend = nodes[0].moisture_trend || trend;
        rateOfChange = nodes[0].moisture_rate || rateOfChange;
        if (val >= 75.0 || nodes.some(n => n.risk_level === "CRITICAL" || n.risk_level === "HIGH")) {
          isAlert = true;
          alertMsg = `⛰️ Landslide Moisture (${val.toFixed(1)}%)`;
        }
        extraData = { slopeNodesList: nodes };
      }
    } else if (sensorKey === "imu_tilt" && cache.slopeNodes && cache.slopeNodes.nodes) {
      const nodes = Object.values(cache.slopeNodes.nodes);
      if (nodes.length > 0) {
        const maxTilt = Math.max(...nodes.map(n => n.tilt_angle_deg || 0));
        if (maxTilt > val) val = maxTilt;
        if (val >= 15.0) {
          isAlert = true;
          alertMsg = `📐 Structural Shear (${val.toFixed(1)}°)`;
        }
      }
    } else if (sensorKey === "rgb_camera" && cache.cameras && cache.cameras.cameras) {
      const cams = Object.values(cache.cameras.cameras);
      if (cams.length > 0) {
        const cam = cams[0];
        val = cam.confidence != null ? cam.confidence : val;
        unit = "conf";
        status = cam.status || status;
        extraData = {
          person_count: cam.person_count || 0,
          visibility: Math.round((cam.visibility || 1) * 100),
          occlusion: Math.round((cam.occlusion || 0) * 100),
          detection_state: cam.detection_state || "SCANNING",
        };
      }
    } else if (sensorKey === "thermal_imaging" && cache.thermal && cache.thermal.thermal_cameras) {
      const thms = Object.values(cache.thermal.thermal_cameras);
      if (thms.length > 0) {
        const thm = thms[0];
        val = thm.estimated_temperature != null ? thm.estimated_temperature : val;
        unit = "°C";
        status = thm.status || status;
        extraData = {
          delta_t: thm.temperature_delta ? thm.temperature_delta.toFixed(1) : "0.0",
          heat_signatures: thm.heat_signature_count || (thm.human_signature ? 1 : 0),
          fire_hotspot: thm.fire_hotspot || false,
          detection_type: thm.detection_type || "THERMAL_SCAN",
        };
      }
    } else if (sensorKey === "gps" && cache.gps && cache.gps.gps) {
      const g = cache.gps.gps;
      val = g.satellites != null ? g.satellites : 12;
      unit = "sats";
      status = g.status || status;
      if (val === 0 || g.status === "OFFLINE") {
        isAlert = true;
        alertMsg = `🚨 GPS Signal Loss`;
      }
      extraData = {
        lat: g.latitude != null ? g.latitude.toFixed(4) : "32.3740",
        lon: g.longitude != null ? g.longitude.toFixed(4) : "77.2491",
        accuracy_m: g.accuracy_m != null ? g.accuracy_m.toFixed(1) : "2.5",
        speed_mps: g.speed_mps != null ? g.speed_mps.toFixed(1) : "0.0",
        fix_quality: g.fix_quality || "3D_FIX_PRECISION",
      };
    } else if (sensorKey === "heart_rate_radar") {
      if (val > 0 && (val < 40 || val > 120)) {
        isAlert = true;
        alertMsg = `⚠️ Cardiac Anomaly (${val.toFixed(0)} bpm)`;
      }
    } else if (sensorKey === "water_level") {
      if (cache.waterLevel && cache.waterLevel.water_level) {
        const w = cache.waterLevel.water_level;
        val = w.water_level_cm != null ? w.water_level_cm : val;
        trend = w.trend || trend;
        rateOfChange = w.rate_of_change != null ? w.rate_of_change : rateOfChange;
        confidence = w.confidence != null ? w.confidence : confidence;
        status = w.status || status;
      }
      if (val > 60.0) {
        isAlert = true;
        alertMsg = `🌊 Flood Submersion (${val.toFixed(1)} cm)`;
      }
      const wObj = (cache.waterLevel && cache.waterLevel.water_level) || {};
      const depthM = wObj.water_depth_m != null ? Number(wObj.water_depth_m) : (val / 100.0);
      const pressKpa = wObj.estimated_pressure_kpa != null ? Number(wObj.estimated_pressure_kpa) : (depthM * 9.80665);
      extraData = {
        water_depth_m: depthM.toFixed(2),
        estimated_pressure_kpa: pressKpa.toFixed(3),
        measured_surface_distance_m: wObj.measured_surface_distance_m != null ? Number(wObj.measured_surface_distance_m).toFixed(2) : (5.0 - depthM).toFixed(2),
        sensor_type: wObj.sensor_type || "ultrasonic",
        reading_quality: wObj.reading_quality || (status === "OFFLINE" ? "UNAVAILABLE" : "EXCELLENT"),
        reading_timestamp: wObj.reading_timestamp || wObj.timestamp || new Date().toISOString(),
        pressure_source: wObj.pressure_source || "non_contact_sensor_estimation",
      };
    } else if (sensorKey === "imu_vibration" && val > 0.40) {
      isAlert = true;
      alertMsg = `📳 Seismic Shock (${val.toFixed(2)} g)`;
    } else if (sensorKey === "imu_tilt" && val > 15.0) {
      isAlert = true;
      alertMsg = `📐 Structural Tilt (${val.toFixed(1)}°)`;
    } else if (sensorKey === "co2" && val > 1500.0) {
      isAlert = true;
      alertMsg = `💨 Elevated CO2 (${val.toFixed(0)} ppm)`;
    } else if (sensorKey === "acoustic" && val > 65.0) {
      isAlert = true;
      alertMsg = `🎙️ Acoustic Spike (${val.toFixed(1)} dB)`;
    }

    return {
      key: sensorKey,
      name: meta.name,
      tech: meta.tech,
      icon: meta.icon,
      port: meta.port,
      power: meta.power,
      role: role,
      weight: weight,
      value: val,
      unit: unit,
      trend: trend,
      isAlert: isAlert,
      alertMsg: alertMsg,
      status: status,
      rateOfChange: rateOfChange,
      confidence: confidence,
      baseline: baseline,
      extraData: extraData,
      operationalRole: meta.role,
    };
  }

  // ------------------------------------------------------------------ //
  // Render: Header & Summary KPI Cards
  // ------------------------------------------------------------------ //

  function renderHeaderAndSummary() {
    const prof = state.profile || {};
    const scenarioName = prof.name || (prof.scenario_id ? prof.scenario_id.toUpperCase().replace(/_/g, " ") : "STANDARD DEPLOYMENT");
    const pSensors = prof.primary_sensors || [];
    const sSensors = prof.supporting_sensors || [];
    const iSensors = prof.inactive_sensors || [];

    const totalCount = SENSOR_ORDER.length; // 18
    const onlineCount = state.latestVictims.length > 0 && state.latestVictims[0].sensor_node_online ? totalCount : (state.latestVictims.length > 0 ? 16 : 0);
    const degradedCount = totalCount - onlineCount;

    let alertsCount = 0;
    for (const key of SENSOR_ORDER) {
      const data = extractSensorData(key);
      if (data.isAlert) alertsCount++;
    }

    if (el.headerScenario) el.headerScenario.textContent = scenarioName;
    if (el.headerTotal) el.headerTotal.textContent = totalCount;
    if (el.headerOnline) el.headerOnline.textContent = onlineCount;
    if (el.headerAlerts) el.headerAlerts.textContent = alertsCount;
    if (el.headerDegraded) el.headerDegraded.textContent = degradedCount;

    if (el.kpiTotal) el.kpiTotal.textContent = totalCount;
    if (el.kpiOnline) el.kpiOnline.textContent = onlineCount;
    if (el.kpiActive) el.kpiActive.textContent = pSensors.length || 3;
    if (el.kpiActiveSub) el.kpiActiveSub.textContent = `${pSensors.length} Core Channels`;
    if (el.kpiStandby) el.kpiStandby.textContent = (sSensors.length + iSensors.length) || 15;
    if (el.kpiStandbySub) el.kpiStandbySub.textContent = `${sSensors.length} Supp · ${iSensors.length} Stby`;
    if (el.kpiAlerts) el.kpiAlerts.textContent = alertsCount;
    if (el.kpiAlertsCard) el.kpiAlertsCard.classList.toggle("has-alerts", alertsCount > 0);

    if (el.cntFilterAll) el.cntFilterAll.textContent = totalCount;
    if (el.cntFilterPrimary) el.cntFilterPrimary.textContent = pSensors.length;
    if (el.cntFilterSupporting) el.cntFilterSupporting.textContent = sSensors.length;
    if (el.cntFilterStandby) el.cntFilterStandby.textContent = iSensors.length;
    if (el.cntFilterAlerts) el.cntFilterAlerts.textContent = alertsCount;
    if (el.cntFilterOffline) el.cntFilterOffline.textContent = degradedCount;
  }

  // ------------------------------------------------------------------ //
  // Render: Active Scenario 3-Column Breakdown
  // ------------------------------------------------------------------ //

  function renderScenarioBreakdown() {
    const prof = state.profile || {};
    const pSensors = prof.primary_sensors || [];
    const sSensors = prof.supporting_sensors || [];
    const iSensors = prof.inactive_sensors || [];

    if (el.cntRolePrimary) el.cntRolePrimary.textContent = pSensors.length;
    if (el.cntRoleSupporting) el.cntRoleSupporting.textContent = sSensors.length;
    if (el.cntRoleStandby) el.cntRoleStandby.textContent = iSensors.length;

    function renderTagList(keys, targetEl, emptyMsg) {
      if (!targetEl) return;
      if (!keys || !keys.length) {
        targetEl.innerHTML = `<span class="hw-role-tag" style="color: var(--ink-faint);">${emptyMsg}</span>`;
        return;
      }
      targetEl.innerHTML = keys.map(k => {
        const meta = HARDWARE_META[k] || { name: k, icon: "📡" };
        return `<span class="hw-role-tag">${meta.icon} ${escapeHtml(meta.name)}</span>`;
      }).join("");
    }

    renderTagList(pSensors, el.rolePrimaryTags, "None active in current scenario");
    renderTagList(sSensors, el.roleSupportingTags, "None active");
    renderTagList(iSensors, el.roleStandbyTags, "None in standby");
  }

  // ------------------------------------------------------------------ //
  // Render: Responsive Sensor Cards Grid & Sensor Table
  // ------------------------------------------------------------------ //

  function getFilteredSensors() {
    let sensors = SENSOR_ORDER.map(k => extractSensorData(k));

    if (state.currentFilter === "PRIMARY") {
      sensors = sensors.filter(s => s.role === "PRIMARY");
    } else if (state.currentFilter === "SUPPORTING") {
      sensors = sensors.filter(s => s.role === "SUPPORTING");
    } else if (state.currentFilter === "STANDBY") {
      sensors = sensors.filter(s => s.role === "STANDBY");
    } else if (state.currentFilter === "ALERTS") {
      sensors = sensors.filter(s => s.isAlert);
    } else if (state.currentFilter === "OFFLINE") {
      sensors = sensors.filter(s => s.status === "OFFLINE" || s.status === "DEGRADED");
    }

    if (state.searchQuery.trim()) {
      const q = state.searchQuery.toLowerCase().trim();
      sensors = sensors.filter(s =>
        s.name.toLowerCase().includes(q) ||
        s.key.toLowerCase().includes(q) ||
        s.role.toLowerCase().includes(q) ||
        s.tech.toLowerCase().includes(q) ||
        s.status.toLowerCase().includes(q)
      );
    }

    const priorityWeight = { PRIMARY: 1, SUPPORTING: 2, STANDBY: 3, OFFLINE: 4 };
    sensors.sort((a, b) => {
      const pa = a.status === "OFFLINE" ? 4 : (priorityWeight[a.role] || 3);
      const pb = b.status === "OFFLINE" ? 4 : (priorityWeight[b.role] || 3);
      if (pa !== pb) return pa - pb;
      return SENSOR_ORDER.indexOf(a.key) - SENSOR_ORDER.indexOf(b.key);
    });

    return sensors;
  }

  function renderSensorGridOrTable() {
    const sensors = getFilteredSensors();

    if (state.viewMode === "GRID") {
      if (el.sensorGrid) el.sensorGrid.hidden = false;
      if (el.tableContainer) el.tableContainer.hidden = true;
      renderGrid(sensors);
    } else {
      if (el.sensorGrid) el.sensorGrid.hidden = true;
      if (el.tableContainer) el.tableContainer.hidden = false;
      renderTable(sensors);
    }
  }

  function renderGrid(sensors) {
    if (!el.sensorGrid) return;

    if (sensors.length === 0) {
      el.sensorGrid.innerHTML = `
        <div class="stat-card" style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--ink-dim);">
          <div style="font-size: 24px; margin-bottom: 6px;">🔍</div>
          <div style="font-weight: 700; font-size: 14px; color: var(--ink);">No sensor modalities match "${escapeHtml(state.searchQuery || state.currentFilter)}"</div>
          <button type="button" class="btn btn-secondary" style="margin-top: 10px;" id="hwResetFilters">Reset Filter &amp; Search</button>
        </div>
      `;
      const btn = document.getElementById("hwResetFilters");
      if (btn) {
        btn.onclick = () => {
          state.currentFilter = "ALL";
          state.searchQuery = "";
          if (el.searchInput) el.searchInput.value = "";
          updateFilterButtons();
          renderSensorGridOrTable();
        };
      }
      return;
    }

    el.sensorGrid.innerHTML = sensors.map(s => {
      const isPrimary = s.role === "PRIMARY";
      const isSupporting = s.role === "SUPPORTING";
      const isSelected = state.selectedSensorKey === s.key;

      let cardRoleClass = isPrimary ? "is-primary" : (isSupporting ? "is-supporting" : "is-standby");
      if (s.isAlert) cardRoleClass += " has-alert";
      if (isSelected) cardRoleClass += " is-selected";

      let roleBadgeClass = isPrimary ? "hw-role-primary" : (isSupporting ? "hw-role-supporting" : "hw-role-standby");
      if (s.isAlert) roleBadgeClass = "hw-role-alert";

      let dotClass = s.status === "ONLINE" ? "is-online" : (s.status === "NOMINAL" ? "is-online" : (s.status === "DEGRADED" ? "is-warning" : "is-offline"));
      if (s.isAlert) dotClass = "is-critical";

      const valFormatted = formatSensorValue(s.value, SENSOR_RANGE[s.key] || { max: 100 });
      const range = SENSOR_RANGE[s.key] || { min: 0, max: 100 };
      const pct = Math.min(100, Math.max(5, ((s.value - range.min) / (range.max - range.min || 1)) * 100));

      const trendIcon = (s.trend || "").includes("RISING") || (s.trend || "").includes("INCREASING") ? "↑" :
                        (s.trend || "").includes("FALLING") || (s.trend || "").includes("DECREASING") ? "↓" : "→";

      return `
        <div class="hw-sensor-card ${cardRoleClass}" data-key="${s.key}">
          <div class="hw-card-top">
            <div class="hw-card-name-wrap">
              <span class="hw-card-icon">${s.icon}</span>
              <div>
                <div class="hw-card-name">${escapeHtml(s.name)}</div>
                <div class="hw-card-tech">${escapeHtml(s.tech)}</div>
              </div>
            </div>
            <div class="hw-card-badges">
              <span class="hw-role-badge ${roleBadgeClass}">${escapeHtml(s.isAlert ? s.alertMsg : s.role)}</span>
            </div>
          </div>

          <div class="hw-card-main-reading">
            <div>
              <span class="hw-reading-val">${valFormatted}</span>
              <span class="hw-reading-unit">${escapeHtml(s.unit)}</span>
            </div>
            <div class="hw-reading-trend" title="Trend: ${escapeHtml(s.trend)}">
              ${trendIcon} ${escapeHtml(s.trend)}
            </div>
          </div>

          <div class="hw-card-progress-bar">
            <div class="hw-progress-fill" style="width: ${pct}%;"></div>
          </div>

          ${s.key === "water_level" ? `
          <div style="margin: 6px 0; padding: 4px 8px; border-radius: 4px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); font-size: 11px; display: flex; justify-content: space-between; align-items: center;">
            <span style="color: var(--ink-dim); font-size: 10px;">📡 Non-Contact Pressure:</span>
            <strong style="color: #38bdf8; font-family: var(--font-mono);">${s.extraData && s.extraData.estimated_pressure_kpa ? s.extraData.estimated_pressure_kpa : ((s.value / 100) * 9.80665).toFixed(2)} kPa</strong>
          </div>
          ` : ''}

          <div class="hw-card-footer">
            <span class="hw-status-indicator">
              <span class="hw-dot ${dotClass}"></span>
              <span>${escapeHtml(s.status)}</span>
            </span>
            <span style="font-family: var(--font-mono); font-size: 10.5px; color: var(--accent-ice);">Inspect →</span>
          </div>
        </div>
      `;
    }).join("");

    // Attach click listeners
    el.sensorGrid.querySelectorAll(".hw-sensor-card").forEach(card => {
      card.onclick = () => {
        const key = card.getAttribute("data-key");
        openDetailModal(key);
      };
    });
  }

  function renderTable(sensors) {
    if (!el.tableBody) return;

    if (sensors.length === 0) {
      el.tableBody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: var(--ink-dim); padding: 24px;">
            No sensor modalities match "${escapeHtml(state.searchQuery || state.currentFilter)}"
          </td>
        </tr>
      `;
      return;
    }

    el.tableBody.innerHTML = sensors.map(s => {
      const isPrimary = s.role === "PRIMARY";
      const isSelected = state.selectedSensorKey === s.key;
      let dotClass = s.status === "ONLINE" ? "is-online" : (s.status === "NOMINAL" ? "is-online" : (s.status === "DEGRADED" ? "is-warning" : "is-offline"));
      if (s.isAlert) dotClass = "is-critical";

      const valFormatted = formatSensorValue(s.value, SENSOR_RANGE[s.key] || { max: 100 });
      const trendIcon = (s.trend || "").includes("RISING") || (s.trend || "").includes("INCREASING") ? "↑" :
                        (s.trend || "").includes("FALLING") || (s.trend || "").includes("DECREASING") ? "↓" : "→";

      return `
        <tr class="${isSelected ? 'is-selected' : ''}" data-key="${s.key}">
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 16px;">${s.icon}</span>
              <div>
                <strong style="color: var(--ink); font-size: 12.5px;">${escapeHtml(s.name)}</strong>
                <div style="font-size: 10.5px; color: var(--ink-dim);">${escapeHtml(s.tech)}</div>
              </div>
            </div>
          </td>
          <td>
            <strong style="font-family: var(--font-display); font-size: 14px; color: var(--ink);">${valFormatted}</strong>
            <span style="font-size: 11px; color: var(--ink-dim);">${escapeHtml(s.unit)}</span>
          </td>
          <td>
            <span style="font-family: var(--font-mono); font-size: 11.5px; font-weight: 600; color: var(--ink-dim);">${trendIcon} ${escapeHtml(s.trend)}</span>
          </td>
          <td>
            <span class="hw-status-indicator">
              <span class="hw-dot ${dotClass}"></span>
              <span style="font-size: 11px; font-weight: 600;">${escapeHtml(s.status)}</span>
            </span>
          </td>
          <td>
            <span class="hw-role-badge ${isPrimary ? 'hw-role-primary' : 'hw-role-supporting'}">${escapeHtml(s.role)}</span>
          </td>
          <td>
            <span style="font-size: 11px; font-weight: 600; color: ${s.isAlert ? 'var(--tri-high)' : 'var(--tri-safe)'};">${escapeHtml(s.isAlert ? s.alertMsg : 'NOMINAL')}</span>
          </td>
          <td>
            <span style="font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-dim);">${escapeHtml(s.port)}</span>
          </td>
        </tr>
      `;
    }).join("");

    el.tableBody.querySelectorAll("tr").forEach(tr => {
      tr.onclick = () => {
        const key = tr.getAttribute("data-key");
        if (key) openDetailModal(key);
      };
    });
  }

  // ------------------------------------------------------------------ //
  // Render: Visual Intelligence (RGB + FLIR Thermal)
  // ------------------------------------------------------------------ //

  function renderVisualIntelligence() {
    const cache = state.cachedTelemetries || {};

    // RGB Optical
    if (cache.cameras && cache.cameras.cameras) {
      const cams = Object.values(cache.cameras.cameras);
      if (cams.length > 0) {
        const c = cams[0];
        if (el.rgbStatusText) el.rgbStatusText.textContent = c.status || "ONLINE";
        if (el.rgbDetectionState) el.rgbDetectionState.textContent = c.detection_state || "HUMAN DETECTED";
        if (el.rgbConfidence) el.rgbConfidence.textContent = `${Math.round((c.confidence || 0.88) * 100)}%`;
        if (el.rgbPersonCount) el.rgbPersonCount.textContent = `${c.person_count || 1} ${c.person_count === 1 ? 'Person' : 'Persons'}`;
        if (el.rgbClarity) el.rgbClarity.textContent = `${Math.round((c.visibility || 0.95) * 100)}% (Clear)`;
      }
    }

    // FLIR Thermal
    if (cache.thermal && cache.thermal.thermal_cameras) {
      const thms = Object.values(cache.thermal.thermal_cameras);
      if (thms.length > 0) {
        const t = thms[0];
        if (el.thermalStatusText) el.thermalStatusText.textContent = t.status || "ONLINE";
        if (el.thermalBodyTemp) el.thermalBodyTemp.textContent = `${(t.estimated_temperature || 34.2).toFixed(1)} °C`;
        if (el.thermalDelta) el.thermalDelta.textContent = `+${(t.temperature_delta || 8.4).toFixed(1)} °C`;
        if (el.thermalSignatures) el.thermalSignatures.textContent = `${t.heat_signature_count || 1} Detected`;
        if (el.thermalHotspot) el.thermalHotspot.textContent = t.fire_hotspot ? "FIRE DETECTED" : "None";
      }
    }
  }

  function renderFloodIntelligence() {
    const cache = state.cachedTelemetries || {};
    const flood = cache.flood || {};
    const ca = flood.current_assessment || {};

    const distEl = document.getElementById("hwFloodDist");
    const depthEl = document.getElementById("hwFloodDepth");
    const pressEl = document.getElementById("hwFloodPressure");
    const riseEl = document.getElementById("hwFloodRiseRate");
    const timeEl = document.getElementById("hwFloodTimeToInund");
    const sapEl = document.getElementById("hwFloodAssemblyPoint");
    const statusTextEl = document.getElementById("hwFloodStatusText");
    const statusDotEl = document.getElementById("hwFloodDot");
    const sourceBadgeEl = document.getElementById("hwFloodSourceBadge");

    if (distEl) distEl.textContent = `${(ca.measured_distance_m != null ? ca.measured_distance_m : 4.80).toFixed(2)} m`;
    if (depthEl) depthEl.textContent = `${(ca.water_depth_m != null ? ca.water_depth_m : 1.20).toFixed(2)} m`;
    if (pressEl) pressEl.textContent = `${(ca.hydrostatic_pressure_kpa != null ? ca.hydrostatic_pressure_kpa : 11.77).toFixed(2)} kPa`;
    if (riseEl) {
      const riseMpm = ca.rise_rate_mps != null ? ca.rise_rate_mps * 60.0 : 0.12;
      riseEl.textContent = `${riseMpm >= 0 ? '+' : ''}${riseMpm.toFixed(2)} m/min`;
    }
    if (timeEl) {
      if (ca.time_to_inundation_minutes != null) {
        timeEl.textContent = `${ca.time_to_inundation_minutes.toFixed(1)} min`;
        timeEl.style.color = ca.time_to_inundation_minutes <= 10.0 ? "#e0311f" : "#ea580c";
      } else {
        timeEl.textContent = "Nominal (>60 min)";
        timeEl.style.color = "#16a34a";
      }
    }
    if (sapEl && cache.evac && cache.evac.recommendations && cache.evac.recommendations.length > 0) {
      const rec = cache.evac.recommendations[0];
      sapEl.textContent = rec.recommended_assembly_point ? rec.recommended_assembly_point.name : "Melamchi Upper Ridge";
    }
    if (statusTextEl) {
      statusTextEl.textContent = ca.risk_level || "MONITORING";
      if (statusDotEl) {
        statusDotEl.className = `hw-dot ${ca.risk_level === 'CRITICAL' ? 'is-critical' : (ca.risk_level === 'WARNING' ? 'is-warning' : 'is-online')}`;
      }
    }
    if (sourceBadgeEl) {
      const isSim = ca.mode === "SIMULATION_DATA" || (ca.is_live_sensor === false);
      sourceBadgeEl.textContent = isSim ? "SIMULATION DATA" : "REAL SENSOR DATA";
      sourceBadgeEl.style.background = isSim ? "rgba(2, 132, 199, 0.15)" : "rgba(16, 185, 129, 0.15)";
      sourceBadgeEl.style.color = isSim ? "#0284c7" : "#10b981";
      sourceBadgeEl.style.borderColor = isSim ? "rgba(2, 132, 199, 0.3)" : "rgba(16, 185, 129, 0.3)";
    }
  }

  // ------------------------------------------------------------------ //
  // Sensor Detail Modal / Drawer Handlers
  // ------------------------------------------------------------------ //

  function openDetailModal(sensorKey) {
    state.selectedSensorKey = sensorKey;
    renderDetailModal(sensorKey);
    if (el.detailOverlay) el.detailOverlay.hidden = false;
  }

  function closeDetailModal() {
    state.selectedSensorKey = null;
    if (el.detailOverlay) el.detailOverlay.hidden = true;
    renderSensorGridOrTable();
  }

  function renderDetailModal(sensorKey) {
    const s = extractSensorData(sensorKey);
    const valFormatted = formatSensorValue(s.value, SENSOR_RANGE[s.key] || { max: 100 });
    const trendIcon = (s.trend || "").includes("RISING") || (s.trend || "").includes("INCREASING") ? "↑" :
                      (s.trend || "").includes("FALLING") || (s.trend || "").includes("DECREASING") ? "↓" : "→";
    let dotClass = s.status === "ONLINE" ? "is-online" : (s.status === "NOMINAL" ? "is-online" : (s.status === "DEGRADED" ? "is-warning" : "is-offline"));
    if (s.isAlert) dotClass = "is-critical";

    if (el.detailIcon) el.detailIcon.textContent = s.icon;
    if (el.detailName) el.detailName.textContent = s.name;
    if (el.detailBigVal) el.detailBigVal.textContent = `${valFormatted} ${s.unit}`;
    if (el.detailHealthBadge) {
      el.detailHealthBadge.innerHTML = `<span class="hw-dot ${dotClass}"></span> ${escapeHtml(s.status)}`;
    }
    if (el.detailTrendVal) el.detailTrendVal.textContent = `${trendIcon} ${escapeHtml(s.trend)}`;
    if (el.detailRoleVal) el.detailRoleVal.textContent = `${escapeHtml(s.role)} (${s.weight > 0 ? (s.weight * 100).toFixed(0) + '% Weight' : 'Gated'})`;
    if (el.detailModelVal) el.detailModelVal.textContent = s.name;
    if (el.detailProtocolVal) el.detailProtocolVal.textContent = s.port;
    if (el.detailPowerVal) el.detailPowerVal.textContent = s.power;
    if (el.detailRateVal) el.detailRateVal.textContent = `${s.rateOfChange >= 0 ? '+' : ''}${s.rateOfChange.toFixed(2)}/cyc`;
    if (el.detailConfVal) el.detailConfVal.textContent = `${Math.round(s.confidence * 100)}% Rated`;
    if (el.detailDoctrineVal) {
      el.detailDoctrineVal.textContent = `${s.operationalRole || s.tech}. ${s.role === 'PRIMARY' ? 'Core driving channel for active disaster classification.' : (s.role === 'SUPPORTING' ? 'Supporting channel for cross-modal validation.' : 'Standby baseline sensor.')}`;
    }
  }

  // ------------------------------------------------------------------ //
  // Render: Victim Selector Tabs
  // ------------------------------------------------------------------ //

  function renderVictimTabs() {
    if (!el.victimTabs) return;
    if (!state.latestVictims.length) {
      el.victimTabs.innerHTML = '<span class="empty-note" style="font-size: 11px; padding: 0;">No victim nodes online yet.</span>';
      return;
    }

    el.victimTabs.innerHTML = state.latestVictims.map(v => {
      const q = state.latestQueue.find(item => item.victim_id === v.victim_id);
      const isSelected = v.victim_id === state.selectedVictimId;
      const emoji = q ? (TRIAGE_EMOJI[q.triage_class] || "") : "";
      return `
        <button type="button" class="hw-vtab-btn ${isSelected ? 'is-active' : ''}" data-victim="${v.victim_id}">
          <span>${escapeHtml(v.victim_id)}</span>
          ${emoji ? `<span>${emoji}</span>` : ""}
          ${v.sensor_node_online ? "" : `<span style="font-size: 9px; color: #ef4444;">OFF</span>`}
        </button>
      `;
    }).join("");

    el.victimTabs.querySelectorAll(".hw-vtab-btn").forEach(tab => {
      tab.onclick = () => {
        state.selectedVictimId = tab.getAttribute("data-victim");
        renderVictimTabs();
        renderSensorGridOrTable();
        renderPipeline();
      };
    });
  }

  // ------------------------------------------------------------------ //
  // Render: Pipeline Diagram (SVG) & Dispatch Strip
  // ------------------------------------------------------------------ //

  function renderPipeline() {
    const victim = state.latestVictims.find(v => v.victim_id === state.selectedVictimId) || state.latestVictims[0];
    const svg = el.pipelineSvg;
    if (!svg) return;

    if (!victim) {
      svg.innerHTML = `<text x="20" y="40" fill="var(--ink-faint)" font-family="var(--font-display)" font-size="13">No victim telemetry yet — start a scenario to stream live data.</text>`;
      return;
    }

    const queueEntry = state.latestQueue.find(q => q.victim_id === victim.victim_id);
    let svgContent = "";

    // Left Column: Compact Sensor Stack
    let y = 10;
    svgContent += `<text x="20" y="${y + 16}" font-size="11" letter-spacing="1.5" fill="var(--ink-faint)" font-family="var(--font-display)">SENSOR KIT · ${escapeHtml(victim.victim_id)}</text>`;
    y += 30;

    for (const sensorKey of SENSOR_ORDER) {
      const meta = HARDWARE_META[sensorKey];
      const range = SENSOR_RANGE[sensorKey];
      const reading = victim.sensors && victim.sensors[sensorKey];
      const unit = (reading && reading.unit) || range.unit || "";
      const valueText = reading ? `${formatSensorValue(reading.value, range)}${unit ? " " + unit : ""}` : "—";
      svgContent += `
        <g transform="translate(20, ${y})">
          <rect width="420" height="28" rx="4" fill="var(--bg-panel-raised)" stroke="var(--border)"/>
          <text x="10" y="18" font-size="11" fill="var(--ink)" font-family="var(--font-display)" font-weight="600">${meta.icon} ${escapeHtml(meta.name)}</text>
          <text x="410" y="18" font-size="11" font-weight="700" fill="var(--accent-ice)" font-family="var(--font-mono)" text-anchor="end">${escapeHtml(valueText)}</text>
        </g>`;
      y += 33;
    }

    // Right Column: Edge AI Chain
    const ex = 480, ecw = 500;
    let ey = 10;
    svgContent += `<text x="${ex}" y="${ey + 16}" font-size="11" letter-spacing="1.5" fill="var(--ink-faint)" font-family="var(--font-display)">EDGE / RESCUE PIPELINE</text>`;
    ey += 30;

    for (let i = 0; i < EDGE_STAGES.length; i++) {
      const stage = EDGE_STAGES[i];
      let extra = "";
      if (stage.id === "pi" && queueEntry) {
        const color = TRIAGE_COLORS[queueEntry.triage_class] || TRIAGE_COLORS.NO_VITAL_SIGNS;
        extra = `<text x="16" y="58" font-size="11" fill="${color}" font-weight="700" font-family="var(--font-mono)">${TRIAGE_EMOJI[queueEntry.triage_class] || ""} ${escapeHtml(queueEntry.triage_class)} · SPS ${queueEntry.sps.toFixed(1)}</text>`;
      }
      if (stage.id === "team") {
        const assigned = state.latestTeamMembers.find(m => m.assigned_victim_id === victim.victim_id && m.status !== "hold");
        if (assigned) {
          extra = `<text x="16" y="58" font-size="11" fill="var(--accent-ice)" font-weight="700" font-family="var(--font-mono)">${escapeHtml(assigned.callsign)} · ${escapeHtml((assigned.status || "").toUpperCase())}</text>`;
        }
      }

      svgContent += `
        <g transform="translate(${ex}, ${ey})">
          <rect width="${ecw}" height="70" rx="6" fill="var(--bg-panel)" stroke="var(--accent-ice-dim)" stroke-width="1.5"/>
          <circle cx="20" cy="22" r="10" fill="var(--accent-ice-dim)"/>
          <text x="20" y="26" font-size="11" font-weight="700" fill="var(--ink)" text-anchor="middle" font-family="var(--font-mono)">${i + 1}</text>
          <text x="40" y="24" font-size="13" font-weight="700" fill="var(--ink)" font-family="var(--font-display)">${escapeHtml(stage.title)}</text>
          <text x="40" y="40" font-size="10.5" fill="var(--ink-dim)" font-family="var(--font-display)">${escapeHtml(stage.sub)}</text>
          ${extra}
        </g>`;
      if (i < EDGE_STAGES.length - 1) {
        const arrowY = ey + 70 + 4;
        svgContent += `<line x1="${ex + ecw / 2}" y1="${arrowY - 2}" x2="${ex + ecw / 2}" y2="${arrowY + 8}" stroke="var(--accent-ice)" stroke-width="2" marker-end="url(#hwArrow)"/>`;
      }
      ey += 84;
    }

    svg.innerHTML = `
      <defs>
        <marker id="hwArrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="var(--accent-ice)"/>
        </marker>
      </defs>
      ${svgContent}`;
  }

  function renderDispatchStrip() {
    if (!el.dispatchStrip) return;
    const members = state.latestTeamMembers || [];
    if (!members.length) {
      el.dispatchStrip.innerHTML = '<p class="empty-note">No rescue team roster loaded.</p>';
      return;
    }

    const visible = members.filter(m => m.status !== "hold");
    if (!visible.length) {
      el.dispatchStrip.innerHTML = '<p class="empty-note">All rescue teams on STANDBY / HOLD.</p>';
      return;
    }

    el.dispatchStrip.innerHTML = visible.map(m => {
      const status = (m.status || "").toUpperCase();
      const statusClass = status === "ARRIVED" ? "is-arrived" : (status === "EN_ROUTE" ? "is-en-route" : "is-hold");
      return `
        <div class="hw-team-pill-card">
          <div class="hw-team-pill-head">
            <span class="hw-team-callsign">🚑 ${escapeHtml(m.callsign)}</span>
            <span class="hw-team-status ${statusClass}">${escapeHtml(status)}</span>
          </div>
          <div style="font-size: 11px; color: var(--ink-dim); font-family: var(--font-mono);">
            Target: <strong>${escapeHtml(m.assigned_victim_id || 'PATROL')}</strong>
          </div>
        </div>`;
    }).join("");
  }

  // ------------------------------------------------------------------ //
  // Controls Handlers: Filters, Search, View Modes & Modals
  // ------------------------------------------------------------------ //

  function updateFilterButtons() {
    if (!el.filterPills) return;
    const btns = el.filterPills.querySelectorAll(".hw-filter-btn");
    btns.forEach(b => {
      const f = b.getAttribute("data-filter");
      if (f === state.currentFilter) {
        b.classList.add("is-active");
      } else {
        b.classList.remove("is-active");
      }
    });
  }

  function setupEventListeners() {
    // Filter Pills
    if (el.filterPills) {
      el.filterPills.querySelectorAll(".hw-filter-btn").forEach(btn => {
        btn.onclick = () => {
          state.currentFilter = btn.getAttribute("data-filter");
          updateFilterButtons();
          renderSensorGridOrTable();
        };
      });
    }

    // View Mode Toggle (Grid vs Table)
    if (el.btnViewGrid) {
      el.btnViewGrid.onclick = () => {
        state.viewMode = "GRID";
        el.btnViewGrid.classList.add("is-active");
        if (el.btnViewTable) el.btnViewTable.classList.remove("is-active");
        renderSensorGridOrTable();
      };
    }
    if (el.btnViewTable) {
      el.btnViewTable.onclick = () => {
        state.viewMode = "TABLE";
        el.btnViewTable.classList.add("is-active");
        if (el.btnViewGrid) el.btnViewGrid.classList.remove("is-active");
        renderSensorGridOrTable();
      };
    }

    // Search Input
    if (el.searchInput) {
      el.searchInput.oninput = (e) => {
        state.searchQuery = e.target.value;
        if (el.searchClear) {
          el.searchClear.hidden = !state.searchQuery;
        }
        renderSensorGridOrTable();
      };
    }

    // Search Clear Button
    if (el.searchClear) {
      el.searchClear.onclick = () => {
        state.searchQuery = "";
        if (el.searchInput) el.searchInput.value = "";
        el.searchClear.hidden = true;
        renderSensorGridOrTable();
      };
    }

    // Detail Modal Close Button
    if (el.btnDetailClose) {
      el.btnDetailClose.onclick = () => closeDetailModal();
    }

    // Close Modal on Background Click
    if (el.detailOverlay) {
      el.detailOverlay.onclick = (e) => {
        if (e.target === el.detailOverlay) {
          closeDetailModal();
        }
      };
    }

    // Global Escape Key to close modal
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && el.detailOverlay && !el.detailOverlay.hidden) {
        closeDetailModal();
      }
    });
  }

  // ------------------------------------------------------------------ //
  // Idle / Fallback State
  // ------------------------------------------------------------------ //

  // ------------------------------------------------------------------ //
  // Smartwatch Hardware Telemetry (Wave Call Plus)
  // ------------------------------------------------------------------ //

  async function pollWatchHardware() {
    try {
      const res = await fetch(`${state.apiBase}/api/wearable/devices`);
      if (!res.ok) return;
      const data = await res.json();
      const dot = document.getElementById("hwWatchDot");
      const statusText = document.getElementById("hwWatchStatusText");
      const lastSeen = document.getElementById("hwWatchLastSeen");
      if (data.devices && statusText) {
        const dev = data.devices.find((d) => d.device_id === "DEV-WEARABLE-CALLPLUS") || data.devices[0];
        if (dev) {
          const isConn = dev.connection_status === "CONNECTED";
          if (dot) dot.className = `hw-dot ${isConn ? "is-online" : "is-offline"}`;
          statusText.textContent = dev.connection_status || "DISCONNECTED";
          if (lastSeen && dev.last_seen) {
            lastSeen.textContent = new Date(dev.last_seen).toLocaleTimeString();
          }
        }
      }
    } catch (e) {
      // Offline fallback
    }
  }

  // Initialize
  setupEventListeners();
  poll();
  pollWatchHardware();
  setInterval(pollWatchHardware, 5000);
})();
