# RIDGEWATCH Subsurface UWB Bioradar Simulation (0–6.0 m Range Upgrade)
## 5.0 m Deep Survivor Demonstration & Fast-Time DSP Architecture

> [!IMPORTANT]
> **SCIENTIFIC & ENGINEERING DISCLAIMER**
> "RIDGEWATCH provides a software-simulated UWB bioradar pipeline for demonstrating subsurface survivor detection and depth estimation. The 0–6 m range is a simulation boundary, and 5 m is an engineering demonstration target. These results are not physical radar measurements and do not constitute experimental validation of 5 m soil penetration."

---

## 1. Simulation Architecture Overview

The RIDGEWATCH Subsurface Bioradar Simulator (`backend/subsurface_dsp.py`) provides an end-to-end deterministic software simulation of an ultra-wideband (UWB) impulse ground-penetrating bioradar sensor (`DEV-UWB-RADAR-01`).

The pipeline models:
1. **Soil Propagation Physics**: Frequency-dependent attenuation, dielectric permittivity, and propagation velocities across 6 configurable strata types and multi-layered soil profiles.
2. **Fast-Time Synthetic A-Scan Generation**: Surface interface reflections, volumetric clutter, depth-dependent two-way exponential path loss ($2 \cdot \alpha \cdot d$), geometric spreading ($1/d^2$), target point reflectors, and additive Gaussian thermal noise.
3. **Ground-Truth Isolated Fast-Time DSP**: Direct-coupling background subtraction, depth-dependent Time-Varying Gain (TVG) amplification up to $+46\text{ dB}$, Hilbert analytic signal envelope extraction, and Non-Maximum Suppression (NMS) peak finding with dynamic depth uncertainty ($\pm \delta\text{ m}$).
4. **Slow-Time Micro-Doppler Vital Sign DSP**: 64-point Discrete Fourier Transform (DFT) spectral estimation isolating physiological frequency bands: Respiration ($0.15\text{–}0.50\text{ Hz}$, $9\text{–}30\text{ RPM}$) and Cardiac ($0.80\text{–}2.20\text{ Hz}$, $48\text{–}132\text{ BPM}$) alongside micro-motion variance.
5. **Multi-Hazard Fusion & Triage (SPS)**: Integration into RIDGEWATCH Survivor Priority Score (SPS) and Landslide sensor weighting (`WEIGHT_UWB_LANDSLIDE = 0.28`).

```
+-----------------------------------------------------------------------------------+
|                            SIMULATION GROUND TRUTH                                 |
| (True Depth: 5.0m | True Respiration: 16 RPM | Alive: True | Soil: Loam 22% Moisture) |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        SYNTHETIC FAST-TIME SCAN GENERATOR                         |
| (256 range bins across 0-6.0m | 2*alpha*d path loss | 1/d^2 spreading | Clutter)   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          | [RAW SYNTHETIC RADAR A-SCAN]
                                          | (DSP is 100% blind to ground truth)
                                          v
+-----------------------------------------------------------------------------------+
|                              FAST-TIME RADAR DSP                                  |
| (Background Subtraction -> +46dB TVG Gain -> Hilbert Envelope -> NMS Peak Finding)|
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                              SLOW-TIME VITALS DSP                                 |
| (DFT Spectral Decomposition: Respiration 0.15-0.50 Hz, Micro-motion, Cardiac)     |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        ESTIMATED TELEMETRY & FUSION                               |
| (Est Depth: 5.02m +-0.09m | Resp: 16.2 RPM | SNR: 11.5 dB | Conf: 85% | SPS: 145)  |
+-----------------------------------------------------------------------------------+
```

---

## 2. 0–6.0 m Range Window & 5.0 m Primary Target

- **Simulation Depth Boundary**: `DEPTH_MAX_M = 6.0` ($0.0\text{–}6.0\text{ meters}$).
- **Primary Demonstration Target**: **5.0 meters** (`preset_5` / `"🚀 RUN 5m SURVIVOR DEMO"`).
- **Range Bin Resolution**: `NUM_RANGE_BINS = 256` bins across $6.0\text{ m}$, providing range bin spacing $\Delta r = 0.0234\text{ m}$ ($2.34\text{ cm}$).
- **Time-of-Flight (ToF) Indexing**:
  $$\text{ToF}(d) = \frac{2 \cdot d}{v_{\text{soil}}}$$
  where $v_{\text{soil}} = \frac{c_0}{\sqrt{\varepsilon_r}}$.

