/* ==========================================================================
   RIDGEWATCH — 4D Live Digital Twin & Hardware Architecture Engine
   Authoritative 4D Physical Simulation, Real-Time Telemetry Data Flow,
   Wire Protocol Harnesses, Scenario-Aware Sensor Activation, and Live Timeline.
   ========================================================================== */

(() => {
  "use strict";

  // ------------------------------------------------------------------ //
  // Configuration & Static Hardware Registry
  // ------------------------------------------------------------------ //

  const POLL_INTERVAL_MS = 3500;

  const HARDWARE_CAT_COLORS = {
    CONTROLLER:        "#6366f1", // Indigo
    POWER:             "#f59e0b", // Amber
    COMMUNICATION:     "#10b981", // Emerald
    CAMERA:            "#ec4899", // Pink
    SENSOR:            "#06b6d4", // Cyan
    GEOTECHNICAL_NODE: "#8b5cf6", // Purple
  };

  const PROTOCOL_COLORS = {
    I2C:        "#06b6d4", // Cyan
    SPI:        "#ec4899", // Pink
    UART:       "#a855f7", // Purple
    I2S:        "#38bdf8", // Sky Blue
    ADC:        "#3b82f6", // Blue
    GPIO:       "#10b981", // Emerald
    MIPI_CSI:   "#ef4444", // Red
    RS485:      "#f97316", // Orange
    LORA_MESH:  "#10b981", // Green
    USB_POWER:  "#f59e0b", // Amber
    DC_BUS:     "#d97706", // Deep Amber
  };

  const STATUS_COLORS = {
    ONLINE:      "#10b981", // Green
    WARNING:     "#f59e0b", // Yellow/Amber
    CRITICAL:    "#ef4444", // Red
    DEGRADED:    "#f97316", // Orange
    OFFLINE:     "#64748b", // Slate/Gray
    CALIBRATION: "#8b5cf6", // Purple
  };

  // Hardware Metadata & Spatial Coordinates in 3D (relative to Central Hub at 0,0,0)
  const HARDWARE_NODES = [
    // 1. Controllers & Core Processing (Center)
    {
      id: "DEV-CTRL-PI5",
      name: "Raspberry Pi 5 Master AI Core",
      concept: "Raspberry Pi 5 (8GB LPDDR4X, Quad-Core ARM Cortex-A76 @ 2.4GHz)",
      category: "CONTROLLER",
      sensorType: null,
      icon: "🧠",
      unit: "",
      pos: [0, 0.4, 0],
      shape: "pi5_board",
      size: [2.8, 0.4, 2.0],
      color: "#6366f1",
      protocol: "HOST_SYSTEM_BUS",
      port: "HOST_BUS",
      connectedTo: "Base Station Server",
      powerRail: "5.0V / 5.0A DC (USB-C)",
      role: "Edge AI Fusion, SPS Triage, Multi-Modal Correlation & Dispatch Engine",
      scenarios: ["ALL"],
      isSimulated: false,
    },
    {
      id: "DEV-CTRL-ESP32",
      name: "ESP32-S3 Sensor Ingestion MCU",
      concept: "Espressif ESP32-S3 Dual-Core Xtensa LX7 @ 240MHz (512KB SRAM, 8MB PSRAM)",
      category: "CONTROLLER",
      sensorType: null,
      icon: "🎛️",
      unit: "",
      pos: [0, -0.35, 0],
      shape: "esp32_board",
      size: [2.2, 0.3, 1.6],
      color: "#4f46e5",
      protocol: "UART",
      port: "VIRTUAL_UART_BRIDGE",
      connectedTo: "Raspberry Pi 5 (UART0)",
      powerRail: "3.3V / 160mA DC",
      role: "18-Channel Multi-Sensor ADC/I2C/SPI Ingestion & Hardware Boundary Gate",
      scenarios: ["ALL"],
      isSimulated: true,
    },

    // 2. Power Supply & PMU
    {
      id: "DEV-PWR-PMU",
      name: "LiFePO4 PMU Battery Enclosure",
      concept: "7.4V 5000mAh LiFePO4 Battery + TI TPS65219 Multi-Rail PMIC + I2C Gauge",
      category: "POWER",
      sensorType: null,
      icon: "🔋",
      unit: "%",
      pos: [0, -1.15, 0],
      shape: "lifepo4_pmu",
      size: [3.4, 0.7, 2.4],
      color: "#f59e0b",
      protocol: "I2C",
      port: "VIRTUAL_PMIC_I2C (0x5E)",
      connectedTo: "ESP32-S3 & Pi 5 PMU Bus",
      powerRail: "7.4V Pack / Regulated 5V & 3.3V",
      role: "Power distribution, battery fuel gauging, and auxiliary solar charge management",
      scenarios: ["ALL"],
      isSimulated: true,
    },

    // 3. Communication Antennas (Top Rear)
    {
      id: "DEV-COMM-LORA",
      name: "SX1262 LoRa Mesh Transceiver",
      concept: "Semtech SX1262 LoRa Transceiver (868/915 MHz, +22dBm, up to 15km line-of-sight)",
      category: "COMMUNICATION",
      sensorType: null,
      icon: "📡",
      unit: "dBm",
      pos: [-1.4, 1.6, -1.0],
      shape: "antenna_lora",
      size: [0.15, 1.8, 16],
      color: "#10b981",
      protocol: "SPI",
      port: "VIRTUAL_SPI_LORA (CS0)",
      connectedTo: "Raspberry Pi 5 (SPI1)",
      powerRail: "3.3V / 120mA",
      role: "Long-range disaster mesh alert broadcast & field responder synchronization",
      scenarios: ["ALL"],
      isSimulated: true,
    },
    {
      id: "DEV-COMM-CELL",
      name: "BG95-M3 4G-5G Cellular Modem",
      concept: "Quectel BG95-M3 LTE-M / NB-IoT / EGPRS Cellular Gateway Modem",
      category: "COMMUNICATION",
      sensorType: null,
      icon: "📶",
      unit: "RSSI",
      pos: [1.4, 1.6, -1.0],
      shape: "antenna_cell",
      size: [0.12, 1.9, 16],
      color: "#059669",
      protocol: "UART",
      port: "VIRTUAL_UART_MODEM",
      connectedTo: "Raspberry Pi 5 (USB/UART4)",
      powerRail: "3.8V Peak 2A",
      role: "High-throughput cloud command telemetry with automatic fallback to LoRa",
      scenarios: ["ALL"],
      isSimulated: true,
    },

    // 4. Cameras & Optical Turret (Top Front)
    {
      id: "DEV-CAM-01",
      name: "Visible Optical RGB Camera",
      concept: "Raspberry Pi Camera Module v3 (12MP Sony IMX708 with Autofocus & HDR)",
      category: "CAMERA",
      sensorType: "rgb_camera",
      icon: "📷",
      unit: "conf",
      pos: [-0.8, 1.0, 1.2],
      shape: "cam_optical",
      size: [0.8, 0.8, 0.7],
      color: "#ec4899",
      protocol: "MIPI_CSI",
      port: "VIRTUAL_CSI_CAM0",
      connectedTo: "Raspberry Pi 5 (CSI-2)",
      powerRail: "3.3V / 300mA",
      role: "Visible spectrum survivor detection, bounding box classification & debris inspection",
      scenarios: ["earthquake", "flood", "building_collapse", "tsunami", "urban_fire", "wildfire"],
      isSimulated: true,
    },
    {
      id: "DEV-THM-01",
      name: "FLIR Lepton 3.5 LWIR Thermal Camera",
      concept: "Teledyne FLIR Lepton 3.5 Radiometric LWIR Core (160×120, 8-14μm)",
      category: "CAMERA",
      sensorType: "thermal_imaging",
      icon: "🌡️",
      unit: "°C",
      pos: [0.8, 1.0, 1.2],
      shape: "cam_thermal",
      size: [0.85, 0.85, 0.75],
      color: "#f43f5e",
      protocol: "SPI",
      port: "VIRTUAL_SPI_VOSPI + I2C",
      connectedTo: "Raspberry Pi 5 (SPI0 & I2C1)",
      powerRail: "3.3V / 150mA",
      role: "Human body heat signature detection, hypothermia triage, and fire hotspot tracking",
      scenarios: ["avalanche", "wildfire", "urban_fire", "earthquake", "building_collapse", "heatwave"],
      isSimulated: true,
    },

    // 5. Vital Signs Sensors (Front Left Wing)
    {
      id: "DEV-RADAR-01",
      name: "mmWave Heart-Rate & Vital Radar",
      concept: "Texas Instruments IWR6843AOP 60-64GHz mmWave Doppler Radar",
      category: "SENSOR",
      sensorType: "heart_rate_radar",
      icon: "📡",
      unit: "bpm",
      pos: [-2.6, 0.4, 0.8],
      shape: "radar_patch",
      size: [0.9, 0.9, 0.3],
      color: "#06b6d4",
      protocol: "UART",
      port: "VIRTUAL_UART_RADAR",
      connectedTo: "ESP32-S3 (UART1)",
      powerRail: "3.3V / 450mA",
      role: "Sub-millimeter chest wall motion tracking for heart rate and breathing through rubble",
      scenarios: ["earthquake", "avalanche", "building_collapse", "landslide", "infrastructure_entrapment"],
      isSimulated: true,
    },
    {
      id: "DEV-PIR-01",
      name: "Pyroelectric PIR Motion Sensor",
      concept: "Panasonic PaPIRs Dual-Element Pyroelectric Infrared Motion Sensor",
      category: "SENSOR",
      sensorType: "pir_motion",
      icon: "👁️",
      unit: "motion",
      pos: [-3.4, 0.4, 0.2],
      shape: "pir_dome",
      size: [0.4, 16, 16],
      color: "#0891b2",
      protocol: "GPIO",
      port: "VIRTUAL_GPIO_INTR (GPIO 4)",
      connectedTo: "ESP32-S3 (GPIO4)",
      powerRail: "3.3V / 15μA",
      role: "Kinematic survivor motion trigger activating high-rate telemetry capture",
      scenarios: ["earthquake", "building_collapse", "avalanche", "infrastructure_entrapment"],
      isSimulated: true,
    },
    {
      id: "DEV-MIC-01",
      name: "Digital Acoustic MEMS Array",
      concept: "InvenSense INMP441 Omnidirectional Digital I2S Microphone Array",
      category: "SENSOR",
      sensorType: "acoustic",
      icon: "🎙️",
      unit: "dB",
      pos: [-2.6, -0.3, 0.8],
      shape: "mic_mems",
      size: [0.3, 0.3, 16],
      color: "#0284c7",
      protocol: "I2S",
      port: "VIRTUAL_I2S_AUDIO",
      connectedTo: "ESP32-S3 (GPIO25/26/27)",
      powerRail: "3.3V / 1.4mA",
      role: "Acoustic detection of human distress calls, labored breathing, and rhythmic tapping",
      scenarios: ["earthquake", "building_collapse", "avalanche", "infrastructure_entrapment"],
      isSimulated: true,
    },
    {
      id: "DEV-CO2-01",
      name: "NDIR Exhaled CO2 Gas Sensor",
      concept: "Winsen MH-Z19C NDIR Non-Dispersive Infrared CO2 Chamber",
      category: "SENSOR",
      sensorType: "co2",
      icon: "💨",
      unit: "ppm",
      pos: [-3.4, -0.3, 0.2],
      shape: "co2_ndir",
      size: [0.4, 0.7, 16],
      color: "#0369a1",
      protocol: "UART",
      port: "VIRTUAL_UART_CO2",
      connectedTo: "ESP32-S3 (UART2)",
      powerRail: "5.0V / 45mA",
      role: "Exhaled carbon dioxide pocket concentration buildup in collapsed voids",
      scenarios: ["earthquake", "building_collapse", "avalanche", "infrastructure_entrapment"],
      isSimulated: true,
    },

    // 6. Geotechnical & Structural Sensors (Front Right Wing)
    {
      id: "DEV-IMU-01",
      name: "MPU6050 3-Axis Inclinometer (Tilt)",
      concept: "InvenSense MPU-6050 6-DoF Inclinometer & Gravity Vector Sensor",
      category: "SENSOR",
      sensorType: "imu_tilt",
      icon: "📐",
      unit: "°",
      pos: [2.6, 0.4, 0.8],
      shape: "imu_chip",
      size: [0.5, 0.25, 0.5],
      color: "#8b5cf6",
      protocol: "I2C",
      port: "VIRTUAL_I2C_ADDR (0x68)",
      connectedTo: "ESP32-S3 (GPIO21/22)",
      powerRail: "3.3V / 3.8mA",
      role: "Rescue kit orientation, slope angle inclination, and structural shift warning",
      scenarios: ["earthquake", "landslide", "building_collapse"],
      isSimulated: true,
    },
    {
      id: "DEV-IMU-02",
      name: "Seismic Acceleration & Vibration Sensor",
      concept: "MPU-6050 3-Axis Seismic Acceleration & Peak Ground Velocity Channel",
      category: "SENSOR",
      sensorType: "imu_vibration",
      icon: "📳",
      unit: "g",
      pos: [3.4, 0.4, 0.2],
      shape: "imu_chip",
      size: [0.5, 0.25, 0.5],
      color: "#7c3aed",
      protocol: "I2C",
      port: "VIRTUAL_I2C_ADDR (0x68)",
      connectedTo: "ESP32-S3 (GPIO21/22)",
      powerRail: "3.3V / 3.8mA",
      role: "Ground shockwaves, aftershock detection, and debris tremor monitoring",
      scenarios: ["earthquake", "building_collapse", "landslide"],
      isSimulated: true,
    },
    {
      id: "DEV-SOIL-01",
      name: "FDR Volumetric Soil Moisture Probe",
      concept: "Frequency Domain Reflectometry (FDR) High-Precision Ground Soil Moisture Probe",
      category: "SENSOR",
      sensorType: "soil_moisture",
      icon: "🌱",
      unit: "%",
      pos: [2.6, -0.3, 0.8],
      shape: "soil_probe",
      size: [0.25, 1.2, 16],
      color: "#10b981",
      protocol: "ADC",
      port: "VIRTUAL_ADC_CH1",
      connectedTo: "ESP32-S3 (GPIO34)",
      powerRail: "3.3V / 12mA",
      role: "Volumetric soil water content measurement for slope liquefaction forecasting",
      scenarios: ["landslide", "flood", "cloudburst", "dam_failure"],
      isSimulated: true,
    },
    {
      id: "DEV-SLOPE-ARRAY",
      name: "Distributed Slope Telemetry Array",
      concept: "3× Geotechnical Array Nodes (SLOPE-01: Upper, SLOPE-02: Mid, SLOPE-03: Base)",
      category: "GEOTECHNICAL_NODE",
      sensorType: null,
      icon: "⛰️",
      unit: "Risk",
      pos: [3.4, -0.3, 0.2],
      shape: "slope_array",
      size: [0.4, 0.8, 16],
      color: "#059669",
      protocol: "RS485",
      port: "VIRTUAL_RS485_SLOPE_BUS",
      connectedTo: "ESP32-S3 (GPIO32/33)",
      powerRail: "5.0V / 36mA",
      role: "3-node slope telemetry mesh reporting synchronized soil moisture and tilt gradients",
      scenarios: ["landslide", "cloudburst"],
      isSimulated: true,
    },

    // 7. Hydrological Sensors (Bottom Front Outriggers)
    {
      id: "DEV-WATER-01",
      name: "Hydrostatic Water-Level Submersible Probe",
      concept: "Piezoresistive Submersible 316L Stainless Steel Pressure Transducer (0-20m)",
      category: "SENSOR",
      sensorType: "water_level",
      icon: "💧",
      unit: "cm",
      pos: [-1.8, -1.0, 1.6],
      shape: "water_probe",
      size: [0.35, 1.4, 16],
      color: "#38bdf8",
      protocol: "ADC",
      port: "VIRTUAL_ADC_CH0",
      connectedTo: "ESP32-S3 (GPIO35)",
      powerRail: "5.0V / 20mA",
      role: "Rising flood water depth, submergence detection, and rate-of-rise computation",
      scenarios: ["flood", "tsunami", "dam_failure", "cloudburst"],
      isSimulated: true,
    },
    {
      id: "DEV-WFLOW-01",
      name: "Acoustic Doppler Water Flow Sensor",
      concept: "Compact Acoustic Doppler Current Profiler / Flow Velocity Meter (0-25 m/s)",
      category: "SENSOR",
      sensorType: "water_flow",
      icon: "🌊",
      unit: "m/s",
      pos: [1.8, -1.0, 1.6],
      shape: "flow_doppler",
      size: [0.35, 1.4, 16],
      color: "#0284c7",
      protocol: "UART",
      port: "VIRTUAL_UART_FLOW",
      connectedTo: "ESP32-S3 (GPIO12/13)",
      powerRail: "5.0V / 35mA",
      role: "Flood current speed, hydraulic force, and hazardous swift-water velocity tracking",
      scenarios: ["flood", "tsunami", "dam_failure"],
      isSimulated: true,
    },

    // 8. Meteorological & Environmental Pod (Rear Left/Right)
    {
      id: "DEV-RAIN-01",
      name: "Optical Infrared Rain Disdrometer",
      concept: "RG-11 Optical Solid-State Precipitation Sensor (up to 500 mm/h)",
      category: "SENSOR",
      sensorType: "rainfall_intensity",
      icon: "🌧️",
      unit: "mm/h",
      pos: [-2.2, 0.8, -1.4],
      shape: "rain_optical",
      size: [0.45, 16, 16],
      color: "#38bdf8",
      protocol: "GPIO",
      port: "VIRTUAL_GPIO_PULSE (GPIO 18)",
      connectedTo: "ESP32-S3 (GPIO19)",
      powerRail: "5.0V / 15mA",
      role: "Precipitation rate (mm/h) and cumulative rainfall volume (mm) monitoring",
      scenarios: ["flood", "landslide", "cyclone", "cloudburst"],
      isSimulated: true,
    },
    {
      id: "DEV-BARO-01",
      name: "BMP280 Precision Barometer",
      concept: "Bosch Sensortec BMP280 Digital Barometric Pressure Sensor (300-1100 hPa)",
      category: "SENSOR",
      sensorType: "barometric_pressure",
      icon: "⏱️",
      unit: "hPa",
      pos: [-1.4, 0.8, -1.4],
      shape: "baro_chip",
      size: [0.4, 0.2, 0.4],
      color: "#60a5fa",
      protocol: "I2C",
      port: "VIRTUAL_I2C_ADDR (0x76)",
      connectedTo: "ESP32-S3 (GPIO21/22)",
      powerRail: "3.3V / 3μA",
      role: "Atmospheric pressure, cyclonic drop severity, and storm pressure anomaly detection",
      scenarios: ["cyclone", "flood", "cloudburst", "avalanche"],
      isSimulated: true,
    },
    {
      id: "DEV-GAS-01",
      name: "MQ-135 Multi-Gas Toxic Sensor",
      concept: "MQ-135 Multi-Gas MOX / Bosch BME680 Environmental Gas Sensor (0-50,000 PPM)",
      category: "SENSOR",
      sensorType: "gas_concentration",
      icon: "☣️",
      unit: "ppm",
      pos: [1.4, 0.8, -1.4],
      shape: "gas_mox",
      size: [0.4, 0.4, 16],
      color: "#eab308",
      protocol: "ADC",
      port: "VIRTUAL_ADC_CH2",
      connectedTo: "ESP32-S3 (GPIO36)",
      powerRail: "5.0V / 150mA",
      role: "Toxic, combustible, and hazardous chemical gas concentration monitoring (PPM)",
      scenarios: ["chemical_leak", "industrial_accident", "urban_fire", "wildfire"],
      isSimulated: true,
    },
    {
      id: "DEV-SMK-01",
      name: "Laser Optical Smoke & Particulate Sensor",
      concept: "Plantower PMS5003 Laser Particulate Obscuration Sensor (0-100%)",
      category: "SENSOR",
      sensorType: "smoke_density",
      icon: "🌫️",
      unit: "%",
      pos: [2.2, 0.8, -1.4],
      shape: "smoke_laser",
      size: [0.5, 0.35, 0.5],
      color: "#94a3b8",
      protocol: "UART",
      port: "VIRTUAL_UART_SMOKE",
      connectedTo: "ESP32-S3 (GPIO14/15)",
      powerRail: "5.0V / 100mA",
      role: "Laser optical smoke density and particulate obscuration percentage measurement",
      scenarios: ["urban_fire", "wildfire", "industrial_accident", "chemical_leak"],
      isSimulated: true,
    },
    {
      id: "DEV-TEMP-01",
      name: "SHT31 Ambient Temperature Sensor",
      concept: "Sensirion SHT31 Calibrated Bandgap Ambient Temperature Sensor (-40 to +125°C)",
      category: "SENSOR",
      sensorType: "temperature",
      icon: "🌡️",
      unit: "°C",
      pos: [-0.6, 0.8, -1.4],
      shape: "temp_sht",
      size: [0.35, 0.2, 0.35],
      color: "#fb923c",
      protocol: "I2C",
      port: "VIRTUAL_I2C_ADDR (0x70)",
      connectedTo: "ESP32-S3 (GPIO21/22)",
      powerRail: "3.3V / 2μA",
      role: "Ambient temperature measurement, hypothermia risk detection, and thermal baselining",
      scenarios: ["avalanche", "heatwave", "wildfire", "urban_fire", "drought"],
      isSimulated: true,
    },
    {
      id: "DEV-HUMID-01",
      name: "SHT31 Relative Humidity Sensor",
      concept: "Sensirion SHT31 Capacitive Polymer Relative Humidity Sensor (0-100% RH)",
      category: "SENSOR",
      sensorType: "humidity",
      icon: "💧",
      unit: "%",
      pos: [0.6, 0.8, -1.4],
      shape: "temp_sht",
      size: [0.35, 0.2, 0.35],
      color: "#38bdf8",
      protocol: "I2C",
      port: "VIRTUAL_I2C_ADDR (0x70)",
      connectedTo: "ESP32-S3 (GPIO21/22)",
      powerRail: "3.3V / 2μA",
      role: "Atmospheric relative humidity, storm saturation tracking, and moisture baselining",
      scenarios: ["flood", "cyclone", "cloudburst", "drought", "wildfire"],
      isSimulated: true,
    },

    // 9. Geospatial Positioning (Top Mast)
    {
      id: "DEV-GPS-01",
      name: "u-blox NEO-M9N GNSS Receiver",
      concept: "u-blox NEO-M9N Multi-Constellation (GPS, GLONASS, Galileo, BeiDou) 92-Ch GNSS",
      category: "SENSOR",
      sensorType: "gps",
      icon: "🛰️",
      unit: "sats",
      pos: [0, 1.8, -0.4],
      shape: "gps_helix",
      size: [0.35, 0.6, 16],
      color: "#3b82f6",
      protocol: "UART",
      port: "VIRTUAL_UART_GNSS",
      connectedTo: "ESP32-S3 (GPIO9/10)",
      powerRail: "3.3V / 35mA",
      role: "Centimeter-to-meter 3D location coordinates, altitude, satellite lock & fix quality",
      scenarios: ["ALL"],
      isSimulated: true,
    },
  ];

  // Canonical Topology Connections from backend/hardware_registry.py
  const HARDWARE_CONNECTIONS = [
    { sourceId: "DEV-PWR-PMU", targetId: "DEV-CTRL-PI5", protocol: "USB_POWER", pinMapping: "VOUT_5V -> USB-C VBUS", powerRail: "5.0V / 5.0A", dataLine: "I2C Telemetry Bus" },
    { sourceId: "DEV-PWR-PMU", targetId: "DEV-CTRL-ESP32", protocol: "DC_BUS", pinMapping: "VOUT_3V3 -> ESP32 3V3", powerRail: "3.3V / 1.0A", dataLine: "Power Only" },
    { sourceId: "DEV-PWR-PMU", targetId: "DEV-COMM-LORA", protocol: "DC_BUS", pinMapping: "VOUT_3V3 -> SX1262 VDD", powerRail: "3.3V", dataLine: "Power Only" },
    { sourceId: "DEV-PWR-PMU", targetId: "DEV-COMM-CELL", protocol: "DC_BUS", pinMapping: "VOUT_VBAT -> BG95 VBAT", powerRail: "3.8V Peak 2A", dataLine: "Power Only" },
    { sourceId: "DEV-CTRL-ESP32", targetId: "DEV-CTRL-PI5", protocol: "UART", pinMapping: "ESP32 TX/RX -> Pi 5 GPIO14/15 (UART0)", powerRail: "3.3V Logic", dataLine: "Telemetry Stream Buffer (2 Mbps)" },
    { sourceId: "DEV-RADAR-01", targetId: "DEV-CTRL-ESP32", protocol: "UART", pinMapping: "Radar TX/RX -> ESP32 GPIO17/18 (UART1)", powerRail: "3.3V DC", dataLine: "Point Cloud & Doppler Bin Stream" },
    { sourceId: "DEV-PIR-01", targetId: "DEV-CTRL-ESP32", protocol: "GPIO", pinMapping: "PIR OUT -> ESP32 GPIO4 (INT)", powerRail: "3.3V DC", dataLine: "Motion Interrupt Pulse" },
    { sourceId: "DEV-MIC-01", targetId: "DEV-CTRL-ESP32", protocol: "I2S", pinMapping: "INMP441 SD/WS/SCK -> ESP32 GPIO25/26/27", powerRail: "3.3V DC", dataLine: "24-bit Digital Audio PCM Stream" },
    { sourceId: "DEV-CO2-01", targetId: "DEV-CTRL-ESP32", protocol: "UART", pinMapping: "MH-Z19 TX/RX -> ESP32 GPIO16/17 (UART2)", powerRail: "5.0V DC", dataLine: "CO2 Gas Concentration Frame" },
    { sourceId: "DEV-IMU-01", targetId: "DEV-CTRL-ESP32", protocol: "I2C", pinMapping: "MPU6050 SDA/SCL -> ESP32 GPIO21/22", powerRail: "3.3V DC", dataLine: "3-Axis Tilt Inclinometer Bus (0x68)" },
    { sourceId: "DEV-IMU-02", targetId: "DEV-CTRL-ESP32", protocol: "I2C", pinMapping: "MPU6050 SDA/SCL -> ESP32 GPIO21/22", powerRail: "3.3V DC", dataLine: "Seismic Acceleration Bus (0x68)" },
    { sourceId: "DEV-SOIL-01", targetId: "DEV-CTRL-ESP32", protocol: "ADC", pinMapping: "FDR Analog Out -> ESP32 GPIO34 (ADC1_CH6)", powerRail: "3.3V DC", dataLine: "Volumetric Soil Saturation Voltage" },
    { sourceId: "DEV-SLOPE-ARRAY", targetId: "DEV-CTRL-ESP32", protocol: "RS485", pinMapping: "MAX485 RO/DI -> ESP32 GPIO32/33", powerRail: "5.0V DC", dataLine: "3-Node Differential Geotechnical Mesh" },
    { sourceId: "DEV-WATER-01", targetId: "DEV-CTRL-ESP32", protocol: "ADC", pinMapping: "Hydrostatic Probe -> ESP32 GPIO35 (ADC1_CH7)", powerRail: "5.0V DC", dataLine: "4-20mA Flood Depth Loop" },
    { sourceId: "DEV-WFLOW-01", targetId: "DEV-CTRL-ESP32", protocol: "UART", pinMapping: "Doppler TX/RX -> ESP32 GPIO12/13", powerRail: "5.0V DC", dataLine: "Flow Velocity Stream (m/s)" },
    { sourceId: "DEV-RAIN-01", targetId: "DEV-CTRL-ESP32", protocol: "GPIO", pinMapping: "RG-11 Pulse -> ESP32 GPIO19 (INT)", powerRail: "5.0V DC", dataLine: "Precipitation Disdrometer Pulses" },
    { sourceId: "DEV-BARO-01", targetId: "DEV-CTRL-ESP32", protocol: "I2C", pinMapping: "BMP280 SDA/SCL -> ESP32 GPIO21/22", powerRail: "3.3V DC", dataLine: "Barometric Pressure I2C Bus (0x76)" },
    { sourceId: "DEV-GAS-01", targetId: "DEV-CTRL-ESP32", protocol: "ADC", pinMapping: "MQ-135 AOUT -> ESP32 GPIO36 (ADC1_CH0)", powerRail: "5.0V DC", dataLine: "Multi-Gas MOX Analog Signal" },
    { sourceId: "DEV-SMK-01", targetId: "DEV-CTRL-ESP32", protocol: "UART", pinMapping: "PMS5003 TX/RX -> ESP32 GPIO14/15", powerRail: "5.0V DC", dataLine: "Laser Optical Smoke Obscuration Frame" },
    { sourceId: "DEV-TEMP-01", targetId: "DEV-CTRL-ESP32", protocol: "I2C", pinMapping: "SHT31 SDA/SCL -> ESP32 GPIO21/22", powerRail: "3.3V DC", dataLine: "Ambient Air Temp I2C (0x70)" },
    { sourceId: "DEV-HUMID-01", targetId: "DEV-CTRL-ESP32", protocol: "I2C", pinMapping: "SHT31 SDA/SCL -> ESP32 GPIO21/22", powerRail: "3.3V DC", dataLine: "Relative Humidity I2C (0x70)" },
    { sourceId: "DEV-GPS-01", targetId: "DEV-CTRL-ESP32", protocol: "UART", pinMapping: "NEO-M9N TX/RX -> ESP32 GPIO9/10", powerRail: "3.3V DC", dataLine: "NMEA / UBX GNSS Navigation Stream" },
    { sourceId: "DEV-CAM-01", targetId: "DEV-CTRL-PI5", protocol: "MIPI_CSI", pinMapping: "2-Lane MIPI CSI-2 15-pin Ribbon", powerRail: "3.3V / 1.8V", dataLine: "1080p Optical RGB Frame Stream" },
    { sourceId: "DEV-THM-01", targetId: "DEV-CTRL-PI5", protocol: "SPI", pinMapping: "VoSPI (MISO/SCK/CS) + I2C Control", powerRail: "3.3V DC", dataLine: "Radiometric 160x120 LWIR Heat Frame" },
    { sourceId: "DEV-COMM-LORA", targetId: "DEV-CTRL-PI5", protocol: "SPI", pinMapping: "SPI1 (MOSI/MISO/SCK/CS0) + GPIO5", powerRail: "3.3V DC", dataLine: "LoRa Packet RX/TX Buffer" },
    { sourceId: "DEV-COMM-CELL", targetId: "DEV-CTRL-PI5", protocol: "UART", pinMapping: "USB Virtual COM / UART4 (TX/RX)", powerRail: "3.8V Peak 2A", dataLine: "Cellular IP Socket & MQTT Telemetry" },
  ];

  // ------------------------------------------------------------------ //
  // Application State (Single Source of Truth)
  // ------------------------------------------------------------------ //

  const state = {
    get apiBase() { return RidgeWatchConfig.getApiBase(); },
    visualMode: "4D", // "2D" | "3D" | "4D"
    selectedScenario: "ALL",
    selectedDeviceId: null,
    selectedConnection: null,
    showDataFlow: true,
    showPipeline: false,
    showInventory: false,
    isFullView: false,
    autoRotate: false,
    showWires: true,
    showLabels: true,
    categoryFilter: "ALL",
    searchQuery: "",
    liveTelemetry: {},
    profile: null,
    hardwareInventory: HARDWARE_NODES,
    connections: HARDWARE_CONNECTIONS,
    scenarioRunning: false,
    isRealHardware: false,
  };

  // ------------------------------------------------------------------ //
  // DOM Elements
  // ------------------------------------------------------------------ //

  const el = {
    viewport3D: document.getElementById("dtViewport3D"),
    viewport2D: document.getElementById("dtViewport2D"),
    canvas3D: document.getElementById("dtCanvas3D"),
    schematicSvg: document.getElementById("dtSchematicSvg"),
    btnView2D: document.getElementById("btnView2D"),
    btnView3D: document.getElementById("btnView3D"),
    btnView4D: document.getElementById("btnView4D"),
    dtSourceBadgeLabel: document.getElementById("dtSourceBadgeLabel"),
    btnToggleFullView: document.getElementById("btnToggleFullView"),
    lblFullView: document.getElementById("lblFullView"),
    btnToggleDataFlow: document.getElementById("btnToggleDataFlow"),
    lblDataFlow: document.getElementById("lblDataFlow"),
    btnTogglePipeline: document.getElementById("btnTogglePipeline"),
    btnToggleInventory: document.getElementById("btnToggleInventory"),
    dtKpiTotal: document.getElementById("dtKpiTotal"),
    dtKpiOnline: document.getElementById("dtKpiOnline"),
    dtKpiWarning: document.getElementById("dtKpiWarning"),
    dtKpiCritical: document.getElementById("dtKpiCritical"),
    dtActiveScenarioLabel: document.getElementById("dtActiveScenarioLabel"),
    dtLiveStreamState: document.getElementById("dtLiveStreamState"),
    dtTooltip: document.getElementById("dtTooltip"),
    dtTooltipIcon: document.getElementById("dtTooltipIcon"),
    dtTooltipName: document.getElementById("dtTooltipName"),
    dtTooltipMeta: document.getElementById("dtTooltipMeta"),
    dtDetailDrawer: document.getElementById("dtDetailDrawer"),
    btnDetailClose: document.getElementById("btnDetailClose"),
    dtDetailIcon: document.getElementById("dtDetailIcon"),
    dtDetailName: document.getElementById("dtDetailName"),
    dtDetailId: document.getElementById("dtDetailId"),
    dtDetailCategory: document.getElementById("dtDetailCategory"),
    dtDetailSimLabel: document.getElementById("dtDetailSimLabel"),
    dtDetailStatusBadge: document.getElementById("dtDetailStatusBadge"),
    dtDetailConcept: document.getElementById("dtDetailConcept"),
    dtDetailDesc: document.getElementById("dtDetailDesc"),
    dtLivePrimaryVal: document.getElementById("dtLivePrimaryVal"),
    dtLiveTrendVal: document.getElementById("dtLiveTrendVal"),
    dtLiveQualityVal: document.getElementById("dtLiveQualityVal"),
    dtDetailProtocol: document.getElementById("dtDetailProtocol"),
    dtDetailInterfaceNature: document.getElementById("dtDetailInterfaceNature"),
    dtDetailVirtualPort: document.getElementById("dtDetailVirtualPort"),
    dtDetailConnectedTo: document.getElementById("dtDetailConnectedTo"),
    dtDetailPowerRail: document.getElementById("dtDetailPowerRail"),
    dtDetailScenTags: document.getElementById("dtDetailScenTags"),
    btnDetailFocus: document.getElementById("btnDetailFocus"),
    btnStationTelemetry: document.getElementById("btnStationTelemetry"),
    dtConnectionInspector: document.getElementById("dtConnectionInspector"),
    btnConnClose: document.getElementById("btnConnClose"),
    dtConnId: document.getElementById("dtConnId"),
    dtConnSource: document.getElementById("dtConnSource"),
    dtConnProto: document.getElementById("dtConnProto"),
    dtConnTarget: document.getElementById("dtConnTarget"),
    dtConnProtocol: document.getElementById("dtConnProtocol"),
    dtConnPinMapping: document.getElementById("dtConnPinMapping"),
    dtConnPowerRail: document.getElementById("dtConnPowerRail"),
    dtConnDataLine: document.getElementById("dtConnDataLine"),
    dtConnStatus: document.getElementById("dtConnStatus"),
    dtInventoryDrawer: document.getElementById("dtInventoryDrawer"),
    btnInventoryClose: document.getElementById("btnInventoryClose"),
    dtInvCountBadge: document.getElementById("dtInvCountBadge"),
    dtInvSearchInput: document.getElementById("dtInvSearchInput"),
    dtInvSearchClear: document.getElementById("dtInvSearchClear"),
    dtInvCatPills: document.getElementById("dtInvCatPills"),
    dtInventoryList: document.getElementById("dtInventoryList"),
    dtPipelineSection: document.getElementById("dtPipelineSection"),
    btnPipelineClose: document.getElementById("btnPipelineClose"),
    dtStatusMessage: document.getElementById("dtStatusMessage"),
    dtStatusFps: document.getElementById("dtStatusFps"),
    btnCamFitAll: document.getElementById("btnCamFitAll"),
    btnCamReset: document.getElementById("btnCamReset"),
    btnCamTop: document.getElementById("btnCamTop"),
    btnCamFront: document.getElementById("btnCamFront"),
    btnCamIso: document.getElementById("btnCamIso"),
    btnCamRotate: document.getElementById("btnCamRotate"),
    btnCamWires: document.getElementById("btnCamWires"),
    btnCamLabels: document.getElementById("btnCamLabels"),
  };

  // ------------------------------------------------------------------ //
  // Three.js 3D/4D Digital Twin Engine
  // ------------------------------------------------------------------ //

  let scene, camera, renderer, controls;
  let raycaster, mouse;
  let meshGroup, wiringGroup, particleGroup, fovGroup, labelsGroup;
  let deviceMeshMap = new Map();
  let wireMeshMap = new Map();
  let wireCurves = [];
  let flowParticles = [];
  let hoveredMesh = null;
  let hoveredWire = null;
  let targetCamPos = null;
  let targetLookAt = null;
  let thermalConeMesh = null;
  let opticalConeMesh = null;
  let radarRings = [];

  function init3D() {
    if (!window.THREE) {
      console.warn("Three.js not loaded. Falling back to 2D schematic mode.");
      switchView("2D");
      return;
    }

    const container = el.viewport3D;
    const width = container.clientWidth || window.innerWidth - 260;
    const height = container.clientHeight || window.innerHeight - 150;

    // 1. Scene - White + Blue RIDGEWATCH Theme
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f6fc);
    scene.fog = new THREE.FogExp2(0xf0f6fc, 0.025);

    // 2. Camera
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(7.5, 6.0, 9.0);

    // 3. Renderer
    renderer = new THREE.WebGLRenderer({ canvas: el.canvas3D, antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // 4. OrbitControls
    if (window.THREE.OrbitControls) {
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.06;
      controls.maxDistance = 30;
      controls.minDistance = 1.5;
      controls.maxPolarAngle = Math.PI / 2 + 0.1;
      controls.target.set(0, 0.2, 0);
    }

    // 5. Lighting - Crisp Clean Engineering Illumination
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.95);
    dirLight1.position.set(10, 15, 10);
    dirLight1.castShadow = true;
    dirLight1.shadow.mapSize.width = 1024;
    dirLight1.shadow.mapSize.height = 1024;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x93c5fd, 0.45); // Soft blue fill light
    dirLight2.position.set(-10, 8, -10);
    scene.add(dirLight2);

    const floorLight = new THREE.DirectionalLight(0xbfdbfe, 0.3);
    floorLight.position.set(0, -10, 0);
    scene.add(floorLight);

    // 6. Floor Grid & Platform Base
    const grid = new THREE.GridHelper(24, 48, 0x93c5fd, 0xdbeafe);
    grid.position.y = -1.6;
    scene.add(grid);

    // Hexagonal platform base
    const platGeo = new THREE.CylinderGeometry(5.4, 5.8, 0.12, 6);
    const platMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.6,
      metalness: 0.1,
    });
    const platform = new THREE.Mesh(platGeo, platMat);
    platform.position.y = -1.66;
    platform.receiveShadow = true;
    scene.add(platform);

    // Platform border ring - RIDGEWATCH Primary Blue
    const ringGeo = new THREE.RingGeometry(5.7, 5.85, 6);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x2563eb, side: THREE.DoubleSide });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = -1.59;
    scene.add(ring);

    // 7. Groups
    meshGroup = new THREE.Group();
    wiringGroup = new THREE.Group();
    particleGroup = new THREE.Group();
    fovGroup = new THREE.Group();
    scene.add(meshGroup);
    scene.add(wiringGroup);
    scene.add(particleGroup);
    scene.add(fovGroup);

    // 8. Build Physical Hardware Geometry
    buildHardwareScene();

    // 9. Raycaster for Mouse Hover & Selection
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();

    // 10. Event Listeners
    window.addEventListener("resize", onWindowResize);
    el.canvas3D.addEventListener("mousemove", onMouseMove);
    el.canvas3D.addEventListener("click", onMouseClick);

    // 11. Start Animation Loop
    animate();
  }

  // ------------------------------------------------------------------ //
  // Procedural Physical Hardware Geometry Builders
  // ------------------------------------------------------------------ //

  function buildHardwareScene() {
    // Clear previous
    while (meshGroup.children.length > 0) meshGroup.remove(meshGroup.children[0]);
    while (wiringGroup.children.length > 0) wiringGroup.remove(wiringGroup.children[0]);
    while (fovGroup.children.length > 0) fovGroup.remove(fovGroup.children[0]);
    deviceMeshMap.clear();
    wireMeshMap.clear();
    wireCurves = [];
    radarRings = [];

    // 1. Build Industrial Deployable Station Chassis & Structural Mounts
    buildRescueStationChassis();

    // 2. Loop through each hardware asset and build authentic real-product procedural 3D model
    HARDWARE_NODES.forEach((dev) => {
      const obj3D = createProceduralHardwareModel(dev);
      obj3D.position.set(dev.pos[0], dev.pos[1], dev.pos[2]);
      obj3D.userData = { device: dev };
      meshGroup.add(obj3D);
      deviceMeshMap.set(dev.id, obj3D);
    });

    // 3. Build 3D Wiring Harnesses Connecting Hardware
    buildPhysicalWiring();

    // 4. Create 3D Flow Particles along Wiring Curves
    createDataFlowParticles();
  }

  // Build Industrial Aluminum Extrusion Station Frame & Mounting Arms
  function buildRescueStationChassis() {
    const chassisGroup = new THREE.Group();

    const metalMat = new THREE.MeshStandardMaterial({
      color: 0x334155,
      metalness: 0.85,
      roughness: 0.25,
    });
    const darkMetalMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.7,
      roughness: 0.4,
    });
    const accentMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      metalness: 0.8,
      roughness: 0.2,
    });

    // Central Vertical Mast (2020 Aluminum Extrusion Profile)
    const mastGeo = new THREE.BoxGeometry(0.35, 3.2, 0.35);
    const mast = new THREE.Mesh(mastGeo, metalMat);
    mast.position.set(0, 0.2, -0.3);
    mast.castShadow = true;
    mast.receiveShadow = true;
    chassisGroup.add(mast);

    // Controller Central Mounting Plate (Between Pi 5 and ESP32)
    const plateGeo = new THREE.BoxGeometry(3.6, 0.1, 2.6);
    const plate = new THREE.Mesh(plateGeo, darkMetalMat);
    plate.position.set(0, -0.05, -0.3);
    plate.receiveShadow = true;
    chassisGroup.add(plate);

    // Lower Battery Cradle
    const cradleGeo = new THREE.BoxGeometry(3.8, 0.08, 2.6);
    const cradle = new THREE.Mesh(cradleGeo, darkMetalMat);
    cradle.position.set(0, -1.35, 0);
    chassisGroup.add(cradle);

    // Upper Antenna & GNSS Mast Cross-Arm
    const topArmGeo = new THREE.BoxGeometry(3.2, 0.15, 0.2);
    const topArm = new THREE.Mesh(topArmGeo, metalMat);
    topArm.position.set(0, 1.45, -0.8);
    chassisGroup.add(topArm);

    // Front Camera / Radar Gimbal Arm
    const frontArmGeo = new THREE.BoxGeometry(2.4, 0.12, 1.4);
    const frontArm = new THREE.Mesh(frontArmGeo, darkMetalMat);
    frontArm.position.set(0, 0.75, 0.8);
    chassisGroup.add(frontArm);

    // Left Vital Sensors Bracket
    const leftBracketGeo = new THREE.BoxGeometry(1.6, 0.08, 1.2);
    const leftBracket = new THREE.Mesh(leftBracketGeo, darkMetalMat);
    leftBracket.position.set(-2.8, 0.15, 0.5);
    chassisGroup.add(leftBracket);

    // Right Geotechnical Sensors Bracket
    const rightBracketGeo = new THREE.BoxGeometry(1.6, 0.08, 1.2);
    const rightBracket = new THREE.Mesh(rightBracketGeo, darkMetalMat);
    rightBracket.position.set(2.8, 0.15, 0.5);
    chassisGroup.add(rightBracket);

    // Rear Meteorological Arms
    const rearLeftArmGeo = new THREE.CylinderGeometry(0.06, 0.06, 2.2, 12);
    const rearLeftArm = new THREE.Mesh(rearLeftArmGeo, metalMat);
    rearLeftArm.rotation.z = Math.PI / 2;
    rearLeftArm.position.set(-1.6, 0.65, -1.4);
    chassisGroup.add(rearLeftArm);

    const rearRightArmGeo = new THREE.CylinderGeometry(0.06, 0.06, 2.2, 12);
    const rearRightArm = new THREE.Mesh(rearRightArmGeo, metalMat);
    rearRightArm.rotation.z = Math.PI / 2;
    rearRightArm.position.set(1.6, 0.65, -1.4);
    chassisGroup.add(rearRightArm);

    // Base Support Legs & Footing Pads
    for (let i = 0; i < 3; i++) {
      const angle = (i * Math.PI * 2) / 3;
      const legGeo = new THREE.CylinderGeometry(0.08, 0.08, 1.8, 12);
      const leg = new THREE.Mesh(legGeo, metalMat);
      leg.position.set(Math.cos(angle) * 1.6, -1.0, Math.sin(angle) * 1.6);
      leg.rotation.z = Math.cos(angle) * 0.45;
      leg.rotation.x = Math.sin(angle) * 0.45;
      chassisGroup.add(leg);

      const footGeo = new THREE.CylinderGeometry(0.28, 0.32, 0.08, 16);
      const foot = new THREE.Mesh(footGeo, accentMat);
      foot.position.set(Math.cos(angle) * 2.4, -1.58, Math.sin(angle) * 2.4);
      chassisGroup.add(foot);
    }

    meshGroup.add(chassisGroup);
  }

  // Create Holographic 3D Floating Billboards / Labels
  function createHolographicBadge(title, subtitle, icon, colorHex) {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 140;
    const ctx = canvas.getContext("2d");

    // Glassmorphism Rounded Pill
    ctx.fillStyle = "rgba(10, 15, 30, 0.88)";
    ctx.strokeStyle = colorHex || "#38bdf8";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.roundRect(8, 8, 496, 124, 24);
    ctx.fill();
    ctx.stroke();

    // Subtle Glow Header Strip
    ctx.fillStyle = colorHex || "#38bdf8";
    ctx.beginPath();
    ctx.roundRect(8, 8, 496, 14, [24, 24, 0, 0]);
    ctx.fill();

    // Icon & Title
    ctx.font = "bold 34px 'Space Grotesk', sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(`${icon} ${title}`, 28, 64);

    // Subtitle / Concept / Role
    ctx.font = "500 22px 'JetBrains Mono', monospace";
    ctx.fillStyle = "#94a3b8";
    ctx.fillText(subtitle, 28, 102);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.92 });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.5, 0.42, 1.0);
    return sprite;
  }

  function createProceduralHardwareModel(dev) {
    const group = new THREE.Group();
    let primaryMat = new THREE.MeshStandardMaterial({
      color: dev.color,
      roughness: 0.35,
      metalness: 0.6,
      emissive: new THREE.Color(dev.color).multiplyScalar(0.12),
    });

    if (dev.shape === "pi5_board") {
      // -------------------------------------------------------------- //
      // 1. RASPBERRY PI 5 (EDGE AI & MASTER CONTROLLER)
      // -------------------------------------------------------------- //
      // Green 6-layer PCB
      const pcbGeo = new THREE.BoxGeometry(3.2, 0.14, 2.2);
      const pcbMat = new THREE.MeshStandardMaterial({ color: 0x0f5132, roughness: 0.6 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      group.add(pcb);

      // 4 Brass Plated Mounting Holes
      const holeMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.9 });
      const holeGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.16, 12);
      [[-1.3, -0.85], [1.3, -0.85], [-1.3, 0.85], [1.3, 0.85]].forEach(([hx, hz]) => {
        const h = new THREE.Mesh(holeGeo, holeMat);
        h.position.set(hx, 0, hz);
        group.add(h);
      });

      // Broadcom BCM2712 SoC Processor with Aluminum Heatspreader
      const socGeo = new THREE.BoxGeometry(0.75, 0.12, 0.75);
      const socMat = new THREE.MeshStandardMaterial({ color: 0xd1d5db, metalness: 0.95, roughness: 0.15 });
      const soc = new THREE.Mesh(socGeo, socMat);
      soc.position.set(-0.25, 0.12, -0.1);
      group.add(soc);

      // RP1 I/O Controller Chip & DA9091 PMIC
      const rp1Geo = new THREE.BoxGeometry(0.45, 0.08, 0.45);
      const rp1Mat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 });
      const rp1 = new THREE.Mesh(rp1Geo, rp1Mat);
      rp1.position.set(0.65, 0.1, -0.1);
      group.add(rp1);

      // Shielded Gigabit Ethernet Jack (Right Edge)
      const ethGeo = new THREE.BoxGeometry(0.65, 0.58, 0.6);
      const ethMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.85 });
      const eth = new THREE.Mesh(ethGeo, ethMat);
      eth.position.set(1.35, 0.35, -0.5);
      group.add(eth);

      // Dual Stacked USB 3.0 Ports (Blue Core)
      const usb3Geo = new THREE.BoxGeometry(0.65, 0.55, 0.55);
      const usb3Mat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.7 });
      const usb3 = new THREE.Mesh(usb3Geo, usb3Mat);
      usb3.position.set(1.35, 0.33, 0.45);
      group.add(usb3);

      // 40-Pin GPIO Header (Top Edge, Black Shroud + 40 Gold Pins)
      const gpioGeo = new THREE.BoxGeometry(2.0, 0.28, 0.22);
      const gpioMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.9 });
      const gpio = new THREE.Mesh(gpioGeo, gpioMat);
      gpio.position.set(-0.25, 0.2, -0.9);
      group.add(gpio);

      // Dual MIPI CSI Camera Connectors (White Plastic Sockets)
      const csiMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.5 });
      const csiGeo = new THREE.BoxGeometry(0.45, 0.12, 0.15);
      const csi1 = new THREE.Mesh(csiGeo, csiMat);
      csi1.position.set(-0.9, 0.12, 0.8);
      const csi2 = csi1.clone();
      csi2.position.set(-0.2, 0.12, 0.8);
      group.add(csi1);
      group.add(csi2);

      // Dual Micro-HDMI and USB-C Power Ports (Bottom Edge)
      const hdmiGeo = new THREE.BoxGeometry(0.3, 0.14, 0.2);
      const portMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9 });
      const hdmi1 = new THREE.Mesh(hdmiGeo, portMat);
      hdmi1.position.set(-0.5, 0.12, 1.05);
      const hdmi2 = hdmi1.clone();
      hdmi2.position.set(0.1, 0.12, 1.05);
      const usbc = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.14, 0.25), portMat);
      usbc.position.set(-1.1, 0.12, 1.05);
      group.add(hdmi1);
      group.add(hdmi2);
      group.add(usbc);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("Raspberry Pi 5", "EDGE AI / CONTROL", "⚡", "#10b981");
      badge.position.set(0, 1.1, 0);
      group.add(badge);

      group.userData.mainMesh = pcb;

    } else if (dev.shape === "esp32_board") {
      // -------------------------------------------------------------- //
      // 2. ESP32-S3 (SENSOR DATA ACQUISITION & REAL-TIME MCU)
      // -------------------------------------------------------------- //
      // Black PCB
      const pcbGeo = new THREE.BoxGeometry(2.4, 0.12, 1.3);
      const pcbMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.7 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      group.add(pcb);

      // ESP32-S3 Metal RF Shielding Can
      const rfGeo = new THREE.BoxGeometry(0.95, 0.12, 0.85);
      const rfMat = new THREE.MeshStandardMaterial({ color: 0xd4d4d8, metalness: 0.9, roughness: 0.2 });
      const rf = new THREE.Mesh(rfGeo, rfMat);
      rf.position.set(-0.35, 0.1, 0);
      group.add(rf);

      // Gold Meandered PCB Trace Antenna
      const antGeo = new THREE.BoxGeometry(0.35, 0.04, 0.7);
      const antMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.95 });
      const ant = new THREE.Mesh(antGeo, antMat);
      ant.position.set(0.85, 0.08, 0);
      group.add(ant);

      // USB Type-C Receptacle (Left Edge)
      const usbcGeo = new THREE.BoxGeometry(0.25, 0.14, 0.35);
      const usbcMat = new THREE.MeshStandardMaterial({ color: 0xa1a1aa, metalness: 0.9 });
      const usbc = new THREE.Mesh(usbcGeo, usbcMat);
      usbc.position.set(-1.15, 0.1, 0);
      group.add(usbc);

      // Dual Row Gold Header Pins
      const pinMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.9 });
      const pinGeo = new THREE.BoxGeometry(2.1, 0.2, 0.08);
      const pin1 = new THREE.Mesh(pinGeo, pinMat);
      pin1.position.set(0, 0.12, -0.55);
      const pin2 = pin1.clone();
      pin2.position.z = 0.55;
      group.add(pin1);
      group.add(pin2);

      // Micro SMD Push Buttons (EN & BOOT)
      const btnGeo = new THREE.BoxGeometry(0.12, 0.08, 0.12);
      const btnMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.8 });
      const btn1 = new THREE.Mesh(btnGeo, btnMat);
      btn1.position.set(-0.85, 0.1, -0.35);
      const btn2 = btn1.clone();
      btn2.position.z = 0.35;
      group.add(btn1);
      group.add(btn2);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("ESP32-S3", "SENSOR DATA ACQUISITION", "🎛️", "#818cf8");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = pcb;

    } else if (dev.shape === "lifepo4_pmu") {
      // -------------------------------------------------------------- //
      // 3. LiFePO4 BATTERY & PMU ENCLOSURE
      // -------------------------------------------------------------- //
      // Industrial Ruggedized ABS Housing (Orange/Charcoal)
      const bodyGeo = new THREE.BoxGeometry(3.6, 0.75, 2.4);
      const body = new THREE.Mesh(bodyGeo, primaryMat);
      group.add(body);

      // Dual Internal Cylindrical Cell Contours
      const cellMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.6 });
      const cell1 = new THREE.Mesh(new THREE.CylinderGeometry(0.48, 0.48, 3.2, 16), cellMat);
      cell1.rotation.z = Math.PI / 2;
      cell1.position.set(0, 0.1, -0.55);
      const cell2 = cell1.clone();
      cell2.position.z = 0.55;
      group.add(cell1);
      group.add(cell2);

      // Heavy Brass High-Current Terminal Studs (+ / -)
      const termGeo = new THREE.CylinderGeometry(0.14, 0.14, 0.3, 16);
      const redMat = new THREE.MeshStandardMaterial({ color: 0xef4444, metalness: 0.7 });
      const blkMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.7 });
      const termPos = new THREE.Mesh(termGeo, redMat);
      termPos.position.set(-1.4, 0.5, 0.7);
      const termNeg = new THREE.Mesh(termGeo, blkMat);
      termNeg.position.set(1.4, 0.5, 0.7);
      group.add(termPos);
      group.add(termNeg);

      // OLED Fuel Gauge Digital Display Window
      const oledGeo = new THREE.BoxGeometry(1.4, 0.05, 0.45);
      const oledMat = new THREE.MeshStandardMaterial({ color: 0x06b6d4, emissive: 0x06b6d4, emissiveIntensity: 0.75 });
      const oled = new THREE.Mesh(oledGeo, oledMat);
      oled.position.set(0, 0.4, 0);
      group.add(oled);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("LiFePO4 PMU", "7.4V / 5000mAh POWER PACK", "🔋", "#f59e0b");
      badge.position.set(0, 1.05, 0);
      group.add(badge);

      group.userData.mainMesh = body;

    } else if (dev.shape === "cam_thermal") {
      // -------------------------------------------------------------- //
      // 4. FLIR LEPTON 3.5 LWIR RADIOMETRIC THERMAL CAMERA
      // -------------------------------------------------------------- //
      // Teledyne FLIR Anodized Aluminum Core
      const coreGeo = new THREE.BoxGeometry(0.9, 0.9, 0.75);
      const core = new THREE.Mesh(coreGeo, primaryMat);
      group.add(core);

      // Golden Germanium Infrared Lens Barrel (8-14μm Coating)
      const lensGeo = new THREE.CylinderGeometry(0.28, 0.32, 0.35, 24);
      const lensMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.95, roughness: 0.1 });
      const lens = new THREE.Mesh(lensGeo, lensMat);
      lens.rotation.x = Math.PI / 2;
      lens.position.set(0, 0, 0.5);
      group.add(lens);

      // Germanium Convex Lens Element
      const elementGeo = new THREE.SphereGeometry(0.24, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2);
      const elementMat = new THREE.MeshStandardMaterial({ color: 0xb45309, metalness: 0.8, roughness: 0.15 });
      const element = new THREE.Mesh(elementGeo, elementMat);
      element.rotation.x = Math.PI / 2;
      element.position.set(0, 0, 0.65);
      group.add(element);

      // Purple Breakout PCB
      const brkGeo = new THREE.BoxGeometry(1.2, 1.2, 0.08);
      const brkMat = new THREE.MeshStandardMaterial({ color: 0x7e22ce, roughness: 0.6 });
      const brk = new THREE.Mesh(brkGeo, brkMat);
      brk.position.set(0, 0, -0.4);
      group.add(brk);

      // Translucent False-Color Radiometric FOV Cone (Scanning Beam)
      const fovConeGeo = new THREE.ConeGeometry(1.8, 3.8, 24, 1, true);
      const fovConeMat = new THREE.MeshBasicMaterial({
        color: 0xf43f5e,
        transparent: true,
        opacity: 0.25,
        side: THREE.DoubleSide,
      });
      thermalConeMesh = new THREE.Mesh(fovConeGeo, fovConeMat);
      thermalConeMesh.rotation.x = -Math.PI / 2;
      thermalConeMesh.position.set(0, 0, 2.4);
      group.add(thermalConeMesh);

      const fovWireMat = new THREE.MeshBasicMaterial({ color: 0xfb7185, wireframe: true, transparent: true, opacity: 0.4 });
      const fovWire = new THREE.Mesh(fovConeGeo, fovWireMat);
      thermalConeMesh.add(fovWire);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("FLIR Lepton 3.5", "LWIR THERMAL CAMERA", "🌡️", "#f43f5e");
      badge.position.set(0, 1.05, 0);
      group.add(badge);

      group.userData.mainMesh = core;

    } else if (dev.shape === "cam_optical") {
      // -------------------------------------------------------------- //
      // 5. SONY IMX708 12MP AUTOFOCUS OPTICAL RGB CAMERA
      // -------------------------------------------------------------- //
      const pcbGeo = new THREE.BoxGeometry(0.85, 0.85, 0.12);
      const pcbMat = new THREE.MeshStandardMaterial({ color: 0x065f46, roughness: 0.7 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      group.add(pcb);

      // Autofocus Cylindrical Lens Housing
      const lensGeo = new THREE.CylinderGeometry(0.28, 0.28, 0.45, 24);
      const lensMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.85, roughness: 0.2 });
      const lens = new THREE.Mesh(lensGeo, lensMat);
      lens.rotation.x = Math.PI / 2;
      lens.position.set(0, 0, 0.3);
      group.add(lens);

      // Brass Aperture Ring
      const ringGeo = new THREE.TorusGeometry(0.26, 0.03, 12, 24);
      const ringMat = new THREE.MeshStandardMaterial({ color: 0xca8a04, metalness: 0.95 });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.set(0, 0, 0.52);
      group.add(ring);

      // Optical Glass Front Element
      const glassGeo = new THREE.CircleGeometry(0.22, 16);
      const glassMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, metalness: 0.9, roughness: 0.1 });
      const glass = new THREE.Mesh(glassGeo, glassMat);
      glass.position.set(0, 0, 0.53);
      group.add(glass);

      // Translucent Optical FOV Wireframe Cone
      const fovGeo = new THREE.ConeGeometry(1.6, 3.5, 16, 1, true);
      const fovMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.25 });
      opticalConeMesh = new THREE.Mesh(fovGeo, fovMat);
      opticalConeMesh.rotation.x = -Math.PI / 2;
      opticalConeMesh.position.set(0, 0, 2.2);
      group.add(opticalConeMesh);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("Sony IMX708", "12MP RGB CAMERA", "📷", "#ec4899");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = pcb;

    } else if (dev.shape === "radar_patch") {
      // -------------------------------------------------------------- //
      // 6. TI IWR6843AOP 60GHz mmWAVE DOPPLER RADAR
      // -------------------------------------------------------------- //
      // White High-Frequency Rogers PCB
      const bodyGeo = new THREE.BoxGeometry(0.95, 0.95, 0.18);
      const body = new THREE.Mesh(bodyGeo, primaryMat);
      group.add(body);

      // 4-Channel Gold Microstrip Patch Antenna Array Grid
      const patchMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.98 });
      for (let r = 0; r < 2; r++) {
        for (let c = 0; c < 2; c++) {
          const p = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.24, 0.04), patchMat);
          p.position.set(-0.2 + c * 0.4, -0.2 + r * 0.4, 0.11);
          group.add(p);
        }
      }

      // Aluminum Baseplate
      const baseGeo = new THREE.BoxGeometry(1.05, 1.05, 0.08);
      const baseMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9 });
      const base = new THREE.Mesh(baseGeo, baseMat);
      base.position.set(0, 0, -0.12);
      group.add(base);

      // Dynamic Animated Doppler Radar Wave Rings
      for (let i = 0; i < 3; i++) {
        const ringGeo = new THREE.RingGeometry(0.8 + i * 0.4, 0.85 + i * 0.4, 24);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0x06b6d4, side: THREE.DoubleSide, transparent: true, opacity: 0.45 });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        ringMesh.position.set(0, 0, 0.6 + i * 0.5);
        group.add(ringMesh);
        radarRings.push(ringMesh);
      }

      // Floating 3D Product Badge
      const badge = createHolographicBadge("TI IWR6843AOP", "mmWave VITAL RADAR", "📡", "#06b6d4");
      badge.position.set(0, 1.05, 0);
      group.add(badge);

      group.userData.mainMesh = body;

    } else if (dev.shape === "pir_dome") {
      // -------------------------------------------------------------- //
      // 7. PANASONIC PaPIRs PYROELECTRIC INFRARED MOTION SENSOR
      // -------------------------------------------------------------- //
      // TO-5 Metal Hermetic Can Base
      const canGeo = new THREE.CylinderGeometry(0.42, 0.42, 0.22, 20);
      const canMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.92, roughness: 0.2 });
      const can = new THREE.Mesh(canGeo, canMat);
      group.add(can);

      // Segmented Multi-Faceted White Polyolefin Fresnel Lens Dome
      const domeGeo = new THREE.SphereGeometry(0.38, 20, 14, 0, Math.PI * 2, 0, Math.PI / 2);
      const domeMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, roughness: 0.35 });
      const dome = new THREE.Mesh(domeGeo, domeMat);
      dome.position.set(0, 0.11, 0);
      group.add(dome);

      // Green Disc Breakout PCB & 3 Gold Header Pins
      const pcb = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.08, 20), primaryMat);
      pcb.position.set(0, -0.15, 0);
      group.add(pcb);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("PaPIRs", "PIR MOTION SENSOR", "👁️", "#0891b2");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = pcb;

    } else if (dev.shape === "imu_chip") {
      // -------------------------------------------------------------- //
      // 8. INVEN SENSE MPU-6050 6-DoF INCLINOMETER & SEISMIC SENSOR
      // -------------------------------------------------------------- //
      // Royal Blue Breakout PCB
      const pcbGeo = new THREE.BoxGeometry(0.85, 0.12, 0.65);
      const pcbMat = new THREE.MeshStandardMaterial({ color: dev.id === "DEV-IMU-01" ? 0x1d4ed8 : 0x7c3aed, roughness: 0.6 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      group.add(pcb);

      // QFN-24 Sensor IC Chip
      const icGeo = new THREE.BoxGeometry(0.3, 0.08, 0.3);
      const icMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.8 });
      const ic = new THREE.Mesh(icGeo, icMat);
      ic.position.set(-0.1, 0.1, 0);
      group.add(ic);

      // 8-Pin Gold Header
      const pinGeo = new THREE.BoxGeometry(0.8, 0.22, 0.08);
      const pinMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.95 });
      const pins = new THREE.Mesh(pinGeo, pinMat);
      pins.position.set(0, 0.12, -0.26);
      group.add(pins);

      // 3D XYZ Coordinate Axis Indicator (Red X, Green Y, Blue Z)
      const axisLen = 0.35;
      const xMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
      const yMat = new THREE.MeshBasicMaterial({ color: 0x22c55e });
      const zMat = new THREE.MeshBasicMaterial({ color: 0x3b82f6 });

      const xArrow = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, axisLen), xMat);
      xArrow.rotation.z = Math.PI / 2;
      xArrow.position.set(0.18, 0.18, 0);
      group.add(xArrow);

      const yArrow = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, axisLen), yMat);
      yArrow.position.set(0, 0.32, 0);
      group.add(yArrow);

      const zArrow = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, axisLen), zMat);
      zArrow.rotation.x = Math.PI / 2;
      zArrow.position.set(0, 0.18, 0.18);
      group.add(zArrow);

      const title = dev.id === "DEV-IMU-01" ? "MPU-6050 Tilt" : "MPU-6050 Seismic";
      const subtitle = dev.id === "DEV-IMU-01" ? "3-AXIS INCLINOMETER" : "ACCELERATION & PGV";
      const badge = createHolographicBadge(title, subtitle, dev.icon, dev.color);
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = pcb;

    } else if (dev.shape === "soil_probe") {
      // -------------------------------------------------------------- //
      // 9. FDR VOLUMETRIC SOIL MOISTURE SENSOR WITH GROUND BASE
      // -------------------------------------------------------------- //
      // Epoxy-Sealed Weatherproof Head
      const headGeo = new THREE.CylinderGeometry(0.24, 0.24, 0.55, 16);
      const head = new THREE.Mesh(headGeo, primaryMat);
      head.position.y = 0.25;
      group.add(head);

      // Dual Stainless Steel Sensing Prongs
      const prongGeo = new THREE.CylinderGeometry(0.035, 0.035, 1.3, 12);
      const prongMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.98, roughness: 0.1 });
      const p1 = new THREE.Mesh(prongGeo, prongMat);
      p1.position.set(-0.12, -0.65, 0);
      const p2 = p1.clone();
      p2.position.x = 0.12;
      group.add(p1);
      group.add(p2);

      // Ground Soil Patch Disc (Earth layer showing probe insertion)
      const soilGeo = new THREE.CylinderGeometry(0.7, 0.75, 0.25, 16);
      const soilMat = new THREE.MeshStandardMaterial({ color: 0x3e2723, roughness: 0.95 });
      const soil = new THREE.Mesh(soilGeo, soilMat);
      soil.position.set(0, -1.2, 0);
      group.add(soil);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("FDR Probe", "SOIL MOISTURE SENSOR", "🌱", "#10b981");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = head;

    } else if (dev.shape === "water_probe") {
      // -------------------------------------------------------------- //
      // 10. SUBMERSIBLE 316L HYDROSTATIC WATER LEVEL PROBE
      // -------------------------------------------------------------- //
      // Stainless Steel Cylindrical Transducer
      const cylGeo = new THREE.CylinderGeometry(0.22, 0.22, 1.4, 20);
      const cylMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.95, roughness: 0.15 });
      const probe = new THREE.Mesh(cylGeo, cylMat);
      group.add(probe);

      // Conical Multi-Hole Intake Filter Tip
      const tipGeo = new THREE.ConeGeometry(0.22, 0.35, 20);
      const tip = new THREE.Mesh(tipGeo, primaryMat);
      tip.rotation.x = Math.PI;
      tip.position.set(0, -0.85, 0);
      group.add(tip);

      // Cable Gland Boot
      const bootGeo = new THREE.CylinderGeometry(0.12, 0.22, 0.3, 16);
      const bootMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.7 });
      const boot = new THREE.Mesh(bootGeo, bootMat);
      boot.position.set(0, 0.85, 0);
      group.add(boot);

      // Floating 3D Product Badge
      const badge = createHolographicBadge("316L Hydrostatic", "WATER LEVEL TRANSDUCER", "💧", "#38bdf8");
      badge.position.set(0, 1.15, 0);
      group.add(badge);

      group.userData.mainMesh = probe;

    } else if (dev.shape === "flow_doppler") {
      // -------------------------------------------------------------- //
      // 11. ACOUSTIC DOPPLER CURRENT PROFILER (ADCP FLOW SENSOR)
      // -------------------------------------------------------------- //
      // Marine Hydrodynamic Pod
      const podGeo = new THREE.BoxGeometry(0.45, 0.35, 1.2);
      const pod = new THREE.Mesh(podGeo, primaryMat);
      group.add(pod);

      // Dual Angled Acoustic Ceramic Transducer Faces
      const faceGeo = new THREE.CircleGeometry(0.14, 16);
      const faceMat = new THREE.MeshStandardMaterial({ color: 0xe0f2fe, metalness: 0.5 });
      const f1 = new THREE.Mesh(faceGeo, faceMat);
      f1.position.set(0, 0.18, 0.4);
      f1.rotation.x = -Math.PI / 3;
      const f2 = f1.clone();
      f2.position.z = -0.4;
      f2.rotation.x = Math.PI / 3;
      group.add(f1);
      group.add(f2);

      const badge = createHolographicBadge("Doppler ADCP", "WATER FLOW SENSOR", "🌊", "#0284c7");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = pod;

    } else if (dev.shape === "rain_optical") {
      // -------------------------------------------------------------- //
      // 12. RG-11 OPTICAL INFRARED RAIN DISDROMETER
      // -------------------------------------------------------------- //
      // Hemispherical Optical Clear Poly Dome
      const domeGeo = new THREE.SphereGeometry(0.38, 20, 14, 0, Math.PI * 2, 0, Math.PI / 2);
      const domeMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        transparent: true,
        opacity: 0.5,
        roughness: 0.1,
        metalness: 0.2,
      });
      const dome = new THREE.Mesh(domeGeo, domeMat);
      dome.position.set(0, 0.25, 0);
      group.add(dome);

      // Weatherproof ASA Housing & Collector Cone
      const coneGeo = new THREE.ConeGeometry(0.48, 0.5, 20);
      const coneMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.5 });
      const cone = new THREE.Mesh(coneGeo, coneMat);
      cone.rotation.x = Math.PI;
      cone.position.set(0, 0, 0);
      group.add(cone);

      // Mounting Conduit Stem
      const stemGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.5, 16);
      const stemMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.8 });
      const stem = new THREE.Mesh(stemGeo, stemMat);
      stem.position.set(0, -0.4, 0);
      group.add(stem);

      const badge = createHolographicBadge("RG-11 Optical", "PRECIPITATION DISDROMETER", "🌧️", "#38bdf8");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = cone;

    } else if (dev.shape === "baro_chip") {
      // -------------------------------------------------------------- //
      // 13. BOSCH BMP280 PRECISION DIGITAL BAROMETER
      // -------------------------------------------------------------- //
      // Cobalt Blue Breakout PCB
      const pcbGeo = new THREE.BoxGeometry(0.7, 0.1, 0.55);
      const pcbMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.6 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      group.add(pcb);

      // Metal LGA Sensor Can with Micro Barometric Vent Hole
      const canGeo = new THREE.BoxGeometry(0.28, 0.08, 0.28);
      const canMat = new THREE.MeshStandardMaterial({ color: 0xd4d4d8, metalness: 0.92, roughness: 0.2 });
      const can = new THREE.Mesh(canGeo, canMat);
      can.position.set(-0.1, 0.08, 0);
      group.add(can);

      const ventGeo = new THREE.CircleGeometry(0.04, 12);
      const ventMat = new THREE.MeshBasicMaterial({ color: 0x09090b });
      const vent = new THREE.Mesh(ventGeo, ventMat);
      vent.rotation.x = -Math.PI / 2;
      vent.position.set(-0.1, 0.13, 0);
      group.add(vent);

      // 6-Pin Header
      const pinGeo = new THREE.BoxGeometry(0.65, 0.18, 0.06);
      const pinMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.95 });
      const pins = new THREE.Mesh(pinGeo, pinMat);
      pins.position.set(0, 0.1, -0.22);
      group.add(pins);

      const badge = createHolographicBadge("Bosch BMP280", "BAROMETRIC PRESSURE", "⏱️", "#60a5fa");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = pcb;

    } else if (dev.shape === "gas_mox") {
      // -------------------------------------------------------------- //
      // 14. MQ-135 MULTI-GAS TOXIC SENSOR (STAINLESS STEEL MESH CAGE)
      // -------------------------------------------------------------- //
      // Bakelite Hexagonal/Round Base Socket
      const baseGeo = new THREE.CylinderGeometry(0.42, 0.44, 0.25, 16);
      const baseMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.8 });
      const base = new THREE.Mesh(baseGeo, baseMat);
      group.add(base);

      // Double-Layer Stainless Steel Wire Mesh Flame Arrestor Cylinder
      const meshGeo = new THREE.CylinderGeometry(0.38, 0.38, 0.55, 20);
      const meshMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        metalness: 0.9,
        roughness: 0.3,
        wireframe: true,
      });
      const mesh = new THREE.Mesh(meshGeo, meshMat);
      mesh.position.set(0, 0.35, 0);
      group.add(mesh);

      // Internal Glowing Micro-Heating Coil
      const coilGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.35, 12);
      const coilMat = new THREE.MeshStandardMaterial({
        color: 0xf97316,
        emissive: 0xf97316,
        emissiveIntensity: 0.8,
      });
      const coil = new THREE.Mesh(coilGeo, coilMat);
      coil.position.set(0, 0.35, 0);
      group.add(coil);

      // Breakout PCB with Potentiometer
      const pcb = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.08, 0.75), primaryMat);
      pcb.position.set(0, -0.16, 0);
      group.add(pcb);

      const pot = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.18, 0.18), new THREE.MeshStandardMaterial({ color: 0x2563eb }));
      pot.position.set(0.3, -0.05, 0.2);
      group.add(pot);

      const badge = createHolographicBadge("MQ-135", "MULTI-GAS TOXIC SENSOR", "☣️", "#eab308");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = base;

    } else if (dev.shape === "smoke_laser") {
      // -------------------------------------------------------------- //
      // 15. PLANTOWER PMS5003 LASER SMOKE & PARTICULATE SENSOR
      // -------------------------------------------------------------- //
      // Laser Optical Scattering Metal Chamber Box
      const boxGeo = new THREE.BoxGeometry(0.9, 0.5, 0.7);
      const boxMat = new THREE.MeshStandardMaterial({ color: 0xd1d5db, metalness: 0.92, roughness: 0.2 });
      const box = new THREE.Mesh(boxGeo, boxMat);
      group.add(box);

      // Louvered Air Intake & Exhaust Ventilation Slots
      const ventMat = new THREE.MeshBasicMaterial({ color: 0x18181b });
      for (let v = 0; v < 3; v++) {
        const vMesh = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.04, 0.02), ventMat);
        vMesh.position.set(-0.15, -0.1 + v * 0.09, 0.36);
        group.add(vMesh);
      }

      const badge = createHolographicBadge("Plantower PMS5003", "LASER SMOKE SENSOR", "🌫️", "#94a3b8");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = box;

    } else if (dev.shape === "temp_sht") {
      // -------------------------------------------------------------- //
      // 16. SENSIRION SHT31 TEMPERATURE & HUMIDITY SENSOR MODULE
      // -------------------------------------------------------------- //
      // Precision Magenta/Purple Breakout PCB
      const pcbGeo = new THREE.BoxGeometry(0.65, 0.1, 0.55);
      const pcb = new THREE.Mesh(pcbGeo, primaryMat);
      group.add(pcb);

      // Slotted Breathable PTFE Protective Filter Cap Cage
      const capGeo = new THREE.BoxGeometry(0.28, 0.16, 0.28);
      const capMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.4 });
      const cap = new THREE.Mesh(capGeo, capMat);
      cap.position.set(-0.08, 0.12, 0);
      group.add(cap);

      // 4-Pin Gold Header
      const pinGeo = new THREE.BoxGeometry(0.55, 0.18, 0.06);
      const pinMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.95 });
      const pins = new THREE.Mesh(pinGeo, pinMat);
      pins.position.set(0, 0.1, -0.22);
      group.add(pins);

      const title = dev.id === "DEV-TEMP-01" ? "Sensirion SHT31 Temp" : "Sensirion SHT31 Humid";
      const subtitle = dev.id === "DEV-TEMP-01" ? "AMBIENT TEMPERATURE" : "RELATIVE HUMIDITY";
      const badge = createHolographicBadge(title, subtitle, dev.icon, dev.color);
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = pcb;

    } else if (dev.shape === "gps_helix" || dev.shape === "gps_patch") {
      // -------------------------------------------------------------- //
      // 17. u-blox NEO-M9N MULTI-CONSTELLATION GNSS RECEIVER
      // -------------------------------------------------------------- //
      // Ceramic Square Patch Antenna (Tan/Gold)
      const patchGeo = new THREE.BoxGeometry(0.7, 0.18, 0.7);
      const patchMat = new THREE.MeshStandardMaterial({ color: 0xd6d3d1, roughness: 0.5 });
      const patch = new THREE.Mesh(patchGeo, patchMat);
      group.add(patch);

      // Metallic Ground Plane and Center Feed Pin
      const feedGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.22, 12);
      const feedMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.95 });
      const feed = new THREE.Mesh(feedGeo, feedMat);
      feed.position.set(0, 0.05, 0);
      group.add(feed);

      // Dark Blue Carrier PCB
      const pcbGeo = new THREE.BoxGeometry(0.9, 0.1, 0.9);
      const pcbMat = new THREE.MeshStandardMaterial({ color: 0x1e3a8a, roughness: 0.7 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      pcb.position.set(0, -0.14, 0);
      group.add(pcb);

      // Coin-Cell Backup Battery Holder
      const batGeo = new THREE.CylinderGeometry(0.16, 0.16, 0.1, 16);
      const batMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9 });
      const bat = new THREE.Mesh(batGeo, batMat);
      bat.position.set(0.28, -0.05, 0.28);
      group.add(bat);

      const badge = createHolographicBadge("u-blox NEO-M9N", "92-CH MULTI-GNSS RECEIVER", "🛰️", "#3b82f6");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = patch;

    } else if (dev.shape === "antenna_lora") {
      // -------------------------------------------------------------- //
      // 18. SEMTECH SX1262 LoRa MESH TRANSCEIVER & FIBERGLASS WHIP
      // -------------------------------------------------------------- //
      // Red Transceiver PCB
      const pcbGeo = new THREE.BoxGeometry(0.65, 0.1, 0.55);
      const pcbMat = new THREE.MeshStandardMaterial({ color: 0xdc2626, roughness: 0.7 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      group.add(pcb);

      // Brass SMA Bulkhead Connector
      const smaGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.25, 12);
      const smaMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.95 });
      const sma = new THREE.Mesh(smaGeo, smaMat);
      sma.position.set(0, 0.16, 0);
      group.add(sma);

      // Flexible High-Gain Whip Antenna (868/915 MHz)
      const whipGeo = new THREE.CylinderGeometry(0.04, 0.08, 2.2, 12);
      const whipMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.5 });
      const whip = new THREE.Mesh(whipGeo, whipMat);
      whip.position.set(0, 1.35, 0);
      group.add(whip);

      const badge = createHolographicBadge("SX1262 LoRa", "LONG-RANGE MESH (15km)", "📡", "#10b981");
      badge.position.set(0, 1.05, 0);
      group.add(badge);

      group.userData.mainMesh = whip;

    } else if (dev.shape === "antenna_cell") {
      // -------------------------------------------------------------- //
      // 19. QUECTEL BG95-M3 4G/5G CELLULAR GATEWAY MODEM
      // -------------------------------------------------------------- //
      // Green M.2 Modem Breakout Board
      const pcbGeo = new THREE.BoxGeometry(0.7, 0.1, 0.6);
      const pcbMat = new THREE.MeshStandardMaterial({ color: 0x166534, roughness: 0.7 });
      const pcb = new THREE.Mesh(pcbGeo, pcbMat);
      group.add(pcb);

      // Shielded Modem Can & SIM Slot
      const canGeo = new THREE.BoxGeometry(0.45, 0.08, 0.45);
      const canMat = new THREE.MeshStandardMaterial({ color: 0xd4d4d8, metalness: 0.9 });
      const can = new THREE.Mesh(canGeo, canMat);
      can.position.set(-0.08, 0.09, 0);
      group.add(can);

      // High-Gain Blade Dipole Antenna
      const bladeGeo = new THREE.BoxGeometry(0.12, 2.4, 0.35);
      const bladeMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.4 });
      const blade = new THREE.Mesh(bladeGeo, bladeMat);
      blade.position.set(0, 1.45, 0);
      group.add(blade);

      const badge = createHolographicBadge("Quectel BG95-M3", "4G-5G / NB-IoT MODEM", "📶", "#059669");
      badge.position.set(0, 1.05, 0);
      group.add(badge);

      group.userData.mainMesh = blade;

    } else if (dev.shape === "mic_mems") {
      // -------------------------------------------------------------- //
      // 20. INVEN SENSE INMP441 DIGITAL ACOUSTIC MEMS ARRAY
      // -------------------------------------------------------------- //
      // Circular Black Breakout PCB
      const discGeo = new THREE.CylinderGeometry(0.35, 0.35, 0.08, 20);
      const discMat = new THREE.MeshStandardMaterial({ color: 0x09090b, roughness: 0.6 });
      const disc = new THREE.Mesh(discGeo, discMat);
      group.add(disc);

      // Gold Sound Port Aperture Hole
      const portGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.1, 16);
      const portMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.95 });
      const port = new THREE.Mesh(portGeo, portMat);
      port.position.set(0, 0.02, 0);
      group.add(port);

      // 6-Pin I2S Header
      const pinGeo = new THREE.BoxGeometry(0.55, 0.16, 0.06);
      const pins = new THREE.Mesh(pinGeo, portMat);
      pins.position.set(0, 0.1, -0.22);
      group.add(pins);

      const badge = createHolographicBadge("INMP441 MEMS", "DIGITAL ACOUSTIC SENSOR", "🎙️", "#0284c7");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = disc;

    } else if (dev.shape === "co2_ndir") {
      // -------------------------------------------------------------- //
      // 21. WINSEN MH-Z19C NDIR EXHALED CO2 OPTICAL GAS CHAMBER
      // -------------------------------------------------------------- //
      // Polished Gold-Plated Optical Absorption Chamber
      const goldChamberGeo = new THREE.CylinderGeometry(0.32, 0.32, 0.65, 20);
      const goldMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.95, roughness: 0.15 });
      const chamber = new THREE.Mesh(goldChamberGeo, goldMat);
      chamber.rotation.x = Math.PI / 2;
      group.add(chamber);

      // White Sintered PTFE Filter Membrane on Front Face
      const memGeo = new THREE.CircleGeometry(0.24, 16);
      const memMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.6 });
      const mem = new THREE.Mesh(memGeo, memMat);
      mem.position.set(0, 0, 0.33);
      group.add(mem);

      // Green Carrier Board
      const pcb = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.08, 0.85), primaryMat);
      pcb.position.set(0, -0.38, 0);
      group.add(pcb);

      const badge = createHolographicBadge("MH-Z19C NDIR", "EXHALED CO2 SENSOR", "💨", "#0369a1");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = chamber;

    } else if (dev.shape === "slope_array") {
      // -------------------------------------------------------------- //
      // 22. IP67 DISTRIBUTED SLOPE TELEMETRY ARRAY JUNCTION
      // -------------------------------------------------------------- //
      // Ruggedized Polycarbonate Junction Box
      const boxGeo = new THREE.BoxGeometry(0.85, 0.55, 0.65);
      const box = new THREE.Mesh(boxGeo, primaryMat);
      group.add(box);

      // Transparent Smoked Cover with Stainless Latches
      const lidGeo = new THREE.BoxGeometry(0.82, 0.08, 0.62);
      const lidMat = new THREE.MeshStandardMaterial({ color: 0x64748b, transparent: true, opacity: 0.6 });
      const lid = new THREE.Mesh(lidGeo, lidMat);
      lid.position.set(0, 0.3, 0);
      group.add(lid);

      // 3 Armored RS-485 Cable Glands (Upper, Mid, Base)
      const glandMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.9 });
      for (let g = 0; g < 3; g++) {
        const gland = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.25, 12), glandMat);
        gland.position.set(-0.25 + g * 0.25, -0.35, 0);
        group.add(gland);
      }

      const badge = createHolographicBadge("RS-485 Array", "3-NODE SLOPE TELEMETRY", "⛰️", "#059669");
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = box;

    } else {
      // Fallback Custom Modular Enclosure
      const geo = new THREE.BoxGeometry(dev.size[0] || 0.8, dev.size[1] || 0.4, dev.size[2] || 0.5);
      const mesh = new THREE.Mesh(geo, primaryMat);
      group.add(mesh);

      const badge = createHolographicBadge(dev.name, dev.role, dev.icon, dev.color);
      badge.position.set(0, 0.95, 0);
      group.add(badge);

      group.userData.mainMesh = mesh;
    }

    // Add High-Precision Bezel Highlight Wireframe
    if (group.userData.mainMesh) {
      const edges = new THREE.EdgesGeometry(group.userData.mainMesh.geometry);
      const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.25 });
      const wireframe = new THREE.LineSegments(edges, lineMat);
      group.userData.mainMesh.add(wireframe);

      // Real Hardware Status LED Indicator
      const ledGeo = new THREE.SphereGeometry(0.08, 12, 12);
      const ledMat = new THREE.MeshBasicMaterial({ color: 0x10b981 });
      const led = new THREE.Mesh(ledGeo, ledMat);
      led.position.y = (dev.size && dev.size[1] ? dev.size[1] * 0.5 : 0.4) + 0.06;
      group.userData.mainMesh.add(led);
      group.userData.led = led;
    }

    return group;
  }

  // ------------------------------------------------------------------ //
  // Physical Wire Harnesses & Interconnect Builder
  // ------------------------------------------------------------------ //

  function buildPhysicalWiring() {
    wireMeshMap.clear();
    wireCurves = [];

    state.connections.forEach((conn) => {
      const srcDev = HARDWARE_NODES.find(d => d.id === conn.sourceId);
      const tgtDev = HARDWARE_NODES.find(d => d.id === conn.targetId);
      if (!srcDev || !tgtDev) return;

      const startPoint = new THREE.Vector3(srcDev.pos[0], srcDev.pos[1], srcDev.pos[2]);
      const endPoint = new THREE.Vector3(tgtDev.pos[0], tgtDev.pos[1], tgtDev.pos[2]);

      // Control point for realistic curved cable sag
      const midPoint = new THREE.Vector3().addVectors(startPoint, endPoint).multiplyScalar(0.5);
      midPoint.y -= 0.32; // Slight gravity sag

      const curve = new THREE.QuadraticBezierCurve3(startPoint, midPoint, endPoint);
      wireCurves.push({ curve: curve, conn: conn });

      const protoColor = PROTOCOL_COLORS[conn.protocol] || "#06b6d4";
      const tubeGeo = new THREE.TubeGeometry(curve, 24, 0.026, 8, false);
      const tubeMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(protoColor),
        roughness: 0.45,
        metalness: 0.35,
        transparent: true,
        opacity: 0.75,
      });

      const wireMesh = new THREE.Mesh(tubeGeo, tubeMat);
      wireMesh.userData = { connection: conn, originalColor: protoColor };
      wiringGroup.add(wireMesh);
      wireMeshMap.set(`${conn.sourceId}->${conn.targetId}`, wireMesh);
    });
  }

  // Create Glowing Moving Data Flow Particles along Active Connections
  function createDataFlowParticles() {
    while (particleGroup.children.length > 0) {
      particleGroup.remove(particleGroup.children[0]);
    }
    flowParticles = [];

    const pGeo = new THREE.SphereGeometry(0.048, 8, 8);

    wireCurves.forEach(({ curve, conn }) => {
      const isPower = conn.protocol === "USB_POWER" || conn.protocol === "DC_BUS";
      const pColor = isPower ? 0xffd700 : (PROTOCOL_COLORS[conn.protocol] || 0x38bdf8);
      const pMat = new THREE.MeshBasicMaterial({ color: pColor });

      // Add 2 particles per wire
      for (let i = 0; i < 2; i++) {
        const pMesh = new THREE.Mesh(pGeo, pMat);
        const progress = (i * 0.5 + Math.random() * 0.2) % 1.0;
        const pos = curve.getPoint(progress);
        pMesh.position.copy(pos);
        particleGroup.add(pMesh);

        flowParticles.push({
          mesh: pMesh,
          curve: curve,
          progress: progress,
          speed: 0.0035 + Math.random() * 0.002,
          conn: conn,
        });
      }
    });
  }

  // ------------------------------------------------------------------ //
  // Animation Loop (High-Performance 4D Engine)
  // ------------------------------------------------------------------ //

  let clock = new THREE.Clock();
  let frameCount = 0;
  let lastFpsUpdate = 0;

  function animate() {
    requestAnimationFrame(animate);

    const delta = clock.getDelta();
    const elapsed = clock.getElapsedTime();

    // 1. Controls Update
    if (controls) {
      controls.autoRotate = state.autoRotate;
      controls.autoRotateSpeed = 1.2;
      controls.update();
    }

    // 2. Smooth Camera Easing when Focusing
    if (targetCamPos && targetLookAt) {
      camera.position.lerp(targetCamPos, 0.06);
      controls.target.lerp(targetLookAt, 0.06);
      if (camera.position.distanceTo(targetCamPos) < 0.08) {
        targetCamPos = null;
        targetLookAt = null;
      }
    }

    // 3. Animate Live Data Flow Particles (Scenario & Health Aware - 4D only)
    if (state.visualMode === "4D" && state.showDataFlow) {
      particleGroup.visible = true;
      flowParticles.forEach((p) => {
        const srcDev = HARDWARE_NODES.find(d => d.id === p.conn.sourceId);
        const isSrcActive = isScenarioRelevant(srcDev, state.selectedScenario);
        const srcStatus = getLiveStatus(p.conn.sourceId);

        // Only flow data if connection/device is active and not OFFLINE
        if (srcStatus === "OFFLINE" || (!isSrcActive && state.selectedScenario !== "ALL")) {
          p.mesh.visible = false;
        } else {
          p.mesh.visible = true;
          const speedMultiplier = isSrcActive ? 1.6 : 0.7;
          p.progress = (p.progress + p.speed * speedMultiplier) % 1.0;
          const pos = p.curve.getPoint(p.progress);
          p.mesh.position.copy(pos);

          // Subtle pulse scale
          const s = 0.8 + 0.35 * Math.sin(elapsed * 6 + p.progress * Math.PI);
          p.mesh.scale.set(s, s, s);
        }
      });
    } else {
      particleGroup.visible = false;
    }

    // 4. Animate Thermal & Optical FOV Cones & Radar Wavefronts (4D vs 3D)
    if (state.visualMode === "4D") {
      if (thermalConeMesh) {
        const thermalPulse = 0.22 + 0.12 * Math.sin(elapsed * 4);
        thermalConeMesh.material.opacity = thermalPulse;
      }
      if (opticalConeMesh) {
        const optPulse = 0.18 + 0.08 * Math.sin(elapsed * 3);
        opticalConeMesh.material.opacity = optPulse;
      }
      radarRings.forEach((ring, idx) => {
        const s = 1.0 + 0.15 * Math.sin(elapsed * 5 + idx * 1.2);
        ring.scale.set(s, s, 1.0);
      });
    } else {
      if (thermalConeMesh) thermalConeMesh.material.opacity = 0.18;
      if (opticalConeMesh) opticalConeMesh.material.opacity = 0.15;
      radarRings.forEach((ring) => {
        ring.scale.set(1.0, 1.0, 1.0);
      });
    }

    // 5. Hardware Mesh & LED Highlighting
    meshGroup.children.forEach((group) => {
      const dev = group.userData.device;
      if (!dev) return;

      const mainMesh = group.userData.mainMesh;
      if (!mainMesh) return;

      const isRelevant = isScenarioRelevant(dev, state.selectedScenario);
      const isSelected = state.selectedDeviceId !== null && dev.id === state.selectedDeviceId;
      const isHovered = group === hoveredMesh;

      if (isSelected) {
        const pulse = state.visualMode === "4D" ? (0.4 + 0.25 * Math.sin(elapsed * 7)) : 0.45;
        mainMesh.material.emissive = new THREE.Color(0x38bdf8).multiplyScalar(pulse);
        mainMesh.material.opacity = 1.0;
        mainMesh.material.transparent = false;
      } else if (state.selectedScenario !== "ALL") {
        if (isRelevant) {
          const pulse = state.visualMode === "4D" ? (0.25 + 0.15 * Math.sin(elapsed * 5)) : 0.25;
          mainMesh.material.emissive = new THREE.Color(dev.color).multiplyScalar(pulse);
          mainMesh.material.opacity = 1.0;
          mainMesh.material.transparent = false;
        } else {
          mainMesh.material.emissive = new THREE.Color(0x000000);
          mainMesh.material.opacity = 0.32;
          mainMesh.material.transparent = true;
        }
      } else {
        mainMesh.material.opacity = 1.0;
        mainMesh.material.transparent = false;
        if (isHovered) {
          mainMesh.material.emissive = new THREE.Color(0x38bdf8).multiplyScalar(0.4);
        } else {
          mainMesh.material.emissive = new THREE.Color(dev.color).multiplyScalar(0.12);
        }
      }

      // Update LED status badge color
      if (group.userData.led) {
        const liveStatus = state.visualMode === "4D" ? getLiveStatus(dev.id) : "ONLINE";
        const ledColor = new THREE.Color(STATUS_COLORS[liveStatus] || STATUS_COLORS.ONLINE);
        group.userData.led.material.color = ledColor;
      }
    });

    // 6. Wire Highlighting on Hover/Selection
    wiringGroup.children.forEach((wireMesh) => {
      const conn = wireMesh.userData.connection;
      const isConnSelected = state.selectedConnection && state.selectedConnection === conn;
      const isConnHovered = wireMesh === hoveredWire;

      if (isConnSelected || isConnHovered) {
        wireMesh.material.emissive = new THREE.Color(0x38bdf8).multiplyScalar(0.6);
        wireMesh.material.opacity = 1.0;
      } else {
        wireMesh.material.emissive = new THREE.Color(0x000000);
        wireMesh.material.opacity = 0.7;
      }
    });

    // 7. Render Scene
    renderer.render(scene, camera);

    // 8. FPS Counter
    frameCount++;
    if (elapsed - lastFpsUpdate > 1.0) {
      const fps = Math.round(frameCount / (elapsed - lastFpsUpdate));
      if (el.dtStatusFps) {
        el.dtStatusFps.textContent = `4D Engine: ${fps} FPS · Three.js r128 · Live WebGL`;
      }
      frameCount = 0;
      lastFpsUpdate = elapsed;
    }
  }

  // ------------------------------------------------------------------ //
  // 3D/4D Event Handlers & Raycasting
  // ------------------------------------------------------------------ //

  function onWindowResize() {
    if (!renderer || !camera || !el.viewport3D) return;
    const width = el.viewport3D.clientWidth;
    const height = el.viewport3D.clientHeight;
    if (width === 0 || height === 0) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  function onMouseMove(event) {
    if (!renderer || !camera) return;
    const rect = el.canvas3D.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Check device meshes first
    const deviceIntersects = raycaster.intersectObjects(meshGroup.children, true);
    if (deviceIntersects.length > 0) {
      let topGroup = deviceIntersects[0].object;
      while (topGroup.parent && topGroup.parent !== meshGroup) {
        topGroup = topGroup.parent;
      }
      hoveredMesh = topGroup;
      hoveredWire = null;
      el.canvas3D.style.cursor = "pointer";

      const dev = topGroup.userData.device;
      if (dev && el.dtTooltip) {
        el.dtTooltip.hidden = false;
        el.dtTooltipIcon.textContent = dev.icon;
        el.dtTooltipName.textContent = dev.name;
        el.dtTooltipMeta.textContent = `${dev.id} · ${dev.protocol} · ${getLiveStatus(dev.id)}`;
        el.dtTooltip.style.left = `${event.clientX - rect.left + 14}px`;
        el.dtTooltip.style.top = `${event.clientY - rect.top + 14}px`;
      }
      return;
    }

    // Check physical wires
    const wireIntersects = raycaster.intersectObjects(wiringGroup.children, false);
    if (wireIntersects.length > 0) {
      hoveredWire = wireIntersects[0].object;
      hoveredMesh = null;
      el.canvas3D.style.cursor = "pointer";

      const conn = hoveredWire.userData.connection;
      if (conn && el.dtTooltip) {
        el.dtTooltip.hidden = false;
        el.dtTooltipIcon.textContent = "🔌";
        el.dtTooltipName.textContent = `${conn.sourceId} ➔ ${conn.targetId}`;
        el.dtTooltipMeta.textContent = `${conn.protocol} · ${conn.pinMapping}`;
        el.dtTooltip.style.left = `${event.clientX - rect.left + 14}px`;
        el.dtTooltip.style.top = `${event.clientY - rect.top + 14}px`;
      }
      return;
    }

    hoveredMesh = null;
    hoveredWire = null;
    el.canvas3D.style.cursor = "default";
    if (el.dtTooltip) el.dtTooltip.hidden = true;
  }

  function onMouseClick(event) {
    if (!raycaster || !camera) return;
    const rect = el.canvas3D.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // 1. Device Click
    const deviceIntersects = raycaster.intersectObjects(meshGroup.children, true);
    if (deviceIntersects.length > 0) {
      let topGroup = deviceIntersects[0].object;
      while (topGroup.parent && topGroup.parent !== meshGroup) {
        topGroup = topGroup.parent;
      }
      const dev = topGroup.userData.device;
      if (dev) {
        selectHardwareComponent(dev.id);
        return;
      }
    }

    // 2. Wire Connection Click (Open Connection Inspector)
    const wireIntersects = raycaster.intersectObjects(wiringGroup.children, false);
    if (wireIntersects.length > 0) {
      const conn = wireIntersects[0].object.userData.connection;
      if (conn) {
        selectConnection(conn);
        return;
      }
    }

    // 3. Clicked empty 3D space -> Deselect & hide details
    deselectHardware();
    deselectConnection();
  }

  // ------------------------------------------------------------------ //
  // Bounding-Box Solver: "Fit All Hardware"
  // ------------------------------------------------------------------ //

  function fitAllHardware() {
    if (!meshGroup || !camera || !controls) return;

    const box = new THREE.Box3();
    meshGroup.children.forEach(mesh => box.expandByObject(mesh));

    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = camera.fov * (Math.PI / 180);
    const cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2)) * 1.55;

    targetLookAt = center.clone();
    targetCamPos = new THREE.Vector3(
      center.x + cameraZ * 0.65,
      center.y + cameraZ * 0.5,
      center.z + cameraZ * 0.8
    );

    if (el.dtStatusMessage) {
      el.dtStatusMessage.textContent = "Framed all 21 hardware assets in 3D viewport.";
    }
  }

  // ------------------------------------------------------------------ //
  // 2D Technical Wiring Schematic Renderer
  // ------------------------------------------------------------------ //

  function render2DSchematic() {
    if (!el.schematicSvg) return;
    const svg = el.schematicSvg;
    svg.innerHTML = "";

    const ns = "http://www.w3.org/2000/svg";

    const defs = document.createElementNS(ns, "defs");
    defs.innerHTML = `
      <linearGradient id="hubGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#eff6ff" />
        <stop offset="100%" stop-color="#dbeafe" />
      </linearGradient>
    `;
    svg.appendChild(defs);

    // Central Processing Core Hub
    const hubGroup = document.createElementNS(ns, "g");
    hubGroup.setAttribute("class", "schematic-hub");
    hubGroup.innerHTML = `
      <rect x="490" y="320" width="420" height="280" rx="14" fill="url(#hubGrad)" stroke="#2563eb" stroke-width="2.5" />
      <text x="700" y="355" text-anchor="middle" fill="#0f2547" font-family="'Space Grotesk', sans-serif" font-weight="700" font-size="17">RIDGEWATCH MASTER PROCESSING CORE</text>
      <text x="700" y="375" text-anchor="middle" fill="#4d5f80" font-family="'JetBrains Mono', monospace" font-size="11">Raspberry Pi 5 (8GB) + ESP32-S3 Ingestion MCU</text>
      
      <rect x="520" y="400" width="170" height="85" rx="8" fill="#ffffff" stroke="#93c5fd" stroke-width="1.5" />
      <text x="605" y="430" text-anchor="middle" fill="#0f2547" font-weight="700" font-size="12">ESP32-S3 MCU</text>
      <text x="605" y="450" text-anchor="middle" fill="#4d5f80" font-size="10">18-Ch Ingestion &amp; ADC</text>
      <text x="605" y="468" text-anchor="middle" fill="#2563eb" font-size="9">3.3V Logic Rail</text>

      <rect x="710" y="400" width="170" height="85" rx="8" fill="#ffffff" stroke="#93c5fd" stroke-width="1.5" />
      <text x="795" y="430" text-anchor="middle" fill="#0f2547" font-weight="700" font-size="12">Pi 5 Edge AI Core</text>
      <text x="795" y="450" text-anchor="middle" fill="#4d5f80" font-size="10">Fusion, SPS &amp; Triage</text>
      <text x="795" y="468" text-anchor="middle" fill="#e0311f" font-size="9">5.0V / 5A DC Bus</text>

      <line x1="690" y1="442" x2="710" y2="442" stroke="#2563eb" stroke-width="3" stroke-dasharray="3,3" />
      <text x="700" y="435" text-anchor="middle" fill="#2563eb" font-size="8">UART 2M</text>

      <rect x="520" y="515" width="360" height="60" rx="8" fill="#ffffff" stroke="#93c5fd" stroke-width="1.5" />
      <text x="700" y="540" text-anchor="middle" fill="#2563eb" font-weight="700" font-size="12">COMMUNICATION &amp; PMU POWER STRIP</text>
      <text x="700" y="558" text-anchor="middle" fill="#4d5f80" font-size="10">LoRa SX1262 · BG95 Cellular · 7.4V LiFePO4 Battery</text>
    `;
    svg.appendChild(hubGroup);

    const leftSensors = HARDWARE_NODES.filter((_, i) => i % 2 === 0 && !["DEV-CTRL-PI5", "DEV-CTRL-ESP32"].includes(_.id));
    const rightSensors = HARDWARE_NODES.filter((_, i) => i % 2 === 1 && !["DEV-CTRL-PI5", "DEV-CTRL-ESP32"].includes(_.id));

    leftSensors.forEach((dev, idx) => {
      createSchematicNode(svg, dev, 70, 80 + idx * 82, 320, 68, true);
    });

    rightSensors.forEach((dev, idx) => {
      createSchematicNode(svg, dev, 1010, 80 + idx * 82, 320, 68, false);
    });
  }

  function createSchematicNode(svg, dev, x, y, w, h, isLeft) {
    const ns = "http://www.w3.org/2000/svg";
    const g = document.createElementNS(ns, "g");
    g.setAttribute("class", "schematic-node");
    g.style.cursor = "pointer";
    g.onclick = () => selectHardwareComponent(dev.id);

    const isSelected = state.selectedDeviceId !== null && dev.id === state.selectedDeviceId;
    const isRelevant = isScenarioRelevant(dev, state.selectedScenario);
    const strokeCol = isSelected ? "#2563eb" : (isRelevant ? (HARDWARE_CAT_COLORS[dev.category] || "#2563eb") : "#d3e1f5");
    const strokeWidth = isSelected ? "3" : (isRelevant ? "2" : "1");
    const opacity = (state.selectedScenario === "ALL" || isRelevant) ? "1.0" : "0.45";

    const line = document.createElementNS(ns, "path");
    const startX = isLeft ? x + w : x;
    const startY = y + h / 2;
    const endX = isLeft ? 490 : 910;
    const endY = 440 + (y - 450) * 0.25;
    const midX = isLeft ? startX + 50 : startX - 50;

    line.setAttribute("d", `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`);
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", dev.category === "POWER" ? "#e8850a" : "#2563eb");
    line.setAttribute("stroke-width", isSelected ? "2.5" : "1.5");
    line.setAttribute("stroke-dasharray", isSelected ? "none" : "4,3");
    line.setAttribute("opacity", opacity);
    svg.appendChild(line);

    g.innerHTML = `
      <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="#ffffff" stroke="${strokeCol}" stroke-width="${strokeWidth}" opacity="${opacity}" />
      <text x="${x + 14}" y="${y + 26}" fill="#0f2547" font-family="'Space Grotesk', sans-serif" font-weight="700" font-size="13">${dev.icon} ${dev.name}</text>
      <text x="${x + 14}" y="${y + 45}" fill="#4d5f80" font-family="'JetBrains Mono', monospace" font-size="10">${dev.id} · ${dev.protocol} · ${dev.port}</text>
      <text x="${x + 14}" y="${y + 60}" fill="#2563eb" font-family="'JetBrains Mono', monospace" font-size="9">Power: ${dev.powerRail} | Pin: ${dev.port}</text>
      <circle cx="${x + w - 18}" cy="${y + 22}" r="5" fill="${STATUS_COLORS[getLiveStatus(dev.id)] || '#16a34a'}" />
    `;
    svg.appendChild(g);
  }

  // ------------------------------------------------------------------ //
  // Hardware Selection & Deselection Handlers
  // ------------------------------------------------------------------ //

  function selectHardwareComponent(deviceId) {
    state.selectedDeviceId = deviceId;
    const dev = HARDWARE_NODES.find(d => d.id === deviceId);
    if (!dev) return;

    if (el.dtDetailDrawer) {
      el.dtDetailDrawer.hidden = false;
      el.dtDetailIcon.textContent = dev.icon;
      el.dtDetailName.textContent = dev.name;
      el.dtDetailId.textContent = `${dev.id} · ${dev.category}`;
      el.dtDetailCategory.textContent = dev.category;
      el.dtDetailCategory.style.borderColor = HARDWARE_CAT_COLORS[dev.category] || "#6366f1";
      el.dtDetailSimLabel.textContent = dev.isSimulated ? "SIMULATED SENSOR" : "PHYSICAL HARDWARE MODEL";
      
      const liveStatus = getLiveStatus(dev.id);
      el.dtDetailStatusBadge.textContent = liveStatus;
      el.dtDetailStatusBadge.className = `dt-badge is-status-${liveStatus.toLowerCase()}`;

      el.dtDetailConcept.textContent = dev.concept;
      el.dtDetailDesc.textContent = dev.role;
      el.dtDetailProtocol.textContent = dev.protocol;
      el.dtDetailInterfaceNature.textContent = dev.isSimulated ? "VIRTUAL PORT (Software Simulation)" : "NATIVE SYSTEM BUS";
      el.dtDetailVirtualPort.textContent = dev.port || "Pin mapping not configured";
      el.dtDetailConnectedTo.textContent = dev.connectedTo;
      el.dtDetailPowerRail.textContent = dev.powerRail;

      if (el.btnStationTelemetry) {
        el.btnStationTelemetry.href = `hardware.html#${dev.id}`;
      }

      el.dtDetailScenTags.innerHTML = "";
      if (dev.scenarios.includes("ALL")) {
        el.dtDetailScenTags.innerHTML = `<span class="dt-tag is-all">Global (All Scenarios)</span>`;
      } else {
        dev.scenarios.forEach(sc => {
          const span = document.createElement("span");
          span.className = "dt-tag";
          span.textContent = sc.replace(/_/g, " ").toUpperCase();
          el.dtDetailScenTags.appendChild(span);
        });
      }

      updateDetailLiveReadings(dev);
    }

    focusCameraOnDevice(deviceId);
    renderInventoryList();
    if (state.visualMode === "2D") render2DSchematic();
  }

  function deselectHardware() {
    state.selectedDeviceId = null;
    if (el.dtDetailDrawer) el.dtDetailDrawer.hidden = true;
    renderInventoryList();
    if (state.visualMode === "2D") render2DSchematic();
  }

  function focusCameraOnDevice(deviceId) {
    if (!deviceId) return;
    const dev = HARDWARE_NODES.find(d => d.id === deviceId);
    if (!dev || !controls) {
      if (el.dtStatusMessage) {
        el.dtStatusMessage.textContent = "3D model unavailable for this hardware.";
      }
      return;
    }

    targetLookAt = new THREE.Vector3(dev.pos[0], dev.pos[1], dev.pos[2]);
    targetCamPos = new THREE.Vector3(
      dev.pos[0] + (dev.pos[0] >= 0 ? 2.2 : -2.2),
      dev.pos[1] + 1.6,
      dev.pos[2] + 2.8
    );

    if (el.dtStatusMessage) {
      el.dtStatusMessage.textContent = `Focused 3D Camera on [${dev.name}]`;
    }
  }

  // ------------------------------------------------------------------ //
  // Connection Inspector Handler
  // ------------------------------------------------------------------ //

  function selectConnection(conn) {
    state.selectedConnection = conn;
    if (!el.dtConnectionInspector) return;

    el.dtConnectionInspector.hidden = false;
    el.dtConnId.textContent = `${conn.protocol} HARNESS (${conn.sourceId} ➔ ${conn.targetId})`;
    el.dtConnSource.textContent = conn.sourceId;
    el.dtConnProto.textContent = conn.protocol;
    el.dtConnTarget.textContent = conn.targetId;
    el.dtConnProtocol.textContent = conn.protocol;
    el.dtConnPinMapping.textContent = conn.pinMapping || "Pin mapping not configured";
    el.dtConnPowerRail.textContent = conn.powerRail || "Not Configured";
    el.dtConnDataLine.textContent = conn.dataLine || "Telemetry Bus";

    const srcStatus = getLiveStatus(conn.sourceId);
    el.dtConnStatus.textContent = srcStatus === "OFFLINE" ? "OFFLINE (NO TRANSMISSION)" : "ONLINE (STREAMING)";
    el.dtConnStatus.className = srcStatus === "OFFLINE" ? "dt-status-offline" : "dt-status-online";
  }

  function deselectConnection() {
    state.selectedConnection = null;
    if (el.dtConnectionInspector) el.dtConnectionInspector.hidden = true;
  }

  // ------------------------------------------------------------------ //
  // Live Telemetry Reader & Detail Formatter
  // ------------------------------------------------------------------ //

  function updateDetailLiveReadings(dev) {
    if (!el.dtLivePrimaryVal) return;

    if (state.visualMode === "3D") {
      el.dtLivePrimaryVal.textContent = `${dev.powerRail} · Nominal Spec`;
      el.dtLiveTrendVal.textContent = `Bus: ${dev.protocol} (${dev.port || 'Native'})`;
      el.dtLiveQualityVal.textContent = "100% (Physical Twin)";
      return;
    }

    const cache = state.liveTelemetry || {};
    let valStr = "NOMINAL";
    let trendStr = "STABLE";
    let qualStr = "98%";

    if (dev.sensorType) {
      const st = dev.sensorType;
      if (st === "rainfall_intensity" && cache.rainfall) {
        valStr = `${Number(cache.rainfall.rainfall_rate_mm_h || 0).toFixed(1)} mm/h (${cache.rainfall.classification || 'LIGHT'})`;
        trendStr = cache.rainfall.trend || "STABLE";
      } else if (st === "barometric_pressure" && cache.pressure) {
        valStr = `${Number(cache.pressure.pressure_hpa || 1013.2).toFixed(1)} hPa (${cache.pressure.drop_severity || 'NORMAL'})`;
        trendStr = cache.pressure.trend || "STABLE";
      } else if (st === "gas_concentration" && cache.gasSmoke) {
        valStr = `${Number(cache.gasSmoke.gas_concentration_ppm || 10.0).toFixed(1)} PPM (${cache.gasSmoke.gas_level || 'NORMAL'})`;
        trendStr = cache.gasSmoke.rate_of_change_gas ? `Δ ${cache.gasSmoke.rate_of_change_gas}` : "STABLE";
      } else if (st === "smoke_density" && cache.gasSmoke) {
        valStr = `${Number(cache.gasSmoke.smoke_density_pct || 5.0).toFixed(1)}% (${cache.gasSmoke.smoke_level || 'NO_SMOKE'})`;
      } else if (st === "soil_moisture" && cache.slopeNodes && cache.slopeNodes.length) {
        valStr = `${Number(cache.slopeNodes[0].soil_moisture_pct || 38.0).toFixed(1)}% (Saturation)`;
        trendStr = cache.slopeNodes[0].moisture_trend || "STABLE";
      } else if (st === "imu_tilt" && cache.slopeNodes && cache.slopeNodes.length) {
        valStr = `${Number(cache.slopeNodes[0].tilt_angle_deg || 0.5).toFixed(1)}° Inclination`;
        trendStr = cache.slopeNodes[0].tilt_trend || "STABLE";
      } else if (st === "temperature" && cache.temperature) {
        valStr = `${Number(cache.temperature.temperature_c || 15.0).toFixed(1)} °C`;
        trendStr = cache.temperature.trend || "STABLE";
      } else if (st === "humidity" && cache.humidity) {
        valStr = `${Number(cache.humidity.humidity_pct || 50.0).toFixed(1)}% RH`;
        trendStr = cache.humidity.trend || "STABLE";
      } else if (st === "gps" && cache.gps) {
        valStr = `${cache.gps.satellites || 12} Sats (${cache.gps.fix_quality || '3D FIX'})`;
        trendStr = `Lat: ${Number(cache.gps.latitude || 32.374).toFixed(4)}°, Lon: ${Number(cache.gps.longitude || 77.249).toFixed(4)}°`;
      } else if (st === "heart_rate_radar" && cache.survivorSensors && cache.survivorSensors.heart_rate_radar) {
        valStr = `${Number(cache.survivorSensors.heart_rate_radar.value || 72).toFixed(0)} bpm`;
      } else if (st === "thermal_imaging" && cache.survivorSensors && cache.survivorSensors.thermal_imaging) {
        valStr = `${Number(cache.survivorSensors.thermal_imaging.value || 34.2).toFixed(1)} °C Body Heat`;
      } else if (st === "acoustic" && cache.survivorSensors && cache.survivorSensors.acoustic) {
        valStr = `${Number(cache.survivorSensors.acoustic.value || 25.0).toFixed(1)} dB`;
      } else if (st === "co2" && cache.survivorSensors && cache.survivorSensors.co2) {
        valStr = `${Number(cache.survivorSensors.co2.value || 450).toFixed(0)} PPM`;
      } else if (st === "water_level" && cache.waterLevel) {
        valStr = `${Number(cache.waterLevel.water_level_cm || 0).toFixed(1)} cm depth`;
        trendStr = cache.waterLevel.trend || "STABLE";
      } else {
        valStr = `ONLINE (Telemetry Streaming)`;
      }
    } else if (dev.category === "POWER") {
      valStr = `98.4% (Pack Voltage 7.42V)`;
      trendStr = `Discharge: -180 mA nominal`;
    } else if (dev.category === "CONTROLLER") {
      valStr = `Running (Cycle ${cache.cycle || 0})`;
      trendStr = `Edge AI Fusion: OK`;
    } else if (dev.category === "COMMUNICATION") {
      valStr = `Active Mesh (Packet Loss: 0.0%)`;
      trendStr = `LoRa Signal: -78 dBm (Strong)`;
    } else {
      valStr = `Telemetry unavailable for this device.`;
      trendStr = `STATIC`;
    }

    el.dtLivePrimaryVal.textContent = valStr;
    el.dtLiveTrendVal.textContent = trendStr;
    el.dtLiveQualityVal.textContent = qualStr;
  }

  // ------------------------------------------------------------------ //
  // Hardware Inventory Drawer & Category Search Filter
  // ------------------------------------------------------------------ //

  function renderInventoryList() {
    if (!el.dtInventoryList) return;
    el.dtInventoryList.innerHTML = "";

    const query = state.searchQuery.toLowerCase().trim();
    const cat = state.categoryFilter;

    const filtered = HARDWARE_NODES.filter((dev) => {
      const matchCat = cat === "ALL" || dev.category === cat;
      const matchQuery = !query ||
        dev.name.toLowerCase().includes(query) ||
        dev.id.toLowerCase().includes(query) ||
        dev.protocol.toLowerCase().includes(query) ||
        dev.port.toLowerCase().includes(query);
      return matchCat && matchQuery;
    });

    if (el.dtInvCountBadge) {
      el.dtInvCountBadge.textContent = `${filtered.length} Assets`;
    }

    if (filtered.length === 0) {
      el.dtInventoryList.innerHTML = `<p class="empty-note" style="padding: 18px; text-align: center; color: var(--ink-dim);">No equipment matching filter.</p>`;
      return;
    }

    filtered.forEach((dev) => {
      const item = document.createElement("div");
      const isSelected = state.selectedDeviceId !== null && dev.id === state.selectedDeviceId;
      const isRelevant = isScenarioRelevant(dev, state.selectedScenario);
      const liveStatus = getLiveStatus(dev.id);

      item.className = `dt-inv-item ${isSelected ? "is-selected" : ""} ${isRelevant ? "is-scenario-active" : ""}`;
      item.innerHTML = `
        <div class="dt-inv-item-icon">${dev.icon}</div>
        <div class="dt-inv-item-info">
          <div class="dt-inv-item-name">${dev.name}</div>
          <div class="dt-inv-item-sub">${dev.id} · <span style="color: ${HARDWARE_CAT_COLORS[dev.category]}">${dev.category}</span> · ${dev.protocol}</div>
        </div>
        <div class="dt-inv-item-status">
          <span class="dt-dot is-${liveStatus.toLowerCase()}"></span>
        </div>
      `;

      item.onclick = () => selectHardwareComponent(dev.id);
      el.dtInventoryList.appendChild(item);
    });
  }

  function toggleInventory(forceState) {
    state.showInventory = typeof forceState === "boolean" ? forceState : !state.showInventory;
    if (el.dtInventoryDrawer) el.dtInventoryDrawer.hidden = !state.showInventory;
    if (el.btnToggleInventory) el.btnToggleInventory.classList.toggle("is-active", state.showInventory);
    setTimeout(onWindowResize, 50);
  }

  function toggleFullView() {
    state.isFullView = !state.isFullView;

    if (state.isFullView) {
      if (el.dtDetailDrawer) el.dtDetailDrawer.hidden = true;
      if (el.dtInventoryDrawer) el.dtInventoryDrawer.hidden = true;
      if (el.dtConnectionInspector) el.dtConnectionInspector.hidden = true;
      if (el.dtPipelineSection) el.dtPipelineSection.hidden = true;
      if (el.btnToggleInventory) el.btnToggleInventory.classList.remove("is-active");
      if (el.btnToggleFullView) el.btnToggleFullView.classList.add("is-active");
      if (el.lblFullView) el.lblFullView.textContent = "RESTORE VIEW";
    } else {
      if (state.selectedDeviceId && el.dtDetailDrawer) el.dtDetailDrawer.hidden = false;
      if (state.showInventory && el.dtInventoryDrawer) {
        el.dtInventoryDrawer.hidden = false;
        if (el.btnToggleInventory) el.btnToggleInventory.classList.add("is-active");
      }
      if (el.btnToggleFullView) el.btnToggleFullView.classList.remove("is-active");
      if (el.lblFullView) el.lblFullView.textContent = "EXPAND 3D";
    }

    setTimeout(onWindowResize, 50);
  }

  // ------------------------------------------------------------------ //
  // Scenario Mode & Highlighting Helper
  // ------------------------------------------------------------------ //

  function isScenarioRelevant(dev, scenarioId) {
    if (!dev) return false;
    if (scenarioId === "ALL") return true;
    if (dev.scenarios.includes("ALL")) return true;
    return dev.scenarios.includes(scenarioId);
  }

  function setScenarioFilter(scenarioId) {
    state.selectedScenario = scenarioId;

    if (el.dtSelectedScenarioText) {
      el.dtSelectedScenarioText.textContent = scenarioId === "ALL" ? "ALL HARDWARE" : scenarioId.replace(/_/g, " ").toUpperCase();
    }

    if (el.scenarioFilters) {
      const btns = el.scenarioFilters.querySelectorAll(".dt-scen-btn");
      btns.forEach(b => b.classList.toggle("is-active", b.getAttribute("data-scenario") === scenarioId));
    }

    if (el.dtScenarioOptionList) {
      const items = el.dtScenarioOptionList.querySelectorAll(".scenario-option-item");
      items.forEach(it => it.classList.toggle("is-selected", it.getAttribute("data-scenario") === scenarioId));
    }

    if (el.dtActiveScenarioLabel) {
      el.dtActiveScenarioLabel.textContent = scenarioId === "ALL" ? "ALL HARDWARE" : scenarioId.replace(/_/g, " ").toUpperCase();
    }

    updateKpiCounters();
    renderInventoryList();

    if (state.visualMode === "2D") render2DSchematic();

    if (el.dtStatusMessage) {
      el.dtStatusMessage.textContent = `Scenario set to [${scenarioId.replace(/_/g, ' ').toUpperCase()}] — Modalities synchronized.`;
    }
  }

  function updateKpiCounters() {
    let online = 0, warning = 0, critical = 0;

    HARDWARE_NODES.forEach((dev) => {
      const st = getLiveStatus(dev.id);
      if (st === "CRITICAL") critical++;
      else if (st === "WARNING" || st === "DEGRADED") warning++;
      else online++;
    });

    if (el.dtKpiTotal) el.dtKpiTotal.textContent = HARDWARE_NODES.length;
    if (el.dtKpiOnline) el.dtKpiOnline.textContent = online;
    if (el.dtKpiWarning) el.dtKpiWarning.textContent = warning;
    if (el.dtKpiCritical) el.dtKpiCritical.textContent = critical;
  }

  function getLiveStatus(deviceId) {
    const dev = HARDWARE_NODES.find(d => d.id === deviceId);
    if (!dev) return "ONLINE";
    const cache = state.liveTelemetry;

    if (dev.sensorType === "gas_concentration" && cache.gasSmoke) {
      if (cache.gasSmoke.gas_level === "CRITICAL") return "CRITICAL";
      if (cache.gasSmoke.gas_level === "ELEVATED" || cache.gasSmoke.gas_level === "HIGH") return "WARNING";
    }
    if (dev.sensorType === "smoke_density" && cache.gasSmoke) {
      if (cache.gasSmoke.smoke_level === "CRITICAL" || cache.gasSmoke.smoke_level === "HIGH") return "CRITICAL";
      if (cache.gasSmoke.smoke_level === "MODERATE") return "WARNING";
    }
    if (dev.sensorType === "barometric_pressure" && cache.pressure) {
      if (cache.pressure.drop_severity === "CRITICAL") return "CRITICAL";
      if (cache.pressure.drop_severity === "RAPID_DROP") return "WARNING";
    }
    if (dev.sensorType === "rainfall_intensity" && cache.rainfall) {
      if (cache.rainfall.classification === "EXTREME" || cache.rainfall.classification === "VERY_HEAVY") return "CRITICAL";
      if (cache.rainfall.classification === "HEAVY") return "WARNING";
    }
    return "ONLINE";
  }

  // ------------------------------------------------------------------ //
  // Mode Switcher: 2D vs 3D vs 4D LIVE (No Page Reload)
  // ------------------------------------------------------------------ //

  function switchView(mode) {
    state.visualMode = mode;

    el.btnView2D.classList.toggle("is-active", mode === "2D");
    el.btnView3D.classList.toggle("is-active", mode === "3D");
    el.btnView4D.classList.toggle("is-active", mode === "4D");

    if (mode === "2D") {
      el.viewport3D.hidden = true;
      el.viewport2D.hidden = false;
      render2DSchematic();
      if (el.dtSourceBadgeLabel) el.dtSourceBadgeLabel.textContent = "2D WIRING SCHEMATIC — TECHNICAL BUS ARCHITECTURE";
      if (el.dtStatusMessage) el.dtStatusMessage.textContent = "2D Schematic mode active — End-to-end bus interconnect topology.";
    } else if (mode === "3D") {
      el.viewport3D.hidden = false;
      el.viewport2D.hidden = true;
      if (particleGroup) particleGroup.visible = false;
      if (el.dtSourceBadgeLabel) el.dtSourceBadgeLabel.textContent = "3D PHYSICAL DIGITAL TWIN — STRUCTURAL SPECIFICATION";
      if (el.dtStatusMessage) el.dtStatusMessage.textContent = "3D Physical Hardware mode active — Inspecting mechanical layout, wiring harnesses, and pin mappings.";
      onWindowResize();
    } else { // "4D"
      el.viewport3D.hidden = false;
      el.viewport2D.hidden = true;
      if (particleGroup) particleGroup.visible = state.showDataFlow;
      const sourceLabel = state.isRealHardware ? "4D LIVE DIGITAL TWIN — LIVE SENSOR DATA" : "4D LIVE DIGITAL TWIN — REAL-TIME SIMULATION";
      if (el.dtSourceBadgeLabel) el.dtSourceBadgeLabel.textContent = sourceLabel;
      if (el.dtStatusMessage) el.dtStatusMessage.textContent = "4D Live Digital Twin active — Real-Time Telemetry, Data Flow, and Scenario Dynamics Streaming.";
      onWindowResize();
    }
  }

  // ------------------------------------------------------------------ //
  // Live Telemetry Polling Loop
  // ------------------------------------------------------------------ //

  async function apiGet(path) {
    const res = await fetch(state.apiBase + path, { method: "GET" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function pollLiveTelemetry() {
    try {
      const [telemetryLatest, rain, baro, gas, temp, humid, gps, slope, victims, profile] = await Promise.all([
        apiGet("/telemetry/cycle/latest").catch(() => null),
        apiGet("/sensors/rainfall/current").catch(() => null),
        apiGet("/sensors/pressure/current").catch(() => null),
        apiGet("/sensors/gas-smoke/current").catch(() => null),
        apiGet("/sensors/temperature/current").catch(() => null),
        apiGet("/sensors/humidity/current").catch(() => null),
        apiGet("/sensors/gps/current").catch(() => null),
        apiGet("/hazards/landslide/nodes").catch(() => null),
        apiGet("/victims").catch(() => null),
        apiGet("/scenario/sensor-profile").catch(() => null),
      ]);

      const cycle = telemetryLatest ? telemetryLatest.cycle : (victims ? victims.cycle : 0);

      state.liveTelemetry = {
        rainfall: rain ? rain.rainfall : (telemetryLatest ? telemetryLatest.environmental_sensors.rainfall : null),
        pressure: baro ? baro.pressure : (telemetryLatest ? telemetryLatest.environmental_sensors.pressure : null),
        gasSmoke: gas ? gas.gas_smoke : (telemetryLatest ? telemetryLatest.environmental_sensors.gas_smoke : null),
        temperature: temp ? temp.temperature : (telemetryLatest ? telemetryLatest.environmental_sensors.temperature : null),
        humidity: humid ? humid.humidity : (telemetryLatest ? telemetryLatest.environmental_sensors.humidity : null),
        gps: gps ? gps.gps : (telemetryLatest ? telemetryLatest.gps : null),
        slopeNodes: slope ? slope.nodes : null,
        survivorSensors: (victims && victims.victims && victims.victims.length) ? victims.victims[0].sensors : null,
        cycle: cycle,
      };

      state.profile = profile;
      state.scenarioRunning = true;

      updateKpiCounters();
      if (state.selectedDeviceId) {
        const currDev = HARDWARE_NODES.find(d => d.id === state.selectedDeviceId);
        if (currDev) updateDetailLiveReadings(currDev);
      }

      if (el.dtLiveStreamState) {
        el.dtLiveStreamState.textContent = "● LIVE";
        el.dtLiveStreamState.style.color = "#10b981";
      }

    } catch (e) {
      state.scenarioRunning = false;
      if (el.dtLiveStreamState) {
        el.dtLiveStreamState.textContent = "○ STANDBY";
        el.dtLiveStreamState.style.color = "#94a3b8";
      }
    }

    setTimeout(pollLiveTelemetry, POLL_INTERVAL_MS);
  }

  // ------------------------------------------------------------------ //
  // UI Event Bindings
  // ------------------------------------------------------------------ //

  function initUI() {
    // Mode Switcher Buttons (2D / 3D / 4D LIVE)
    el.btnView2D.onclick = () => switchView("2D");
    el.btnView3D.onclick = () => switchView("3D");
    el.btnView4D.onclick = () => switchView("4D");

    // Quick Action Toggles
    if (el.btnToggleFullView) el.btnToggleFullView.onclick = () => toggleFullView();

    el.btnToggleDataFlow.onclick = () => {
      state.showDataFlow = !state.showDataFlow;
      el.lblDataFlow.textContent = `DATA FLOW: ${state.showDataFlow ? "ON" : "OFF"}`;
      el.btnToggleDataFlow.classList.toggle("is-active", state.showDataFlow);
    };

    el.btnTogglePipeline.onclick = () => {
      state.showPipeline = !state.showPipeline;
      el.dtPipelineSection.hidden = !state.showPipeline;
      el.btnTogglePipeline.classList.toggle("is-active", state.showPipeline);
    };

    el.btnPipelineClose.onclick = () => {
      state.showPipeline = false;
      el.dtPipelineSection.hidden = true;
      el.btnTogglePipeline.classList.remove("is-active");
    };

    el.btnToggleInventory.onclick = () => toggleInventory();
    el.btnInventoryClose.onclick = () => toggleInventory(false);

    // Detail Panel & Connection Inspector Close Buttons
    el.btnDetailClose.onclick = () => deselectHardware();
    el.btnConnClose.onclick = () => deselectConnection();

    el.btnDetailFocus.onclick = () => focusCameraOnDevice(state.selectedDeviceId);

    // Camera Preset Controls
    el.btnCamFitAll.onclick = () => fitAllHardware();
    el.btnCamReset.onclick = () => {
      targetLookAt = new THREE.Vector3(0, 0.2, 0);
      targetCamPos = new THREE.Vector3(7.5, 6.0, 9.0);
    };
    el.btnCamTop.onclick = () => {
      targetLookAt = new THREE.Vector3(0, 0, 0);
      targetCamPos = new THREE.Vector3(0.01, 13.5, 0.01);
    };
    el.btnCamFront.onclick = () => {
      targetLookAt = new THREE.Vector3(0, 0.3, 0);
      targetCamPos = new THREE.Vector3(0, 1.2, 9.5);
    };
    el.btnCamIso.onclick = () => {
      targetLookAt = new THREE.Vector3(0, 0.2, 0);
      targetCamPos = new THREE.Vector3(8.0, 7.0, 8.0);
    };
    el.btnCamRotate.onclick = () => {
      state.autoRotate = !state.autoRotate;
      el.btnCamRotate.classList.toggle("is-active", state.autoRotate);
    };
    el.btnCamWires.onclick = () => {
      state.showWires = !state.showWires;
      wiringGroup.visible = state.showWires;
      el.btnCamWires.classList.toggle("is-active", state.showWires);
    };
    if (el.btnCamLabels) {
      el.btnCamLabels.onclick = () => {
        state.showLabels = !state.showLabels;
        meshGroup.children.forEach((grp) => {
          grp.traverse((child) => {
            if (child.isSprite) child.visible = state.showLabels;
          });
        });
        el.btnCamLabels.classList.toggle("is-active", state.showLabels);
      };
    }

    // Inventory Search Box
    el.dtInvSearchInput.addEventListener("input", (e) => {
      state.searchQuery = e.target.value;
      el.dtInvSearchClear.hidden = !state.searchQuery;
      renderInventoryList();
    });

    el.dtInvSearchClear.onclick = () => {
      el.dtInvSearchInput.value = "";
      state.searchQuery = "";
      el.dtInvSearchClear.hidden = true;
      renderInventoryList();
    };

    // Category Filter Pills in Inventory Drawer
    el.dtInvCatPills.addEventListener("click", (e) => {
      const btn = e.target.closest(".dt-cat-btn");
      if (btn) {
        el.dtInvCatPills.querySelectorAll(".dt-cat-btn").forEach(b => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        state.categoryFilter = btn.getAttribute("data-cat");
        renderInventoryList();
      }
    });

    // Global Escape Key to close all modal drawers & clear selection
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        deselectHardware();
        deselectConnection();
        toggleInventory(false);
        if (el.dtPipelineSection) {
          state.showPipeline = false;
          el.dtPipelineSection.hidden = true;
          if (el.btnTogglePipeline) el.btnTogglePipeline.classList.remove("is-active");
        }
      }
    });

    // Populate Initial State
    renderInventoryList();
    deselectHardware();
    deselectConnection();
  }


  // ------------------------------------------------------------------ //
  // Initialization Entry Point
  // ------------------------------------------------------------------ //

  document.addEventListener("DOMContentLoaded", () => {
    init3D();
    initUI();
    pollLiveTelemetry();
  });

})();
