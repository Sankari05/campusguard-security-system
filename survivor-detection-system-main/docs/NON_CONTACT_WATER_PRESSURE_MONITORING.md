# RIDGEWATCH Non-Contact Flood-Water Level & Hydrostatic Pressure Monitoring System

---

## 1. Executive Summary & Physics Principle

In search-and-rescue (SAR), flood containment, and post-avalanche/dam-break scenarios, deploying submerged contact transducers (such as 316L stainless steel piezoresistive diaphragms) is frequently hazardous or physically impossible due to rapid currents, heavy silt, debris, or inaccessible ravines.

The **RIDGEWATCH Non-Contact Pressure Estimation Module** calculates hydrostatic water column pressure indirectly using fluid statics without placing a sensor inside or touching the water.

### Mathematical Formulation

By Pascal's Principle and the hydrostatic equation for an incompressible fluid:

$$P_{\text{gauge}} = \rho \cdot g \cdot h$$

$$P_{\text{absolute}} = P_{\text{atm}} + (\rho \cdot g \cdot h)$$

Where:
* **$\rho$ (rho)**: Fluid density ($1000.0\text{ kg/m}^3$ for standard fresh flood water; $\approx 1025.0\text{ kg/m}^3$ for seawater/storm surges).
* **$g$**: Gravitational acceleration ($9.80665\text{ m/s}^2$).
* **$h$**: Water-column depth in metres relative to the defined pressure datum.
* **$P_{\text{atm}}$**: Ambient atmospheric pressure from the non-contact barometric sensor (BMP280 / BMP380 in $\text{hPa}$).

---

## 2. Non-Contact Sensing Geometry & Coordinate Frame

```
[ Downward Transceiver: Ultrasonic / 60–80GHz FMCW Radar ]  <-- Mounted at Height H_mount
        |
        |  Non-Contact Time-of-Flight (d_surface)
        v
~~~~~~~~~~~~~~~~~~~ Water Surface ~~~~~~~~~~~~~~~~~~~
|
|   Water Column Depth (h = H_mount - z_datum - d_surface)
|
v
------------------- Pressure Datum (z = 0, e.g. Riverbed / Road Basalt) -------------------
```

1. **Sensor Mount Height ($H_{\text{mount}}$)**: Fixed vertical distance in metres from the sensor reference face to the ground datum ($z = 0$). Configured via `NONCONTACT_SENSOR_MOUNT_HEIGHT_M` (default: `5.0 m`).
2. **Pressure Datum ($z_{\text{datum}}$)**: Elevation baseline where pressure is estimated (e.g., riverbed, basin foundation, or culvert invert). Configured via `NONCONTACT_PRESSURE_DATUM_M` (default: `0.0 m`).
3. **Measured Surface Distance ($d_{\text{surface}}$)**: Downward distance measured by ultrasonic or radar pulse reflection.
4. **Calculated Depth ($h$)**:
   $$h = \max(0.0, (H_{\text{mount}} - z_{\text{datum}}) - d_{\text{surface}})$$
5. **Hydrostatic Pressure**:
   $$P_{\text{Pa}} = \rho \cdot g \cdot h$$
   $$P_{\text{kPa}} = \frac{P_{\text{Pa}}}{1000.0}$$

---

## 3. Sensor Technology Comparison

| Feature | Airborne Ultrasonic (e.g. JSN-SR04T) | 60–80 GHz FMCW Radar (e.g. TI IWR6843) | Submerged Hydrostatic Probe (Contact) |
| :--- | :--- | :--- | :--- |
| **Measurement Mode** | **Non-Contact (Airborne Acoustic ToF)** | **Non-Contact (Airborne mmWave FMCW)** | **Direct In-Situ Contact** |
| **Water Contact Required?** | ❌ **No** | ❌ **No** | ✅ **Yes** |
| **Debris Clogging Risk** | ❌ **Zero (Mounted above water)** | ❌ **Zero (Mounted above water)** | ⚠️ High (Silt & silt fouling) |
| **Immunity to Fog & Rain** | ⚠️ Moderate (Speed of sound varies with air temp) | ✅ High (Electromagnetic waves unaffected by wind/temp) | ✅ Unaffected by surface weather |
| **Maximum Range** | 0.2 m – 6.0 m | 0.1 m – 35.0 m | 0.0 m – 50.0 m column |
| **Typical SAR Application** | Culverts, Urban Bridges, Retaining Basins | River Gorges, Canyon Dams, Torrential Channels | Deep Aquifers, Boreholes |