---

## 3. Dielectric Soil Models

The simulator calculates complex dielectric permittivity $\varepsilon_r$, velocity $v_{\text{soil}}$, and attenuation $\alpha$ based on semi-empirical volumetric soil-water models (Topp / Dobson approximations):

| Soil Medium | Typical Moisture ($\%$) | Clay Fraction | Rel. Permittivity $\varepsilon_r$ | Velocity $v$ (m/ns) | Attenuation $\alpha$ (dB/m) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Dry Sandy Soil** | $5\text{–}15\%$ | $0.05$ | $3.0\text{–}6.5$ | $0.12\text{–}0.17$ | $1.5\text{–}4.0\text{ dB/m}$ |
| **Normal / Moist Loam** | $15\text{–}30\%$ | $0.15$ | $6.0\text{–}14.0$ | $0.08\text{–}0.12$ | $4.0\text{–}10.0\text{ dB/m}$ |
| **Wet Soil** | $40\text{–}65\%$ | $0.20$ | $14.0\text{–}30.0$ | $0.05\text{–}0.08$ | $12.0\text{–}25.0\text{ dB/m}$ |
| **Clay Soil** | $30\text{–}50\%$ | $0.45\text{–}0.70$ | $10.0\text{–}28.0$ | $0.05\text{–}0.09$ | $15.0\text{–}32.0\text{ dB/m}$ |
| **Saturated Mud** | $70\text{–}90\%$ | $0.30\text{–}0.50$ | $30.0\text{–}65.0$ | $0.035\text{–}0.055$ | $35.0\text{–}60.0\text{ dB/m}$ |
| **Mixed Rubble / Debris** | $20\text{–}40\%$ | $0.10$ | $6.5\text{–}18.0$ | $0.07\text{–}0.11$ | $6.0\text{–}16.0\text{ dB/m}$ |

---

## 4. Layered-Soil Simulation Model

The simulator supports multi-layer soil strata calculations (`calculate_layered_propagation`):

$$\alpha_{\text{eff}} = \frac{1}{d_{\text{target}}} \sum_{i=1}^{N} \alpha_i \cdot \Delta d_i$$

$$t_{\text{roundtrip}} = \sum_{i=1}^{N} \frac{2 \cdot \Delta d_i}{v_i} \implies v_{\text{eff}} = \frac{2 \cdot d_{\text{target}}}{t_{\text{roundtrip}}}$$

$$\varepsilon_{r,\text{eff}} = \left(\frac{c_0}{v_{\text{eff}}}\right)^2$$

*Example 3-Layer Profile*:
- Layer 1 ($0.0\text{–}0.8\text{ m}$): Dry sand ($\varepsilon_r \approx 4.2$, $\alpha \approx 2.5\text{ dB/m}$)
- Layer 2 ($0.8\text{–}2.5\text{ m}$): Moist loam ($\varepsilon_r \approx 12.0$, $\alpha \approx 8.0\text{ dB/m}$)
- Layer 3 ($2.5\text{–}6.0\text{ m}$): Wet clay ($\varepsilon_r \approx 24.0$, $\alpha \approx 22.0\text{ dB/m}$)

---

## 5. Depth-Dependent Signal Degradation

Synthetic fast-time radar echoes undergo natural physical degradation with depth:
1. **Two-way exponential path loss**: $L_{\text{atten}} = 10^{-\frac{2 \cdot \alpha \cdot d}{20}}$
2. **Geometric spherical spreading**: $L_{\text{spread}} = \frac{1}{(1 + d)^2}$
3. **Composite echo amplitude**:
   $$A_{\text{rx}}(d) = A_0 \cdot L_{\text{atten}} \cdot L_{\text{spread}} + A_{\text{clutter}} + N(0, \sigma^2)$$

*Observed Simulated SNR Progression (Sandy Loam Soil)*:
- **1.0 m**: $+18.2\text{ dB}$ (Crisp, High Confidence)
- **2.0 m**: $+14.6\text{ dB}$ (Strong, High Confidence)
- **3.0 m**: $+11.8\text{ dB}$ (Good, Medium Confidence)
- **4.0 m**: $+8.4\text{ dB}$ (Moderate, Medium Confidence)
- **5.0 m**: $+5.2\text{–}11.5\text{ dB}$ (Challenging, Clear Breathing)
- **6.0 m**: $+1.2\text{–}3.8\text{ dB}$ (Boundary / Weak)

