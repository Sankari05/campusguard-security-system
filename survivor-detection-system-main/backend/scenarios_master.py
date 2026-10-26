"""
scenarios_master.py
-------------------
Canonical master list and matching engine for Disaster Scenarios.

Single source of truth across RidgeWatch backend and frontend for:
- 19 supported disaster scenarios
- Scenario metadata (IDs, display labels, categories, icons, hazard capabilities)
- Data-driven staff scenario eligibility matching algorithm
"""

from __future__ import annotations
import re
from typing import Optional, List, Dict, Any


DISASTER_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "earthquake",
        "name": "Earthquake",
        "category": "Geophysical",
        "icon": "🌋",
        "description": "Buildings collapse, people trapped in debris, structural search and rescue required.",
        "keywords": ["earthquake", "quake", "seismic", "tremor", "rubble", "collapse", "structural"],
    },
    {
        "id": "tsunami",
        "name": "Tsunami",
        "category": "Hydrological",
        "icon": "🌊",
        "description": "Coastal areas affected by large waves, coastal flooding, sea-to-shore evacuation and maritime rescue.",
        "keywords": ["tsunami", "tidal_wave", "coastal", "surge", "maritime"],
    },
    {
        "id": "flood",
        "name": "Flood",
        "category": "Hydrological",
        "icon": "💧",
        "description": "Heavy rainfall / river overflow, waterlogged urban and rural sectors, water rescue and boat evacuation.",
        "keywords": ["flood", "flooding", "waterlogging", "inundation", "overflow", "submerged"],
    },
    {
        "id": "cyclone",
        "name": "Cyclone",
        "category": "Meteorological",
        "icon": "🌪️",
        "description": "Severe cyclonic storm, high wind speeds, heavy precipitation, storm surge, rapid evacuation.",
        "keywords": ["cyclone", "hurricane", "typhoon", "storm", "high_winds", "gale"],
    },
    {
        "id": "landslide",
        "name": "Landslide",
        "category": "Geological",
        "icon": "⛰️",
        "description": "Soil/rock displacement, debris flows, blocked transport routes, geotechnical SAR operations.",
        "keywords": ["landslide", "mudslide", "rockfall", "debris_flow", "slope_failure"],
    },
    {
        "id": "building_collapse",
        "name": "Building Collapse",
        "category": "Structural",
        "icon": "🏚️",
        "description": "People trapped inside collapsed buildings, confined-space detection, void search and heavy extraction.",
        "keywords": ["building_collapse", "collapse", "confined_space", "void_search", "concrete", "structural_collapse"],
    },
    {
        "id": "urban_fire",
        "name": "Fire / Urban Fire",
        "category": "Thermal",
        "icon": "🔥",
        "description": "Residential, commercial, or urban fires, smoke inhalation risk, structural burning and evacuation.",
        "keywords": ["urban_fire", "fire", "building_fire", "structure_fire", "flames", "smoke"],
    },
    {
        "id": "wildfire",
        "name": "Forest Fire / Wildfire",
        "category": "Thermal",
        "icon": "🌲",
        "description": "Rapidly spreading forest and vegetation fires, perimeter containment, wilderness evacuation.",
        "keywords": ["wildfire", "forest_fire", "bushfire", "brushfire", "vegetation_fire"],
    },
    {
        "id": "industrial_accident",
        "name": "Industrial Accident",
        "category": "Industrial",
        "icon": "🏭",
        "description": "Manufacturing plant explosions, machinery structural failures, industrial site search and rescue.",
        "keywords": ["industrial_accident", "factory", "explosion", "machinery", "industrial"],
    },
    {
        "id": "chemical_leak",
        "name": "Chemical / Toxic Gas Leak",
        "category": "CBRN / HazMat",
        "icon": "☣️",
        "description": "Hazardous toxic gas dispersion, HazMat decontamination, breathing apparatus response, quarantine perimeter.",
        "keywords": ["chemical_leak", "toxic_gas", "chemical", "gas_leak", "hazmat", "poisonous", "cbrn"],
    },
    {
        "id": "dam_failure",
        "name": "Dam Failure / Dam Break",
        "category": "Hydrological / Structural",
        "icon": "🌊",
        "description": "Catastrophic reservoir breach, sudden downstream flash flood wall, high-speed emergency evacuation.",
        "keywords": ["dam_failure", "dam_break", "reservoir_breach", "flash_flood", "inundation"],
    },
    {
        "id": "avalanche",
        "name": "Avalanche",
        "category": "Cryospheric",
        "icon": "❄️",
        "description": "Snow/ice mass displacement, victim burial under compacted snowpack, probe search, hypothermia triage.",
        "keywords": ["avalanche", "snowpack", "snow_slide", "blizzard", "alpine", "hypothermia"],
    },
    {
        "id": "drought",
        "name": "Drought",
        "category": "Climatological",
        "icon": "☀️",
        "description": "Protracted regional water deficit, emergency potable water distribution, humanitarian logistics.",
        "keywords": ["drought", "water_shortage", "arid", "famine", "desiccation"],
    },
    {
        "id": "heatwave",
        "name": "Extreme Heat / Heatwave",
        "category": "Climatological",
        "icon": "🌡️",
        "description": "Severe thermal anomalies, heatstroke triage, mobile cooling stations, vulnerable citizen monitoring.",
        "keywords": ["heatwave", "extreme_heat", "thermal_stress", "heatstroke", "high_temperature"],
    },
    {
        "id": "cloudburst",
        "name": "Cloudburst",
        "category": "Meteorological",
        "icon": "⛈️",
        "description": "Intense torrential cloudburst rainfall, flash torrents, rapid hillside flooding, emergency SAR.",
        "keywords": ["cloudburst", "torrential_rain", "flash_flood", "downpour", "deluge"],
    },
    {
        "id": "stampede",
        "name": "Stampede / Mass Gathering Accident",
        "category": "Crowd / Humanitarian",
        "icon": "👥",
        "description": "High-density crowd crush, mass casualty triage, emergency corridor clearance, crush injury extraction.",
        "keywords": ["stampede", "mass_gathering", "crowd_crush", "crush_injury", "mass_casualty"],
    },
    {
        "id": "transport_accident",
        "name": "Major Road / Transport Accident",
        "category": "Transportation",
        "icon": "🚌",
        "description": "Multi-vehicle, rail, aviation, or maritime transport crash, vehicle extrication, mass casualty response.",
        "keywords": ["transport_accident", "road_accident", "train_crash", "plane_crash", "derailment", "extrication"],
    },
    {
        "id": "infrastructure_entrapment",
        "name": "Building / Infrastructure Trapped-Person Emergency",
        "category": "Specialized Rescue",
        "icon": "🚇",
        "description": "Tunnel, mine, basement, elevator shaft, or subterranean entrapment requiring technical confined-space SAR.",
        "keywords": ["infrastructure_entrapment", "tunnel", "mine", "subterranean", "elevator", "trapped_person"],
    },
    {
        "id": "multi_hazard",
        "name": "Multi-Hazard Disaster",
        "category": "Compound Disasters",
        "icon": "⚡",
        "description": "Compound cascading disaster scenarios (e.g. Earthquake → Building Collapse → Urban Fire).",
        "keywords": ["multi_hazard", "compound", "cascading", "multi_disaster", "complex"],
    },
]

