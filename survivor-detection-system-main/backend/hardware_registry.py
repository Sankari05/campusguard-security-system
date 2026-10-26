"""
hardware_registry.py
---------------------
Centralized Hardware & Equipment Inventory Registry for the RidgeWatch
Survivor Detection & Rescue Prioritization System.

Authoritative source of truth for:
- All 18 sensor modalities and physical hardware concepts
- Processing and ingestion controllers (ESP32-S3, Raspberry Pi 5, Command Base Station)
- Power supply and battery management modules (LiFePO4 PMIC, Solar Harvester)
- Communication and telemetry transceivers (LoRa SX1262, GSM/LTE-M, BLE/Wi-Fi)
- Virtual interfaces, bus protocols, and wiring topologies
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional

from models import SensorType, SensorHealthStatus


class HardwareCategory(str, Enum):
    CONTROLLER = "CONTROLLER"
    SENSOR = "SENSOR"
    CAMERA = "CAMERA"
    COMMUNICATION = "COMMUNICATION"
    POWER = "POWER"
    GEOTECHNICAL_NODE = "GEOTECHNICAL_NODE"


class InterfaceProtocol(str, Enum):
    I2C = "I2C"
    SPI = "SPI"
    UART = "UART"
    I2S = "I2S"
    ADC = "ADC"
    GPIO = "GPIO"
    MIPI_CSI = "MIPI_CSI"
    RS485 = "RS485"
    LORA_MESH = "LORA_MESH"
    USB_POWER = "USB_POWER"
    DC_BUS = "DC_BUS"


@dataclass
class HardwareConnection:
    source_id: str
    target_id: str
    protocol: InterfaceProtocol
    pin_mapping: str
    power_rail: str
    data_line: str
    is_virtual: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "protocol": self.protocol.value,
            "pin_mapping": self.pin_mapping,
            "power_rail": self.power_rail,
            "data_line": self.data_line,
            "is_virtual": self.is_virtual,
            "description": self.description,
        }


@dataclass
class HardwareEquipment:
    device_id: str
    name: str
    hardware_concept: str
    category: HardwareCategory
    sensor_type: Optional[SensorType]
    role_description: str
    icon: str
    unit: str
    is_simulated: bool = True
    physical_model_description: str = ""
    nominal_operating_voltage: str = "3.3V"
    nominal_current_draw_ma: float = 25.0
    telemetry_frequency_hz: float = 0.25  # 4s poll cycle
    primary_interface: InterfaceProtocol = InterfaceProtocol.I2C
    virtual_port: str = "VIRTUAL_I2C_0"
    scenario_relevance: List[str] = field(default_factory=list)
    connections: List[HardwareConnection] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["sensor_type"] = self.sensor_type.value if self.sensor_type else None
        d["primary_interface"] = self.primary_interface.value
        d["connections"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in self.connections]
        return d


# --------------------------------------------------------------------------- #
# Canonical Hardware Inventory Definitions
# --------------------------------------------------------------------------- #

HARDWARE_INVENTORY: List[HardwareEquipment] = [
    # 1. Processing Units & Controllers
    HardwareEquipment(
        device_id="DEV-CTRL-PI5",
        name="RidgeWatch Master Processing Core",
        hardware_concept="Raspberry Pi 5 (8GB LPDDR4X, Quad-Core ARM Cortex-A76 @ 2.4GHz)",
        category=HardwareCategory.CONTROLLER,
        sensor_type=None,
        role_description="Edge AI Sensor Fusion, Survivor Priority Scoring (SPS), Triage Classification & Dispatch",
        icon="🧠",
        unit="",
        is_simulated=False,
        physical_model_description="Central Edge Computing Unit executing Python/FastAPI fusion engine and SQLite logging",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=2500.0,
        primary_interface=InterfaceProtocol.USB_POWER,
        virtual_port="HOST_SYSTEM_BUS",
        scenario_relevance=["ALL"],
    ),
    HardwareEquipment(
        device_id="DEV-CTRL-ESP32",
        name="Edge Sensor Ingestion Microcontroller",
        hardware_concept="Espressif ESP32-S3 Dual-Core Xtensa LX7 @ 240MHz (512KB SRAM, 8MB PSRAM)",
        category=HardwareCategory.CONTROLLER,
        sensor_type=None,
        role_description="Multi-Channel ADC/I2C/SPI Ingestion, Hardware Boundary Validation & Frame Packaging",
        icon="🎛️",
        unit="",
        is_simulated=True,
        physical_model_description="Low-power edge microcontroller bridging physical/simulated sensor array to Master Core",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=160.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_BRIDGE",
        scenario_relevance=["ALL"],
    ),

    # 2. Power & Energy Management
    HardwareEquipment(
        device_id="DEV-PWR-PMU",
        name="Intelligent Power Management & Battery Unit",
        hardware_concept="7.4V 5000mAh LiFePO4 Battery Pack + TI TPS65219 Multi-Rail PMIC + I2C Fuel Gauge",
        category=HardwareCategory.POWER,
        sensor_type=None,
        role_description="Regulated power rails (5.0V, 3.3V, 1.8V), battery health monitoring & solar trickle charge",
        icon="🔋",
        unit="%",
        is_simulated=True,
        physical_model_description="Field-deployable battery pack with intelligent power management and telemetry",
        nominal_operating_voltage="7.4V",
        nominal_current_draw_ma=0.0,
        primary_interface=InterfaceProtocol.I2C,
        virtual_port="VIRTUAL_PMIC_I2C (0x5E)",
        scenario_relevance=["ALL"],
    ),

    # 3. Communication Modules
    HardwareEquipment(
        device_id="DEV-COMM-LORA",
        name="Long-Range LoRa Mesh Transceiver",
        hardware_concept="Semtech SX1262 LoRa Transceiver (868/915 MHz, +22dBm output, up to 15km range)",
        category=HardwareCategory.COMMUNICATION,
        sensor_type=None,
        role_description="Disaster-hardened peer-to-peer alert broadcast, packet mesh and field responder sync",
        icon="📡",
        unit="dBm",
        is_simulated=True,
        physical_model_description="Long-range mesh communication module for cellular-denied disaster environments",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=120.0,
        primary_interface=InterfaceProtocol.SPI,
        virtual_port="VIRTUAL_SPI_LORA (CS0)",
        scenario_relevance=["ALL"],
    ),
    HardwareEquipment(
        device_id="DEV-COMM-CELL",
        name="GSM / 4G-5G Cellular Gateway Modem",
        hardware_concept="Quectel BG95-M3 LTE-M / NB-IoT / EGPRS Cellular Modem",
        category=HardwareCategory.COMMUNICATION,
        sensor_type=None,
        role_description="High-throughput command center uplink & cloud telemetry synchronization",
        icon="📶",
        unit="RSSI",
        is_simulated=True,
        physical_model_description="Cellular telemetry modem with automated fallback to LoRa when towers fail",
        nominal_operating_voltage="3.8V",
        nominal_current_draw_ma=250.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_MODEM",
        scenario_relevance=["ALL"],
    ),

    # 4. Vital Signs & Survivor Detection Sensors
    HardwareEquipment(
        device_id="DEV-RADAR-01",
        name="mmWave Heart-Rate & Vital Radar",
        hardware_concept="Texas Instruments IWR6843AOP 60-64GHz mmWave Doppler Radar",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.HEART_RATE_RADAR,
        role_description="Sub-millimeter chest wall motion detection for survivor heartbeat and respiration through rubble",
        icon="📡",
        unit="bpm",
        is_simulated=True,
        physical_model_description="Micro-Doppler vital signs radar penetrating concrete/snowpack without physical contact",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=450.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_RADAR (921600 baud)",
        scenario_relevance=["earthquake", "avalanche", "building_collapse", "landslide", "infrastructure_entrapment"],
    ),
    HardwareEquipment(
        device_id="DEV-PIR-01",
        name="Pyroelectric Passive Infrared Motion Sensor",
        hardware_concept="Panasonic PaPIRs Dual-Element Pyroelectric Motion Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.PIR_MOTION,
        role_description="Kinematic survivor motion detection via differential infrared thermal radiation",
        icon="👁️",
        unit="",
        is_simulated=True,
        physical_model_description="Ultra-low power optical motion sensor triggering active detection cycles upon survivor movement",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=0.015,
        primary_interface=InterfaceProtocol.GPIO,
        virtual_port="VIRTUAL_GPIO_INTR (GPIO 4)",
        scenario_relevance=["earthquake", "building_collapse", "avalanche", "infrastructure_entrapment"],
    ),
    HardwareEquipment(
        device_id="DEV-MIC-01",
        name="Digital Acoustic MEMS Array Microphone",
        hardware_concept="Knowles / TDK InvenSense INMP441 Omnidirectional Digital I2S Microphone",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.ACOUSTIC,
        role_description="Acoustic distress signal detection: human cries, breathing, tapping patterns, and void sounds",
        icon="🎙️",
        unit="dB",
        is_simulated=True,
        physical_model_description="High SNR digital microphone with hardware bandpass filter targeting 20Hz-20kHz survivor acoustics",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=1.4,
        primary_interface=InterfaceProtocol.I2S,
        virtual_port="VIRTUAL_I2S_AUDIO",
        scenario_relevance=["earthquake", "building_collapse", "avalanche", "infrastructure_entrapment"],
    ),
    HardwareEquipment(
        device_id="DEV-CO2-01",
        name="NDIR Carbon Dioxide Gas Sensor",
        hardware_concept="Winsen MH-Z19C NDIR Non-Dispersive Infrared CO2 Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.CO2,
        role_description="Human exhalation pocket concentration measurement in confined subterranean voids",
        icon="💨",
        unit="ppm",
        is_simulated=True,
        physical_model_description="Gold-plated NDIR optical chamber measuring 400-50,000 PPM CO2 concentrations",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=45.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_CO2 (9600 baud)",
        scenario_relevance=["earthquake", "building_collapse", "avalanche", "infrastructure_entrapment"],
    ),

    # 5. Visual & Infrared Cameras
    HardwareEquipment(
        device_id="DEV-CAM-01",
        name="Visible-Spectrum Optical RGB Camera",
        hardware_concept="Raspberry Pi Camera Module v3 (12MP Sony IMX708 with AutoFocus & HDR)",
        category=HardwareCategory.CAMERA,
        sensor_type=SensorType.RGB_CAMERA,
        role_description="Visible spectrum survivor identification, visual scene categorization, and debris inspection",
        icon="📷",
        unit="",
        is_simulated=True,
        physical_model_description="High-resolution optical camera module with 75° FoV connected via MIPI CSI-2 interface",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=300.0,
        primary_interface=InterfaceProtocol.MIPI_CSI,
        virtual_port="VIRTUAL_CSI_CAM0",
        scenario_relevance=["earthquake", "flood", "building_collapse", "tsunami", "urban_fire", "wildfire"],
    ),
    HardwareEquipment(
        device_id="DEV-THM-01",
        name="Long-Wave Infrared (LWIR) Thermal Camera",
        hardware_concept="Teledyne FLIR Lepton 3.5 Radiometric LWIR Core (160×120, 8-14μm)",
        category=HardwareCategory.CAMERA,
        sensor_type=SensorType.THERMAL_IMAGING,
        role_description="Human body heat signature extraction, hypothermia detection, and fire hotspot tracking",
        icon="🌡️",
        unit="°C",
        is_simulated=True,
        physical_model_description="Uncooled microbolometer thermal sensor measuring absolute surface temperature delta (-10 to 400°C)",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=150.0,
        primary_interface=InterfaceProtocol.SPI,
        virtual_port="VIRTUAL_SPI_VOSPI + I2C (0x2A)",
        scenario_relevance=["avalanche", "wildfire", "urban_fire", "earthquake", "building_collapse", "heatwave"],
    ),

    # 6. Structural & Geotechnical Sensors
    HardwareEquipment(
        device_id="DEV-IMU-01",
        name="Inertial Measurement Unit & 3-Axis Tilt",
        hardware_concept="InvenSense MPU-6050 6-DoF Gyroscope + Accelerometer Inclinometer",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.IMU_TILT,
        role_description="Sensor kit orientation, angular slope inclination, and structural shift detection",
        icon="📐",
        unit="°",
        is_simulated=True,
        physical_model_description="MEMS digital motion processor computing gravity vector and tilt angles in degrees",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=3.8,
        primary_interface=InterfaceProtocol.I2C,
        virtual_port="VIRTUAL_I2C_ADDR (0x68)",
        scenario_relevance=["earthquake", "landslide", "building_collapse"],
    ),
    HardwareEquipment(
        device_id="DEV-IMU-02",
        name="Seismic Acceleration & Vibration Sensor",
        hardware_concept="MPU-6050 3-Axis High-Sensitivity Piezoelectric / Accelerometer Channel",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.IMU_VIBRATION,
        role_description="Ground shockwaves, secondary aftershocks, and building collapse tremors",
        icon="📳",
        unit="g",
        is_simulated=True,
        physical_model_description="Seismic vibration channel tracking peak ground velocity (PGV) and acceleration in g",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=3.8,
        primary_interface=InterfaceProtocol.I2C,
        virtual_port="VIRTUAL_I2C_ADDR (0x68)",
        scenario_relevance=["earthquake", "building_collapse", "landslide"],
    ),
    HardwareEquipment(
        device_id="DEV-SOIL-01",
        name="Volumetric Soil Moisture Probe (FDR)",
        hardware_concept="Frequency Domain Reflectometry (FDR) High-Precision Soil Moisture Probe",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.SOIL_MOISTURE,
        role_description="Volumetric soil water saturation measurement for slope liquefaction and landslide prediction",
        icon="🌱",
        unit="%",
        is_simulated=True,
        physical_model_description="Stainless-steel probe measuring soil dielectric permittivity (0-100% volumetric moisture)",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=12.0,
        primary_interface=InterfaceProtocol.ADC,
        virtual_port="VIRTUAL_ADC_CH1",
        scenario_relevance=["landslide", "flood", "cloudburst", "dam_failure"],
    ),
    HardwareEquipment(
        device_id="DEV-SLOPE-ARRAY",
        name="Multi-Node Slope Telemetry Network",
        hardware_concept="3× Geotechnical Telemetry Nodes (SLOPE-01: Upper, SLOPE-02: Mid, SLOPE-03: Base)",
        category=HardwareCategory.GEOTECHNICAL_NODE,
        sensor_type=None,
        role_description="Distributed slope profile monitoring: multi-depth moisture + multi-axis tilt correlation",
        icon="⛰️",
        unit="Risk",
        is_simulated=True,
        physical_model_description="Distributed 3-node geotechnical sensor mesh reporting synchronized landslide risk metrics",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=36.0,
        primary_interface=InterfaceProtocol.RS485,
        virtual_port="VIRTUAL_RS485_SLOPE_BUS",
        scenario_relevance=["landslide", "cloudburst"],
    ),

    # 7. Hydrological & Meteorological Sensors
    HardwareEquipment(
        device_id="DEV-WATER-01",
        name="Submersible Hydrostatic Water-Level Probe",
        hardware_concept="Piezoresistive Submersible Hydrostatic Pressure Transducer",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.WATER_LEVEL,
        role_description="Rising flood water depth, submergence detection, and rate-of-rise computation",
        icon="💧",
        unit="cm",
        is_simulated=True,
        physical_model_description="Submersible 316L stainless steel pressure transmitter measuring 0-20m flood water column",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=20.0,
        primary_interface=InterfaceProtocol.ADC,
        virtual_port="VIRTUAL_ADC_CH0 (4-20mA to Volt)",
        scenario_relevance=["flood", "tsunami", "dam_failure", "cloudburst"],
    ),
    HardwareEquipment(
        device_id="DEV-WATER-NC01",
        name="Non-Contact Radar/Ultrasonic Level & Pressure Sensor",
        hardware_concept="Non-Contact Airborne Ultrasonic / 60-80GHz FMCW Radar Level Gauge",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.WATER_LEVEL,
        role_description="Non-contact downward ranging to flood surface & indirect hydrostatic pressure estimation (P = ρ·g·h)",
        icon="📡",
        unit="cm",
        is_simulated=True,
        physical_model_description="Airborne non-contact downward-ranging level sensor mounted above water to estimate surface distance and hydrostatic pressure",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=25.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_NONCONTACT",
        scenario_relevance=["flood", "tsunami", "dam_failure", "cloudburst"],
    ),
    HardwareEquipment(
        device_id="DEV-WFLOW-01",
        name="Acoustic Doppler Water Flow Velocity Sensor",
        hardware_concept="Compact Acoustic Doppler Current Profiler / Flow Velocity Meter",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.WATER_FLOW,
        role_description="Flood current speed, hydraulic force, and treacherous water velocity tracking",
        icon="🌊",
        unit="m/s",
        is_simulated=True,
        physical_model_description="Doppler ultrasound transducer measuring water flow speeds from 0 to 25 m/s",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=35.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_FLOW",
        scenario_relevance=["flood", "tsunami", "dam_failure"],
    ),
    HardwareEquipment(
        device_id="DEV-RAIN-01",
        name="Optical Infrared Rainfall Disdrometer",
        hardware_concept="RG-11 / Optical Solid-State Precipitation Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.RAINFALL_INTENSITY,
        role_description="Precipitation rate (mm/h) and cumulative rainfall volume (mm) monitoring",
        icon="🌧️",
        unit="mm/h",
        is_simulated=True,
        physical_model_description="Optical infrared drop-sensing dome measuring rainfall intensity up to 500 mm/h without moving parts",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=15.0,
        primary_interface=InterfaceProtocol.GPIO,
        virtual_port="VIRTUAL_GPIO_PULSE (GPIO 18)",
        scenario_relevance=["flood", "landslide", "cyclone", "cloudburst"],
    ),
    HardwareEquipment(
        device_id="DEV-BARO-01",
        name="Precision Barometric Pressure Sensor",
        hardware_concept="Bosch Sensortec BMP280 Digital Barometric Pressure Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.BAROMETRIC_PRESSURE,
        role_description="Atmospheric pressure, cyclone pressure drops, altitude calculation, and storm forecasting",
        icon="⏱️",
        unit="hPa",
        is_simulated=True,
        physical_model_description="High-accuracy piezoresistive pressure transducer (300-1100 hPa with ±0.12 hPa relative accuracy)",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=0.003,
        primary_interface=InterfaceProtocol.I2C,
        virtual_port="VIRTUAL_I2C_ADDR (0x76)",
        scenario_relevance=["cyclone", "flood", "cloudburst", "avalanche"],
    ),

    # 8. Environmental & CBRN Sensors
    HardwareEquipment(
        device_id="DEV-GAS-01",
        name="Multi-Gas & Toxic Concentration Probe",
        hardware_concept="MQ-135 Multi-Gas MOX / Bosch BME680 Environmental Gas Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.GAS_CONCENTRATION,
        role_description="Toxic, hazardous, and combustible chemical gas concentration monitoring (PPM)",
        icon="☣️",
        unit="ppm",
        is_simulated=True,
        physical_model_description="Metal-oxide semiconductor gas sensor detecting CO, ammonia, ethanol, benzene, and toxic VOCs",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=150.0,
        primary_interface=InterfaceProtocol.ADC,
        virtual_port="VIRTUAL_ADC_CH2",
        scenario_relevance=["chemical_leak", "industrial_accident", "urban_fire", "wildfire"],
    ),
    HardwareEquipment(
        device_id="DEV-SMK-01",
        name="Laser Optical Smoke & Particulate Sensor",
        hardware_concept="Plantower PMS5003 / Laser Optical Scattering Dust & Smoke Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.SMOKE_DENSITY,
        role_description="Optical smoke obscuration percentage and particulate density measurement",
        icon="🌫️",
        unit="%",
        is_simulated=True,
        physical_model_description="Laser particulate scattering chamber determining smoke density from 0% to 100% obscuration",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=100.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_SMOKE (9600 baud)",
        scenario_relevance=["urban_fire", "wildfire", "industrial_accident", "chemical_leak"],
    ),
    HardwareEquipment(
        device_id="DEV-TEMP-01",
        name="Precision Ambient Air Temperature Sensor",
        hardware_concept="Sensirion SHT31 / Bosch BME280 Precision Digital Temperature Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.TEMPERATURE,
        role_description="Ambient temperature measurement, hypothermia risk detection, and thermal baseline reference",
        icon="🌡️",
        unit="°C",
        is_simulated=True,
        physical_model_description="Calibrated digital bandgap temperature sensor (-40°C to +125°C with ±0.2°C accuracy)",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=0.002,
        primary_interface=InterfaceProtocol.I2C,
        virtual_port="VIRTUAL_I2C_ADDR (0x70)",
        scenario_relevance=["avalanche", "heatwave", "wildfire", "urban_fire", "drought"],
    ),
    HardwareEquipment(
        device_id="DEV-HUMID-01",
        name="Capacitive Relative Humidity Sensor",
        hardware_concept="Sensirion SHT31 Capacitive Polymer Relative Humidity Sensor",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.HUMIDITY,
        role_description="Atmospheric relative humidity, storm saturation tracking, and moisture baselining",
        icon="💧",
        unit="%",
        is_simulated=True,
        physical_model_description="Capacitive polymer hygrometer measuring 0-100% RH with ±1.5% RH accuracy",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=0.002,
        primary_interface=InterfaceProtocol.I2C,
        virtual_port="VIRTUAL_I2C_ADDR (0x70)",
        scenario_relevance=["flood", "cyclone", "cloudburst", "drought", "wildfire"],
    ),

    # 9. Geospatial Positioning & Navigation
    HardwareEquipment(
        device_id="DEV-GPS-01",
        name="Multi-Constellation GNSS / GPS Receiver",
        hardware_concept="u-blox NEO-M9N Multi-Constellation (GPS, GLONASS, Galileo, BeiDou) GNSS Module",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.GPS,
        role_description="Centimeter-to-meter 3D location positioning, kinematics, fix quality & responder navigation",
        icon="🛰️",
        unit="sats",
        is_simulated=True,
        physical_model_description="92-channel GNSS receiver with active patch antenna providing 10Hz position fixes",
        nominal_operating_voltage="3.3V",
        nominal_current_draw_ma=35.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_GNSS (38400 baud)",
        scenario_relevance=["ALL"],
    ),

    # 10. Subsurface & Soil Penetration (Landslide / Debris)
    HardwareEquipment(
        device_id="DEV-UWB-RADAR-01",
        name="Subsurface UWB Bioradar Simulator",
        hardware_concept="Ultra-Wideband (UWB) Subsurface Ground-Penetrating Bio-Radar Transceiver (Simulated)",
        category=HardwareCategory.SENSOR,
        sensor_type=SensorType.UWB_BIORADAR,
        role_description="Subsurface soil, mud, and rubble penetration detecting buried survivor chest micro-motion, respiration, and cardiac Doppler echoes (SIMULATED)",
        icon="📡",
        unit="%",
        is_simulated=True,
        physical_model_description="Simulated 3.1-10.6 GHz Impulse Radio UWB array with fast-time range profiling and slow-time Doppler demodulation",
        nominal_operating_voltage="5.0V",
        nominal_current_draw_ma=120.0,
        primary_interface=InterfaceProtocol.UART,
        virtual_port="VIRTUAL_UART_UWB (921600 baud)",
        scenario_relevance=["landslide", "earthquake", "debris_flow", "ALL"],
    ),
]

# Quick index by device ID
_HARDWARE_BY_ID = {h.device_id: h for h in HARDWARE_INVENTORY}


# --------------------------------------------------------------------------- #
# Hardware Wiring & Interconnect Topology
# --------------------------------------------------------------------------- #

HARDWARE_TOPOLOGY: List[HardwareConnection] = [
    # Power Distribution Lines
    HardwareConnection(source_id="DEV-PWR-PMU", target_id="DEV-CTRL-PI5", protocol=InterfaceProtocol.USB_POWER, pin_mapping="VOUT_5V -> USB-C VBUS", power_rail="5.0V / 5.0A", data_line="I2C Telemetry"),
    HardwareConnection(source_id="DEV-PWR-PMU", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.DC_BUS, pin_mapping="VOUT_3V3 -> ESP32 3V3", power_rail="3.3V / 1.0A", data_line="Power Only"),
    HardwareConnection(source_id="DEV-PWR-PMU", target_id="DEV-COMM-LORA", protocol=InterfaceProtocol.DC_BUS, pin_mapping="VOUT_3V3 -> SX1262 VDD", power_rail="3.3V", data_line="Power Only"),
    HardwareConnection(source_id="DEV-PWR-PMU", target_id="DEV-COMM-CELL", protocol=InterfaceProtocol.DC_BUS, pin_mapping="VOUT_VBAT -> BG95 VBAT", power_rail="3.8V Peak 2A", data_line="Power Only"),

    # Controller Interconnect (ESP32 Ingestion MCU -> Raspberry Pi 5 Master Core)
    HardwareConnection(source_id="DEV-CTRL-ESP32", target_id="DEV-CTRL-PI5", protocol=InterfaceProtocol.UART, pin_mapping="ESP32 TX/RX -> Pi 5 GPIO14/15 (UART0)", power_rail="3.3V Logic", data_line="Telemetry Stream Buffer (2 Mbps)"),

    # Sensor -> ESP32 Ingestion Lines
    HardwareConnection(source_id="DEV-RADAR-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.UART, pin_mapping="Radar TX/RX -> ESP32 GPIO17/18 (UART1)", power_rail="3.3V DC", data_line="Point Cloud & Doppler Bin Stream"),
    HardwareConnection(source_id="DEV-PIR-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.GPIO, pin_mapping="PIR OUT -> ESP32 GPIO4 (INT)", power_rail="3.3V DC", data_line="Motion Interrupt Pulse"),
    HardwareConnection(source_id="DEV-MIC-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.I2S, pin_mapping="INMP441 SD/WS/SCK -> ESP32 GPIO25/26/27", power_rail="3.3V DC", data_line="24-bit Digital Audio PCM Stream"),
    HardwareConnection(source_id="DEV-CO2-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.UART, pin_mapping="MH-Z19 TX/RX -> ESP32 GPIO16/17 (UART2)", power_rail="5.0V DC", data_line="CO2 Gas Concentration Frame"),
    HardwareConnection(source_id="DEV-IMU-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.I2C, pin_mapping="MPU6050 SDA/SCL -> ESP32 GPIO21/22", power_rail="3.3V DC", data_line="3-Axis Tilt Inclinometer Bus (0x68)"),
    HardwareConnection(source_id="DEV-IMU-02", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.I2C, pin_mapping="MPU6050 SDA/SCL -> ESP32 GPIO21/22", power_rail="3.3V DC", data_line="Seismic Acceleration Bus (0x68)"),
    HardwareConnection(source_id="DEV-SOIL-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.ADC, pin_mapping="FDR Analog Out -> ESP32 GPIO34 (ADC1_CH6)", power_rail="3.3V DC", data_line="Volumetric Soil Saturation Voltage"),
    HardwareConnection(source_id="DEV-SLOPE-ARRAY", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.RS485, pin_mapping="MAX485 RO/DI -> ESP32 GPIO32/33", power_rail="5.0V DC", data_line="3-Node Differential Geotechnical Mesh"),
    HardwareConnection(source_id="DEV-WATER-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.ADC, pin_mapping="Hydrostatic Probe -> ESP32 GPIO35 (ADC1_CH7)", power_rail="5.0V DC", data_line="4-20mA Flood Depth Loop"),
    HardwareConnection(source_id="DEV-WFLOW-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.UART, pin_mapping="Doppler TX/RX -> ESP32 GPIO12/13", power_rail="5.0V DC", data_line="Flow Velocity Stream (m/s)"),
    HardwareConnection(source_id="DEV-RAIN-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.GPIO, pin_mapping="RG-11 Pulse -> ESP32 GPIO19 (INT)", power_rail="5.0V DC", data_line="Precipitation Disdrometer Pulses"),
    HardwareConnection(source_id="DEV-BARO-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.I2C, pin_mapping="BMP280 SDA/SCL -> ESP32 GPIO21/22", power_rail="3.3V DC", data_line="Barometric Pressure I2C Bus (0x76)"),
    HardwareConnection(source_id="DEV-GAS-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.ADC, pin_mapping="MQ-135 AOUT -> ESP32 GPIO36 (ADC1_CH0)", power_rail="5.0V DC", data_line="Multi-Gas MOX Analog Signal"),
    HardwareConnection(source_id="DEV-SMK-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.UART, pin_mapping="PMS5003 TX/RX -> ESP32 GPIO14/15", power_rail="5.0V DC", data_line="Laser Optical Smoke Obscuration Frame"),
    HardwareConnection(source_id="DEV-TEMP-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.I2C, pin_mapping="SHT31 SDA/SCL -> ESP32 GPIO21/22", power_rail="3.3V DC", data_line="Ambient Air Temp I2C (0x70)"),
    HardwareConnection(source_id="DEV-HUMID-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.I2C, pin_mapping="SHT31 SDA/SCL -> ESP32 GPIO21/22", power_rail="3.3V DC", data_line="Relative Humidity I2C (0x70)"),
    HardwareConnection(source_id="DEV-GPS-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.UART, pin_mapping="NEO-M9N TX/RX -> ESP32 GPIO9/10", power_rail="3.3V DC", data_line="NMEA / UBX GNSS Navigation Stream"),
    HardwareConnection(source_id="DEV-UWB-RADAR-01", target_id="DEV-CTRL-ESP32", protocol=InterfaceProtocol.UART, pin_mapping="UWB TX/RX -> ESP32 GPIO23/19 (UART3)", power_rail="5.0V DC", data_line="Fast-Time A-Scan & Slow-Time Doppler Complex Frames (Simulated)"),

    # Direct Master Core Connections (Cameras & Wireless)
    HardwareConnection(source_id="DEV-CAM-01", target_id="DEV-CTRL-PI5", protocol=InterfaceProtocol.MIPI_CSI, pin_mapping="2-Lane MIPI CSI-2 15-pin Flat Ribbon", power_rail="3.3V / 1.8V", data_line="1080p Optical RGB Video / Frame Stream"),
    HardwareConnection(source_id="DEV-THM-01", target_id="DEV-CTRL-PI5", protocol=InterfaceProtocol.SPI, pin_mapping="FLIR Lepton SPI + I2C -> Pi 5 SPI0 & I2C1", power_rail="3.3V / 2.8V", data_line="160x120 Radiometric LWIR Thermal Array"),
    HardwareConnection(source_id="DEV-COMM-LORA", target_id="DEV-CTRL-PI5", protocol=InterfaceProtocol.SPI, pin_mapping="SX1262 SPI -> Pi 5 SPI1 (CS0/IRQ)", power_rail="3.3V DC", data_line="LoRa Mesh Packet Queue"),
    HardwareConnection(source_id="DEV-COMM-CELL", target_id="DEV-CTRL-PI5", protocol=InterfaceProtocol.UART, pin_mapping="BG95 USB / UART -> Pi 5 USB / UART4", power_rail="3.8V DC", data_line="TCP/IP Cloud Gateway Uplink"),
]


# --------------------------------------------------------------------------- #
# Public Accessors
# --------------------------------------------------------------------------- #

def get_hardware_inventory() -> List[Dict[str, Any]]:
    """Return all equipment in the centralized hardware inventory."""
    return [h.to_dict() for h in HARDWARE_INVENTORY]


def get_hardware_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    """Lookup a hardware asset by device ID."""
    h = _HARDWARE_BY_ID.get(device_id)
    return h.to_dict() if h else None


def get_hardware_topology() -> List[Dict[str, Any]]:
    """Return the complete wiring and interconnect topology."""
    return [c.to_dict() for c in HARDWARE_TOPOLOGY]


def get_hardware_summary(active_scenario_id: Optional[str] = None) -> Dict[str, Any]:
    """Calculate dynamic equipment summary counts and category breakdowns."""
    total = len(HARDWARE_INVENTORY)
    by_category = {}
    for h in HARDWARE_INVENTORY:
        cat = h.category.value
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total_equipment": total,
        "categories": by_category,
        "active_scenario": active_scenario_id or "ALL",
        "total_connections": len(HARDWARE_TOPOLOGY),
        "interfaces_used": list({c.protocol.value for c in HARDWARE_TOPOLOGY}),
    }