---

## 6. Catalog of 11 Simulation Presets

| Preset ID | Preset Name | Soil Type | Depth | Moisture | Target Count | Expected Outcome |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `preset_1` | Shallow Survivor (1.0m) | Dry Sand | $1.0\text{ m}$ | $15\%$ | 1 | Strong echo ($+18\text{ dB}$ SNR), High confidence |
| `preset_2` | Moderate Depth (2.0m) | Wet Loam | $2.0\text{ m}$ | $45\%$ | 1 | Steady respiration ($+14\text{ dB}$ SNR) |
| `preset_3` | Deep Survivor (3.0m) | Clay Soil | $3.0\text{ m}$ | $35\%$ | 1 | Moderate attenuation ($+11\text{ dB}$ SNR) |
| `preset_4` | Very Deep Survivor (4.0m) | Wet Soil | $4.0\text{ m}$ | $40\%$ | 1 | Lower SNR ($+8\text{ dB}$ SNR), breathing peak |
| `preset_5` | **Primary 5.0m Target (SIH Demo)** | Dry/Loam | $5.0\text{ m}$ | $22\%$ | 1 | **Primary Demo Target**, clear respiration |
| `preset_6` | 6.0m Boundary Case | Dry Sand | $6.0\text{ m}$ | $15\%$ | 1 | Upper boundary test, widened uncertainty |
| `preset_7` | 5.0m Saturated Mud | Saturated Mud | $5.0\text{ m}$ | $85\%$ | 1 | $>160\text{ dB}$ loss $\to$ Low SNR / degraded |
| `preset_8` | 5.0m Heavy Clay | Heavy Clay | $5.0\text{ m}$ | $45\%$ | 1 | High dielectric loss, expanded uncertainty |
| `preset_9` | 5.0m Clutter Debris | Mixed Debris | $5.0\text{ m}$ | $30\%$ | 1 | Demonstrates clutter rejection & peak isolation |
| `preset_10`| Empty Landslide (FP Rejection) | Moist Soil | None | $25\%$ | 0 | False-positive rejection, `NO_TARGET` |
| `preset_11`| Multiple Survivors | Sandy Soil | 1m, 3m, 5m | $15\%$ | 3 | Distinguishes 3 distinct depth echoes |

---

## 7. Strict Ground-Truth Isolation

To maintain scientific integrity, the DSP engine (`process_fast_time_dsp`, `analyze_slow_time_vitals`) **never accesses ground-truth metadata**.

- **Ground Truth**: Used exclusively by `generate_synthetic_fast_time_scan` to synthesize the raw Fast-Time RF A-scan.
- **DSP Processing**: Receives only the raw numerical array `raw_signal[256]` and calculates estimated depth via ToF peak localization.
- **Automated Verification**: Validated by unit test `test_dsp_does_not_use_true_depth_for_5m_target`, which passes an empty ground truth array (`ground_truth_targets=[]`) and confirms accurate peak localization.

---

## 8. Scenario Applicability

Subsurface radar simulation is integrated only into disaster scenarios involving physical entrapment or burial:
- **Applicable**: Landslide, Building Collapse, Earthquake, Avalanche, Cloudburst / Debris Flow, Industrial Collapse.
- **Excluded**: Flood/Tsunami (unless dedicated underwater sonar/acoustic model exists), Wildfire, Cyclone/Windstorm, Extreme Heatwave.

---

## 9. REST API Reference

- `GET /api/subsurface/presets`: Returns all 11 simulation presets.
- `GET /api/subsurface/status`: Returns active configuration and latest radar telemetry.
- `POST /api/subsurface/simulate`: Runs a single simulation cycle.
- `POST /api/subsurface/control`: Controls lifecycle (`start`, `pause`, `resume`, `reset`, `set_preset`).
- `POST /api/subsurface/config`: Modifies simulation parameters ($0.0\text{–}6.0\text{ m}$, soil type, moisture, clutter).
- `POST /api/sensor/subsurface-reading`: Ingests radar telemetry into the RIDGEWATCH Fusion Engine.