# Quick lookup index by ID
_SCENARIO_BY_ID = {s["id"]: s for s in DISASTER_SCENARIOS}


def get_all_scenarios() -> List[Dict[str, Any]]:
    """Return complete list of all 19 master disaster scenarios."""
    result = []
    for s in DISASTER_SCENARIOS:
        d = dict(s)
        d["scenario_id"] = s["id"]
        result.append(d)
    return result


def get_scenario_by_id(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Look up a disaster scenario by its ID or alias."""
    if not scenario_id:
        return None
    norm = normalize_scenario_key(scenario_id)
    if norm in _SCENARIO_BY_ID:
        d = dict(_SCENARIO_BY_ID[norm])
        d["scenario_id"] = d["id"]
        return d
    for s in DISASTER_SCENARIOS:
        if norm in [normalize_scenario_key(kw) for kw in s["keywords"]] or norm == normalize_scenario_key(s["name"]):
            d = dict(s)
            d["scenario_id"] = d["id"]
            return d
    return None


def normalize_scenario_key(key: str) -> str:
    """Normalize a scenario name or ID to a standard lowercase alphanumeric_underscore key."""
    if not key:
        return ""
    k = str(key).lower().strip()
    k = re.sub(r"[\s\-\/\\]+", "_", k)
    k = re.sub(r"[^\w_]", "", k)
    # Common alias mappings
    aliases = {
        "fire": "urban_fire",
        "fire_urban_fire": "urban_fire",
        "forest_fire": "wildfire",
        "forest_fire_wildfire": "wildfire",
        "chemical_toxic_gas_leak": "chemical_leak",
        "toxic_gas_leak": "chemical_leak",
        "gas_leak": "chemical_leak",
        "dam_break": "dam_failure",
        "dam_failure_dam_break": "dam_failure",
        "extreme_heat": "heatwave",
        "extreme_heat_heatwave": "heatwave",
        "stampede_mass_gathering_accident": "stampede",
        "mass_gathering_accident": "stampede",
        "major_road_transport_accident": "transport_accident",
        "road_accident": "transport_accident",
        "building_infrastructure_trapped_person_emergency": "infrastructure_entrapment",
        "trapped_person_emergency": "infrastructure_entrapment",
        "multi_hazard_disaster": "multi_hazard",
        "earthquake_building_collapse": "earthquake",
        "himalaya_avalanche": "avalanche",
        "flood_urban": "flood",
    }
    return aliases.get(k, k)


def is_staff_eligible_for_scenario(
    staff_scenarios: Optional[List[str] | str],
    job_scenario: str,
) -> bool:
    """
    Data-driven matching engine:
    Checks if a staff member with `staff_scenarios` is qualified and eligible
    to be assigned to a job or operation with `job_scenario`.
    
    Rules:
    1. Multi-hazard trained staff (`multi_hazard`) are eligible for all scenarios.
    2. Multi-hazard jobs (`multi_hazard`) match staff who have `multi_hazard` OR any constituent hazard capabilities.
    3. Direct match: normalized job_scenario in normalized staff_scenarios.
    4. Keyword/Compound match: If job scenario references related disaster types.
    """
    if not job_scenario:
        return False

    norm_job = normalize_scenario_key(job_scenario)

    # Normalize staff scenarios list
    if staff_scenarios is None:
        return False
    if isinstance(staff_scenarios, str):
        # Support comma-separated or json string
        import json
        try:
            parsed = json.loads(staff_scenarios)
            if isinstance(parsed, list):
                raw_list = parsed
            else:
                raw_list = [staff_scenarios]
        except Exception:
            raw_list = [s.strip() for s in staff_scenarios.split(",") if s.strip()]
    else:
        raw_list = staff_scenarios

    norm_staff_keys = [normalize_scenario_key(s) for s in raw_list if s]

    if not norm_staff_keys:
        return False

    # 1. Staff trained for multi-hazard disaster can handle all scenarios
    if "multi_hazard" in norm_staff_keys:
        return True

    # 2. Multi-hazard job accepts staff trained for multi-hazard or any emergency scenario
    if norm_job == "multi_hazard":
        return len(norm_staff_keys) > 0

    # 3. Direct normalized key match
    if norm_job in norm_staff_keys:
        return True

    # 4. Keyword / Related capabilities match
    job_meta = get_scenario_by_id(norm_job)
    if job_meta:
        job_keywords = set(normalize_scenario_key(k) for k in job_meta.get("keywords", []))
        for s_key in norm_staff_keys:
            if s_key in job_keywords:
                return True
            s_meta = get_scenario_by_id(s_key)
            if s_meta and set(normalize_scenario_key(k) for k in s_meta.get("keywords", [])) & job_keywords:
                return True

    return False