---

## 4. Operational Limitations & Error Sources

> [!WARNING]
> **Strict Technical Distinction**: This system computes **indirect hydrostatic pressure** from surface level geometry. It does not measure direct compressive stress through a submerged transducer diaphragm.

The following environmental phenomena can introduce uncertainty in non-contact depth and pressure estimation:

1. **Surface Turbulence & Standing Waves**:
   * White-water rapids, standing waves, and surface chop can scatter acoustic and radar reflections, causing pulse jitter ($\pm 2\text{ cm}$ to $\pm 10\text{ cm}$).
   * *Mitigation*: RIDGEWATCH employs rolling exponential moving average (EMA) filtering and sudden jump rejection (`NONCONTACT_MAX_JUMP_RATE_M_S`).
2. **Surface Foam, Aeration & Floating Debris**:
   * Thick foam or dense vegetative drift may attenuate high-frequency ultrasound or reflect slightly above the actual liquid water line.
   * *Mitigation*: mmWave FMCW radar penetrates light foam layer directly to liquid interface.
3. **Air Temperature Gradients (Ultrasonic Specific)**:
   * Speed of sound in air varies with temperature: $c \approx 331.3 \sqrt{1 + T/273.15}\text{ m/s}$.
   * *Mitigation*: Acoustic distance is dynamically temperature-compensated using co-located Sensirion SHT31 / BMP280 temperature sensors.
4. **Mounting Tilt & Alignment Angle**:
   * Transceiver beam must be aligned normal (perpendicular) to the water surface ($< 3^\circ$ off-nadir). Excessive tilt degrades echo return amplitude.

---

## 5. Configuration & Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `NONCONTACT_SENSOR_TYPE` | string | `ultrasonic` | Transceiver modality (`ultrasonic` or `radar`). |
| `NONCONTACT_SENSOR_MOUNT_HEIGHT_M` | float | `5.0` | Fixed vertical height of sensor face above zero datum ($m$). |
| `NONCONTACT_PRESSURE_DATUM_M` | float | `0.0` | Measurement datum elevation baseline ($m$). |
| `NONCONTACT_SENSOR_MAX_RANGE_M` | float | `10.0` | Upper limit of sensor ranging envelope ($m$). |
| `NONCONTACT_SENSOR_TIMEOUT_SECONDS` | float | `10.0` | Stale reading rejection timeout window ($s$). |
| `NONCONTACT_WATER_DENSITY_KG_M3` | float | `1000.0` | Fluid density ($1000\text{ kg/m}^3$ fresh, $1025\text{ kg/m}^3$ saline). |
| `NONCONTACT_GRAVITY_M_S2` | float | `9.80665` | Gravitational constant ($m/s^2$). |
| `NONCONTACT_MAX_JUMP_RATE_M_S` | float | `3.0` | Maximum plausible physical surge rate ($m/s$). |

---

## 6. Field Calibration Protocol

1. **Dry-Datum Calibration**:
   * Mount sensor securely above empty channel/basin.
   * Record dry baseline distance $d_0$. Set `NONCONTACT_SENSOR_MOUNT_HEIGHT_M = d_0`.
   * Verify measured depth $h = 0.00\text{ m}$ and gauge pressure $P = 0.000\text{ kPa}$.
2. **Known-Depth Verification**:
   * Introduce a calibrated water depth (e.g. $1.00\text{ m}$).
   * Confirm sensor surface distance measures $d = (H_{\text{mount}} - 1.00\text{ m})$.
   * Confirm estimated hydrostatic pressure equals $9.807\pm 0.05\text{ kPa}$.
3. **Placard / Datum Marking**:
   * Affix a permanent benchmark plate showing Datum Zero ($z=0$) and Sensor Reference Point ($z=H_{\text{mount}}$) for SAR audit compliance.
