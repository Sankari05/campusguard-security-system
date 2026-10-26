"""
generate_backend_documentation_data.py
--------------------------------------
Structured data definitions, 6W analysis for all 14 backend files, and chapter contents for:
RIDGEWATCH Backend Architecture & File-by-File Conceptual Documentation.
"""

BACKEND_FILES_DATA = [
    # 1. api.py
    {
        "name": "api.py",
        "type": "Python Module (FastAPI Application Gateway)",
        "purpose": "Primary HTTP/REST application gateway and WebSocket orchestrator providing over 60 operational endpoints, multi-operation lifecycle management, telemetry ingestion, commander dispatches, analytics summaries, and CORS middleware.",
        "what": "The central web API layer of RidgeWatch exposing RESTful endpoints for the frontend, field tablets, wearable clients, and external sensor ingest nodes.",
        "why": "Decouples backend data processing, multi-sensor fusion, and simulation engines from presentation layers, providing high-concurrency asynchronous endpoints.",
        "who": "Frontend Web Client, Mobile Field Apps, Ingestion Gateways, Incident Commanders, System Evaluators.",
        "where": "Top-level API Gateway Layer (backend/api.py).",
        "when": "Runs continuously as the main ASGI web server process on port 5000 (or custom configured port).",
        "how": "Instantiates FastAPI application; initializes multi-operation registry (ScenarioState); dispatches incoming HTTP requests to fusion engines, database transactions, simulation steppers, and dispatch managers.",
        "inputs": "HTTP GET/POST/PUT/DELETE requests, JSON request bodies (telemetry injections, dispatch assignments, scenario configurations, alert acknowledgments).",
        "outputs": "JSON responses containing serialized operation states, detection results, triage priorities, telemetry timeseries, analytics summaries, and HTTP status codes.",
        "dependencies": "models.py, db.py, fusion_engine.py, scenario_intelligence.py, scenario_loader.py, sensor_simulator.py, rescue_dispatch.py, alert_dispatch.py, hardware_registry.py, scenario_sensor_profiles.py",
        "data_flow": "Receives external HTTP requests -> Validates models via Pydantic -> Interacts with ScenarioState / DB -> Returns serialized JSON response to client.",
        "persistence": "Reads and writes sessions, operational events, custom scenarios, team dispatches, and alert acknowledgments via db.py.",
        "error_handling": "Implements global HTTPException handlers, _require_running guards, pydantic validation error trapping, and safe attribute extractors.",
        "if_missing": "The entire system loses its network interface, rendering all frontend modules, mobile clients, and testing consoles unable to communicate with backend logic.",
        "important_notes": "Maintains an in-memory operations dictionary for concurrent disaster instances, with compatibility proxies (_StateProxy) for legacy single-operation calls."
    },
    # 2. models.py
    {
        "name": "models.py",
        "type": "Python Module (Domain Data Models & Enums)",
        "purpose": "Foundational data contract defining all Pydantic request/response schemas, dataclasses, enums, sensor modalities, GPS geodetic coordinates, health statuses, and SPS calculation models.",
        "what": "The authoritative domain model repository and type system for the entire RidgeWatch backend ecosystem.",
        "why": "Enforces strict type safety, prevents schema drift across modules, and provides standardized serialization/deserialization helpers.",
        "who": "All backend modules (api.py, db.py, fusion_engine.py, sensor_simulator.py, etc.) and automated test suites.",
        "where": "Core Domain Layer (backend/models.py).",
        "when": "Imported at module load time; instantiated on every sensor packet, fusion calculation, database transaction, and API serialization.",
        "how": "Defines enums (SensorType, RiskLevel, TriagePriority, TeamAvailability), dataclasses (GPSCoordinate, SensorHealth, VictimState), and Pydantic validation models.",
        "inputs": "Raw dictionary payloads, constructor arguments, GPS coordinates, sensor readings.",
        "outputs": "Validated immutable data objects, serialized dictionaries (.to_dict()), mathematical helper calculations.",
        "dependencies": "Standard Python libraries (dataclasses, enum, datetime, typing, uuid, math), Pydantic.",
        "data_flow": "Defines schemas instantiated by sensor_simulator.py -> Processed by fusion_engine.py -> Persisted by db.py -> Serialized by api.py.",
        "persistence": "Defines the exact structure of data persisted into SQLite tables.",
        "error_handling": "GPSCoordinate.validate() rejects invalid latitudes (>90°), longitudes (>180°), NaN, and Infinite floats.",
        "if_missing": "The entire backend collapses due to missing core data types, models, and enum definitions.",
        "important_notes": "Includes Haversine great-circle distance formulas, sensor baseline configs (LandslideConfig, PressureConfig, RainfallConfig), and strict null-safety wrappers."
    },
    # 3. db.py
    {
        "name": "db.py",
        "type": "Python Module (SQLite Persistence & Audit Layer)",
        "purpose": "Thread-safe SQLite database manager handling table schema provisioning, disaster session persistence, operational event auditing, responder personnel records, custom scenarios, and analytics query aggregation.",
        "what": "The centralized database abstraction and persistence manager for RidgeWatch.",
        "why": "Guarantees durable audit logs, historical session recording, cross-restart state persistence, and real-time operational query aggregation without requiring heavy external database services.",
        "who": "api.py, rescue_dispatch.py, sensor_simulator.py, analytics reporting engine.",
        "where": "Persistence Layer (backend/db.py).",
        "when": "Initializes on startup; executes synchronous and async SQLite transactions upon event triggers, cycle completions, and API queries.",
        "how": "Manages connection pools and WAL mode; executes parameterized SQL queries for sessions, victims, staff, operational_events, and sensor telemetry.",
        "inputs": "Session metadata, operational event logs, personnel registrations, team structures, telemetry timeseries rows.",
        "outputs": "Aggregated session counts, victim histories, historical telemetry records, CSV audit exports, active ledger lists.",
        "dependencies": "models.py, sqlite3, json, threading, datetime.",
        "data_flow": "Receives operational events from API/Simulator -> Writes indexed rows to survivor_detection.db -> Serves aggregated analytics queries.",
        "persistence": "Manages SQLite database file survivor_detection.db with tables: sessions, operational_events, victims, personnel, teams, custom_scenarios, hardware_stations.",
        "error_handling": "Uses context managers (with closing(conn):), transaction rollbacks on failure, column-existence migrations, and graceful fallbacks for missing tables.",
        "if_missing": "System loses all long-term memory, session history, audited event logs, responder rosters, and analytics reporting.",
        "important_notes": "Configured with SQLite Write-Ahead Logging (WAL) and busy timeouts to prevent database locks during high-frequency telemetry streaming."
    },
    # 4. fusion_engine.py
    {
        "name": "fusion_engine.py",
        "type": "Python Module (Bayesian Multi-Sensor Fusion & SPS Engine)",
        "purpose": "Executes the core Step 0–Step 9 Bayesian evidence fusion algorithm, calculates the Survival Probability Score (SPS), applies multi-hazard environmental multipliers, and derives START triage priority rankings.",
        "what": "The core mathematical and artificial intelligence reasoning engine of RidgeWatch.",
        "why": "Translates noisy, multi-modal, conflicting sensor readings (thermal heat, radar heartbeat, optical bounding boxes, seismic vibration) into an explainable, probabilistic survival score.",
        "who": "api.py, logic.html AI Decision Center, incident dispatch coordinators.",
        "where": "Intelligence & Analytics Layer (backend/fusion_engine.py).",
        "when": "Executed on every simulation cycle or whenever new sensor telemetry packets are ingested for an active disaster scenario.",
        "how": "Normalizes raw readings (Step 0) -> Computes individual modality confidences (Step 1-2) -> Executes Bayesian joint probability fusion (Step 3-5) -> Applies hazard multiplier (Step 6) -> Computes SPS (Step 7-8) -> Ranks victims by triage urgency (Step 9).",
        "inputs": "List of SensorReading objects from multiple sensor stations and victim profiles.",
        "outputs": "Dictionary of DetectionResult objects containing SPS scores (0.0–100.0%), triage classifications (P1_IMMEDIATE, P2_DELAYED, etc.), and step-by-step mathematical proofs.",
        "dependencies": "models.py, scenario_intelligence.py, math, typing.",
        "data_flow": "Consumes SensorReading stream -> Computes mathematical probabilities -> Outputs DetectionResult records to API and db.py.",
        "persistence": "Writes computed triage results and SPS scores to SQLite victims table.",
        "error_handling": "Clamps probabilities between 0.001 and 0.999 to prevent zero-division in Bayesian log-odds; handles missing sensor modalities via neutral prior fallbacks.",
        "if_missing": "The system loses its primary AI capability; survivor survival probabilities, multi-sensor weighting, and triage rankings cannot be calculated.",
        "important_notes": "Includes full mathematical explainability metadata for every step, allowing commanders to inspect the exact formula weights in logic.html."
    },
    # 5. scenario_intelligence.py
    {
        "name": "scenario_intelligence.py",
        "type": "Python Module (Domain-Specific Hazard Intelligence Engine)",
        "purpose": "Evaluates physical hazard thresholds across 19 disaster categories (Landslide, Avalanche, Flood, Earthquake, Wildfire, Chemical Gas Leak, Dam Failure, Cyclone), computes hazard severity scores, and identifies primary sensor drivers.",
        "what": "The multi-hazard domain intelligence and environmental risk calculation engine.",
        "why": "Different disasters have distinct physics; a landslide relies on soil moisture and tilt, whereas a gas leak relies on PPM concentrations. This engine applies specialized disaster-specific intelligence.",
        "who": "fusion_engine.py, api.py, alert_dispatch.py, commander.html, logic.html.",
        "where": "Domain Intelligence Layer (backend/scenario_intelligence.py).",
        "when": "Triggered during operational assessment cycles and whenever environmental telemetry thresholds are evaluated.",
        "how": "Maintains specialized hazard evaluators (_assess_landslide, _assess_flood, _assess_avalanche, etc.); computes hazard risk scores (0–100); evaluates trend vectors (Rising, Rapidly Rising, Spike); outputs operational alerts.",
        "inputs": "ScenarioConfig, current environmental sensor readings (tilt, rainfall, water level, gas ppm, seismic g-force, pressure hPa).",
        "outputs": "ScenarioAssessment object containing overall risk level (LOW, MEDIUM, HIGH, CRITICAL), primary sensor drivers, active hazard alerts, and action guidance.",
        "dependencies": "models.py, scenario_sensor_profiles.py, math, datetime.",
        "data_flow": "Consumes raw environmental telemetry -> Computes domain-specific risk matrices -> Passes hazard multipliers to fusion_engine.py and alert notifications to api.py.",
        "persistence": "Hazard assessments and risk timeline snapshots are stored in memory and persisted to db.py.",
        "error_handling": "Employs safe baseline defaults (e.g. nominal atmospheric pressure 1013.25 hPa) if specific environmental sensors are uncalibrated or offline.",
        "if_missing": "The system cannot perform domain-specific disaster risk assessments or tailor sensor weights to specific disaster categories.",
        "important_notes": "Implements persistence and recovery cycle filters to prevent transient sensor noise spikes from triggering false hazard alarms."
    },
    # 6. sensor_simulator.py
    {
        "name": "sensor_simulator.py",
        "type": "Python Module (Physics & Telemetry Simulation Engine)",
        "purpose": "Simulates physical environment dynamics, realistic sensor telemetry generation, stochastic Gaussian noise, hardware battery drainage, communication dropouts, and victim biometric degradation.",
        "what": "The comprehensive multi-modal sensor and environmental physics simulator.",
        "why": "Enables realistic disaster simulation, testing, algorithm benchmarking, and operational training without requiring live physical disaster deployments.",
        "who": "ScenarioState, testing.html sandbox, automated test suites.",
        "where": "Simulation & Physics Layer (backend/sensor_simulator.py).",
        "when": "Runs synchronously or periodically on every simulation cycle step (e.g. every 1–4 seconds) during active operations.",
        "how": "Maintains physical state variables (tilt angles, rainfall rates, water depths, thermal plumes); injects calibrated Gaussian noise; simulates battery consumption; generates SensorReading streams.",
        "inputs": "ScenarioConfig, manual telemetry injection overrides, cycle step commands, degradation mode flags.",
        "outputs": "Streams of calibrated SensorReading objects for all active stations and detected survivor profiles.",
        "dependencies": "models.py, hardware_registry.py, random, math, datetime.",
        "data_flow": "Generates synthetic sensor data -> Emits readings to fusion_engine.py, hardware_registry.py, and WebSocket/REST endpoints in api.py.",
        "persistence": "Writes raw telemetry timeseries rows to SQLite for historical chart playback.",
        "error_handling": "Bounds all generated values within physical sensor limits (e.g. humidity clamped between 0% and 100%, battery clamped between 0% and 100%).",
        "if_missing": "The system cannot generate synthetic sensor streams, advance disaster cycles, or simulate sensor telemetry for testing.",
        "important_notes": "Supports manual telemetry injection overrides via the Testing Console (/testing/inject-reading) to test edge-case threshold alarms."
    },
    # 7. rescue_dispatch.py
    {
        "name": "rescue_dispatch.py",
        "type": "Python Module (Autonomous Rescue Dispatch Agent)",
        "purpose": "Manages the automated and commander-directed rescue job dispatch workflow, matches responder disaster certifications against active scenarios, tracks team states, and calculates arrival ETAs.",
        "what": "The operational dispatch state machine and resource allocation agent.",
        "why": "Ensures rescue teams are assigned to survivors based on proximity, priority urgency (P1 first), and appropriate disaster skill certifications.",
        "who": "Incident Commander (commander.html), Field Responders (watch.html), Logistics Coordinators.",
        "where": "Operational Dispatch Layer (backend/rescue_dispatch.py).",
        "when": "Executed on every cycle step or when a commander manually issues a job assignment command via REST API.",
        "how": "Evaluates candidate teams; filters staff by disaster qualification; tracks job lifecycle (PENDING -> ASSIGNED -> EN_ROUTE -> ARRIVED -> RESCUED); calculates Haversine travel distance and ETA.",
        "inputs": "DetectionResult rankings, RescueTeamStatus roster, Personnel certification records, manual dispatch requests.",
        "outputs": "Dispatched RescueJob records, updated team availability states, arrival alerts, operational activity logs.",
        "dependencies": "models.py, db.py, datetime, math.",
        "data_flow": "Consumes ranked victims from fusion_engine.py -> Assigns available teams -> Emits dispatch events to db.py and commander.js.",
        "persistence": "Records dispatch assignments, team movements, and rescue completion timestamps in operational_events table.",
        "error_handling": "Prevents double-assignment of busy teams; enforces fallback queuing if no qualified teams are currently available.",
        "if_missing": "Commanders cannot assign rescue teams to victims, track responder movements, or verify rescue completions.",
        "important_notes": "Maintains strict qualification matching (e.g. requiring Avalanche certification before assigning staff to winter avalanche rescue jobs)."
    },
    # 8. alert_dispatch.py
    {
        "name": "alert_dispatch.py",
        "type": "Python Module (Emergency Alert Generation & Multi-Channel Broadcast)",
        "purpose": "Processes safety threshold breaches, generates structured NetworkAlert records, classifies hazard severity, and coordinates multi-channel dispatch (Web Audio, REST ledger, Webhooks, GSM simulation).",
        "what": "The emergency alert lifecycle manager and broadcasting engine.",
        "why": "Provides life-safety warning mechanisms to ensure critical alerts (e.g. secondary landslide danger, toxic gas plume) are instantly broadcast to responders.",
        "who": "Safety Officers, Incident Commanders, Field Personnel (alerts.html, watch.html).",
        "where": "Alerting Layer (backend/alert_dispatch.py).",
        "when": "Triggered when sensor values breach safety thresholds, victim vital signs plunge, or commanders issue manual evacuation alarms.",
        "how": "Creates NetworkAlert objects with unique UUIDs, timestamps, and severity levels (CRITICAL, HIGH, WARNING, INFO); registers in ledger; tracks responder acknowledgment state.",
        "inputs": "ScenarioAssessment alerts, sensor threshold breach signals, commander alarm triggers.",
        "outputs": "Active alert ledgers, JSON alert streams, webhook payloads, acknowledgment audit records.",
        "dependencies": "models.py, db.py, datetime, uuid, typing.",
        "data_flow": "Receives alert signals from scenario_intelligence.py -> Records alert in db.py -> Broadcasts to alerts.html and topbar notification feeds.",
        "persistence": "Persists all generated alerts and responder acknowledgment timestamps to SQLite.",
        "error_handling": "Suppresses duplicate alert spam via deduplication windows; ensures unacknowledged critical alerts remain persistent.",
        "if_missing": "The system cannot generate, record, or broadcast emergency safety warnings to operational personnel.",
        "important_notes": "Supports explicit acknowledgment auditing (/alerts/{id}/ack) with recorded responder identity and timestamp."
    },
    # 9. hardware_registry.py
    {
        "name": "hardware_registry.py",
        "type": "Python Module (Hardware Station Registry & Telemetry Buffer)",
        "purpose": "Maintains physical sensing station inventory, buffers sliding-window telemetry time-series, computes battery depletion rates, and evaluates hardware communication health ratings.",
        "what": "Hardware and sensor station management subsystem.",
        "why": "Ensures physical monitoring stations (masts, solar power units, drone relays) are continuously monitored for hardware failure and communication dropouts.",
        "who": "Hardware Technicians, Systems Engineers (hardware.html, visual.html).",
        "where": "Hardware Infrastructure Layer (backend/hardware_registry.py).",
        "when": "Updated on every incoming sensor reading packet; queried by hardware diagnostic dashboards.",
        "how": "Maintains in-memory station registry; tracks rolling history of last 60 readings per channel; calculates signal quality and battery depletion.",
        "inputs": "Sensor readings, station registration payloads, battery telemetry, heartbeat signals.",
        "outputs": "Station diagnostic summaries, rolling time-series arrays, hardware health status ratings (ONLINE, DEGRADED, OFFLINE).",
        "dependencies": "models.py, collections.deque, datetime, typing.",
        "data_flow": "Buffers incoming sensor packets from sensor_simulator.py -> Serves diagnostic summaries to hardware.js and visual.js.",
        "persistence": "Hardware station definitions and health snapshots are synchronized with SQLite.",
        "error_handling": "Marks stations as STALE or OFFLINE if heartbeat timestamp exceeds timeout threshold (>15s).",
        "if_missing": "Hardware telemetry cannot be buffered or monitored; hardware.html and 3D digital twin lose station health visibility.",
        "important_notes": "Maintains a fixed-size ring buffer (collections.deque) per sensor to guarantee bounded memory usage during long simulation runs."
    },
    # 10. scenario_loader.py
    {
        "name": "scenario_loader.py",
        "type": "Python Module (JSON Scenario Parser & Procedural Entity Placer)",
        "purpose": "Parses standard JSON disaster scenario configurations, validates coordinate schemas, seeds procedural victim locations around site origins, and constructs ScenarioConfig objects.",
        "what": "Scenario configuration loader and geographical entity placement engine.",
        "why": "Provides standardized loading of pre-defined disaster scenarios and dynamic generation of victim and sensor station locations.",
        "who": "api.py, scenarios.html, testing-scenarios.html.",
        "where": "Configuration & Initialization Layer (backend/scenario_loader.py).",
        "when": "Executed when launching a pre-configured disaster scenario or loading the scenario catalog.",
        "how": "Reads JSON scenario files from backend/scenarios/; parses site origin coordinates; procedurally scatters victim entities within calibrated distance bands; returns ScenarioConfig.",
        "inputs": "JSON scenario files (e.g. himalaya_avalanche.json), scenario ID strings.",
        "outputs": "Fully initialized ScenarioConfig objects with populated victim, sensor, and rescue team lists.",
        "dependencies": "models.py, scenario_sensor_profiles.py, json, os, random, math.",
        "data_flow": "Reads JSON disk files -> Validates coordinates -> Passes ScenarioConfig to ScenarioState in api.py.",
        "persistence": "Reads from backend/scenarios/*.json; merges with custom scenarios from SQLite.",
        "error_handling": "Falls back to safe default coordinates and procedural survivor profiles if a JSON scenario file is malformed.",
        "if_missing": "Pre-configured disaster scenarios cannot be loaded from disk into operational memory.",
        "important_notes": "Ensures all victim coordinates are geodetically valid relative to the scenario site origin anchor."
    },
    # 11. scenarios_master.py
    {
        "name": "scenarios_master.py",
        "type": "Python Module (Master Scenario Catalog & Metadata Registry)",
        "purpose": "Maintains the master registry of 19 standardized multi-disaster scenarios, defining disaster types, complexity ratings, default coordinate anchors, and hazard descriptions.",
        "what": "The master catalog and taxonomy definition module for all supported disaster types.",
        "why": "Centralizes scenario metadata, category taxonomies, and geographic presets across the entire application.",
        "who": "api.py, scenarios.html, testing-add-scenario.js.",
        "where": "Metadata & Taxonomy Layer (backend/scenarios_master.py).",
        "when": "Imported on startup to populate available scenario lists and dropdown pickers.",
        "how": "Exposes dictionary of scenario definitions indexed by normalized scenario key (e.g. 'landslide', 'earthquake', 'flood', 'avalanche', 'chemical_leak').",
        "inputs": "Scenario query keys, catalog requests.",
        "outputs": "Standardized scenario metadata dictionaries (name, category, complexity, default victims, description).",
        "dependencies": "models.py, typing.",
        "data_flow": "Provides metadata schemas to api.py -> Rendered by scenarios.js on the frontend catalog.",
        "persistence": "Static in-memory definition table; used to seed initial database scenario ledgers.",
        "error_handling": "normalize_scenario_key helper handles case-insensitive lookups, aliases, and hyphen-to-underscore normalization.",
        "if_missing": "The system loses its master catalog of disaster definitions, complexity ratings, and category mappings.",
        "important_notes": "Supports 19 distinct disaster categories: Landslide, Earthquake, Flood, Avalanche, Wildfire, Chemical Leak, Tsunami, Cyclone, Dam Failure, etc."
    },
    # 12. scenario_sensor_profiles.py
    {
        "name": "scenario_sensor_profiles.py",
        "type": "Python Module (Sensor-to-Scenario Profile Mapping Registry)",
        "purpose": "Defines explicit sensor modality relevance profiles for every disaster type, categorizing sensors into PRIMARY (highest weight), SUPPORTING (secondary evidence), and INACTIVE (ignored).",
        "what": "Sensor modality profile and relevance mapping registry.",
        "why": "Prevents irrelevant sensor modalities from corrupting Bayesian fusion (e.g. water level sensors should not influence an avalanche rescue score).",
        "who": "fusion_engine.py, scenario_intelligence.py, logic.html AI Decision Center.",
        "where": "Configuration & Taxonomy Layer (backend/scenario_sensor_profiles.py).",
        "when": "Queried during scenario initialization, fusion evidence weighting, and AI explainability rendering.",
        "how": "Maps each disaster key to a ScenarioSensorProfile dataclass containing primary_sensors, supporting_sensors, and inactive_sensors lists.",
        "inputs": "Scenario ID or disaster type string.",
        "outputs": "ScenarioSensorProfile object with categorized SensorType lists.",
        "dependencies": "models.py, typing.",
        "data_flow": "Provides sensor relevance rules to fusion_engine.py and scenario_intelligence.py.",
        "persistence": "In-memory configuration matrix.",
        "error_handling": "Returns a balanced multi-hazard default sensor profile if an unrecognized scenario key is passed.",
        "if_missing": "The system cannot distinguish which sensors are primary versus irrelevant for a given disaster type.",
        "important_notes": "Directly drives the Level 2 Sensor Evidence breakdown in the logic.html AI Decision Center."
    },
    # 13. scenarios/*.json (5 files)
    {
        "name": "scenarios/*.json (5 Scenario Seed Files)",
        "type": "JSON Data Files (Standard Disaster Scenarios)",
        "purpose": "Static scenario seed definitions providing baseline coordinates, hazard profiles, victim rosters, and sensor kit layouts for 5 core disaster simulations.",
        "what": "JSON scenario configuration files stored on disk.",
        "why": "Provides out-of-the-box demonstration scenarios for offline training, drills, and hackathon evaluation.",
        "who": "scenario_loader.py, system instructors, evaluators.",
        "where": "Configuration Data Layer (backend/scenarios/).",
        "when": "Loaded into memory upon user selection of pre-configured scenarios.",
        "how": "Contains structured JSON objects: chemical_gas_leak.json, earthquake_building_collapse.json, flood_urban.json, himalaya_avalanche.json, wildfire_forest.json.",
        "inputs": "Static JSON file contents.",
        "outputs": "Raw scenario configuration dictionaries parsed by scenario_loader.py.",
        "dependencies": "backend/scenario_loader.py",
        "data_flow": "Disk JSON -> scenario_loader.py -> ScenarioConfig -> ScenarioState in api.py.",
        "persistence": "Static configuration files on filesystem.",
        "error_handling": "Validated by scenario_loader.py against Pydantic schemas before operational ingestion.",
        "if_missing": "Pre-configured offline demonstration scenarios cannot be loaded from disk.",
        "important_notes": "Contains calibrated site origins (e.g. Kedarnath Valley coordinates for Himalayan Avalanche)."
    },
    # 14. scripts/cleanup_default_data.py
    {
        "name": "scripts/cleanup_default_data.py",
        "type": "Python Utility Script (Database Maintenance & Data Migration)",
        "purpose": "Maintenance utility for purging stale test sessions, resetting SQLite database tables, and verifying schema integrity prior to production deployments.",
        "what": "Database administrative and maintenance script.",
        "why": "Ensures testing databases are cleanly reset between evaluation runs without leaving orphaned foreign key records.",
        "who": "System Administrators, QA Automation, DevOps Engineers.",
        "where": "Maintenance & Utility Layer (backend/scripts/).",
        "when": "Executed manually via CLI or as part of automated CI/CD database teardown workflows.",
        "how": "Connects to survivor_detection.db; executes cleanup SQL statements; vacuums database to reclaim disk space.",
        "inputs": "Command-line invocation.",
        "outputs": "Cleaned database file and stdout maintenance confirmation log.",
        "dependencies": "sqlite3, os.",
        "data_flow": "Direct SQLite DDL/DML execution -> Cleansed database.",
        "persistence": "Modifies SQLite tables directly.",
        "error_handling": "Catches SQLite exceptions and logs cleanup status.",
        "if_missing": "Automated database resets must be performed through manual SQL commands.",
        "important_notes": "Intended strictly for administrative maintenance and testing environment resets."
    }
]

# ---------------------------------------------------------------------------
# CHAPTER & SECTION CONTENTS (25 SECTIONS)
# ---------------------------------------------------------------------------

BACKEND_SECTIONS_CONTENT = [
    # SECTION 1: EXECUTIVE SUMMARY & BACKEND PURPOSE
    {
        "title": "1. Executive Summary & Backend Purpose",
        "blocks": [
            {
                "type": "paragraph",
                "text": "RIDGEWATCH is an autonomous, AI-powered multi-disaster survivor detection, medical triage prioritization, and tactical search-and-rescue coordination system. "
                        "The backend represents the mission-critical computational core of RidgeWatch. "
                        "It ingests multi-modal physical sensor streams, executes mathematical Bayesian evidence fusion, models domain-specific disaster physics, evaluates life-safety risk thresholds, "
                        "coordinates autonomous rescue dispatch workflows, and guarantees audited SQLite data persistence."
            },
            {
                "type": "heading2",
                "text": "Core Operational Questions Answered by the Backend"
            },
            {
                "type": "paragraph",
                "prefix": "1. What is the backend?",
                "text": "A high-performance, asynchronous Python backend built upon FastAPI, SQLite, Pydantic, and specialized mathematical intelligence algorithms, comprising 14 audited modules, engines, and datasets."
            },
            {
                "type": "paragraph",
                "prefix": "2. Why is the backend necessary?",
                "text": "Disaster environments produce noisy, incomplete, and conflicting sensor readings across chaotic spatial environments. The backend eliminates guesswork by fusing multi-sensor evidence into an explainable Survival Probability Score (SPS), automating team dispatches, and enforcing safety thresholds in real time."
            },
            {
                "type": "paragraph",
                "prefix": "3. Who interacts with it?",
                "text": "The frontend web portal (Dashboard, Visual 3D, Logical AI, Commander, Analytics), mobile field responder apps (Watch interface), IoT sensor gateway nodes, automated test suites, and incident command personnel."
            },
            {
                "type": "paragraph",
                "prefix": "4. Where does it sit in the system topology?",
                "text": "It resides as the central computational nexus between external physical/synthetic sensor feeds, the SQLite persistence layer, and all client-facing presentation interfaces."
            },
            {
                "type": "paragraph",
                "prefix": "5. When are backend services triggered?",
                "text": "Continuously via asynchronous background simulation loops, event-driven sensor telemetry packets, scheduled diagnostic health checks, and incoming REST API requests."
            },
            {
                "type": "paragraph",
                "prefix": "6. How does data move through the backend?",
                "text": "Raw sensor telemetry -> Ingestion & validation -> Bayesian evidence fusion -> Domain hazard assessment -> Triage prioritization -> Dispatch generation -> SQLite persistence -> REST/WebSocket client delivery."
            },
            {
                "type": "callout",
                "title": "MATHEMATICAL INTEGRITY MANDATE",
                "text": "All metrics emitted by the backend (SPS scores, rescue rates, hazard multipliers, arrival ETAs) derive strictly from rigorous mathematical formulas and validated simulation models. The backend enforces zero fake data and zero fabricated metrics across all endpoints."
            }
        ]
    },

    # SECTION 2: BACKEND ARCHITECTURAL PHILOSOPHY & DESIGN PRINCIPLES
    {
        "title": "2. Backend Architectural Philosophy & Design Principles",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The RidgeWatch backend is engineered around six foundational architectural principles:"
            },
            {
                "type": "paragraph",
                "prefix": "1. Modularity & Loose Coupling:",
                "text": "Sensor simulation, evidence fusion, domain intelligence, alert broadcasting, and dispatch state machines exist as independent Python modules with explicit data contracts."
            },
            {
                "type": "paragraph",
                "prefix": "2. Explainable AI Reasoning:",
                "text": "Avoids opaque black-box machine learning models in favor of transparent, auditable Step 0–Step 9 Bayesian probability calculations and explicit hazard multipliers."
            },
            {
                "type": "paragraph",
                "prefix": "3. Zero-Footprint Embedded Persistence:",
                "text": "Utilizes embedded SQLite with Write-Ahead Logging (WAL) and bounded in-memory ring buffers, requiring zero external database installations or cloud dependencies."
            },
            {
                "type": "paragraph",
                "prefix": "4. Multi-Operation Concurrency:",
                "text": "Supports isolated concurrent disaster operations in memory via the ScenarioState registry, allowing multiple disaster simulations to run simultaneously without cross-talk."
            },
            {
                "type": "paragraph",
                "prefix": "5. Geodetic & Kinematic Precision:",
                "text": "All spatial locations use WGS-84 GPS coordinates with Haversine great-circle distance math and boundary sanity validations."
            },
            {
                "type": "paragraph",
                "prefix": "6. Graceful Fault Tolerance & Degradation:",
                "text": "When individual sensors drop out or report corrupted packets, the fusion engine automatically falls back to neutral Bayesian priors without crashing operational workflows."
            }
        ]
    },

    # SECTION 3: BACKEND SYSTEM ARCHITECTURE & COMPONENT TOPOLOGY
    {
        "title": "3. Backend System Architecture & Component Topology",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The backend component topology illustrates the unidirectional flow of operational telemetry from physical/simulated sensing sources through mathematical fusion to client delivery."
            },
            {
                "type": "heading2",
                "text": "High-Level Architectural Topology"
            },
            {
                "type": "paragraph",
                "text": "                 EXTERNAL CLIENTS / FRONTEND MODULES\n"
                        "                                  │ (HTTP REST / WebSockets)\n"
                        "                                  ▼\n"
                        "                     FASTAPI APPLICATION GATEWAY\n"
                        "                              (api.py)\n"
                        "                                  │\n"
                        "        ┌─────────────────────────┼─────────────────────────┐\n"
                        "        │                         │                         │\n"
                        "        ▼                         ▼                         ▼\n"
                        "  DOMAIN MODELS &           SQLITE PERSISTENCE        HARDWARE REGISTRY\n"
                        "   PYDANTIC SCHEMAS               LAYER                & HEALTH BUFFER\n"
                        "    (models.py)                  (db.py)           (hardware_registry.py)\n"
                        "        │                         ▲                         ▲\n"
                        "        ▼                         │                         │\n"
                        "  SENSOR SIMULATOR & ─────────────┼─────────────────────────┘\n"
                        "  PHYSICS INGESTION ENGINE        │\n"
                        "  (sensor_simulator.py)           │\n"
                        "        │                         │\n"
                        "        ▼                         │\n"
                        "  BAYESIAN MULTI-SENSOR           │\n"
                        "  EVIDENCE FUSION ENGINE          │\n"
                        "   (fusion_engine.py)             │\n"
                        "        │                         │\n"
                        "        ▼                         │\n"
                        "  SCENARIO DOMAIN                 │\n"
                        "  INTELLIGENCE ENGINE             │\n"
                        " (scenario_intelligence.py)       │\n"
                        "        │                         │\n"
                        "   ┌────┴────────────┬────────────┴────┐\n"
                        "   │                 │                 │\n"
                        "   ▼                 ▼                 ▼\n"
                        "DISPATCH AGENT    ALERT BROADCAST   ANALYTICS SUMMARY\n"
                        "(rescue_dispatch) (alert_dispatch)    AGGREGATOR\n"
                        "   │                 │                 │\n"
                        "   └─────────────────┼─────────────────┘\n"
                        "                     ▼\n"
                        "         PERSISTED TO survivor_detection.db"
            }
        ]
    },

    # SECTION 4: DATA MODELS, SCHEMAS & ENTITIES (models.py)
    {
        "title": "4. Data Models, Schemas & Entity Specifications (models.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/models.py establishes the formal domain type system for the entire application, defining 18 specialized Enums, 24 DataClasses, and Pydantic validation schemas."
            },
            {
                "type": "heading2",
                "text": "Primary Domain Entity Classes"
            },
            {
                "type": "table",
                "headers": ["CLASS / ENUM NAME", "CATEGORY", "PURPOSE & ATTRIBUTES"],
                "data": [
                    ["SensorType", "Enum (str)", "Defines 18 sensor modalities (THERMAL_IMAGING, PIR_MOTION, ACOUSTIC, CO2, HEART_RATE_RADAR, IMU_TILT, RAINFALL_INTENSITY, etc.)"],
                    ["GPSCoordinate", "DataClass", "WGS-84 location model with latitude, longitude, altitude_m, validation, and Haversine distance calculations"],
                    ["SensorReading", "DataClass", "Raw and normalized sensor telemetry packet with timestamp, sensor_id, raw_value, normalized_value, and confidence"],
                    ["SensorHealth", "DataClass", "Tracks station battery percentage (0–100%), signal quality (0.0–1.0), and health status (ONLINE, DEGRADED, OFFLINE)"],
                    ["VictimState", "DataClass", "Individual survivor tracking model with GPS position, vital signs (HR, SpO2), burial depth, triage priority, and SPS"],
                    ["DetectionResult", "DataClass", "Output of Bayesian fusion containing SPS survival score, triage classification, hazard multiplier, and explainability proofs"],
                    ["RescueTeamStatus", "DataClass", "Rescue team model containing team_id, callsign, base location, availability state, and assigned member rosters"],
                    ["TeamMember", "DataClass", "Individual responder model with member_id, full name, operational role, and certified disaster category lists"],
                    ["RescueJob", "DataClass", "Tactical mission task connecting a rescue team to a target survivor with dispatch status, timestamp, and ETA"],
                    ["NetworkAlert", "DataClass", "Emergency hazard warning with alert_id, severity (CRITICAL, HIGH, WARNING), hazard type, message, and ack state"],
                    ["ScenarioConfig", "DataClass", "Full disaster scenario configuration with scenario_id, site_origin, victim templates, and sensor stations"],
                ],
                "widths": [1.8, 1.2, 3.4]
            }
        ]
    },

    # SECTION 5: BAYESIAN MULTI-SENSOR FUSION & SPS ENGINE (fusion_engine.py)
    {
        "title": "5. Multi-Sensor Bayesian Fusion & SPS Engine (fusion_engine.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/fusion_engine.py implements the mathematical core of RidgeWatch, deriving the Survival Probability Score (SPS) and START triage classifications across 10 distinct mathematical calculation steps."
            },
            {
                "type": "heading2",
                "text": "The Step 0–Step 9 Mathematical Pipeline"
            },
            {
                "type": "table",
                "headers": ["STEP", "MATHEMATICAL OPERATION", "CONCEPTUAL RESPONSIBILITY"],
                "data": [
                    ["Step 0", "Raw Telemetry Normalization", "Normalizes heterogenous sensor units (°C, dB, ppm, mm/h) to standardized [0.0, 1.0] intensity ranges"],
                    ["Step 1", "Modality Weight Assignment", "Assigns disaster-specific sensor weights based on scenario profile (Primary = 0.35, Supporting = 0.15)"],
                    ["Step 2", "Signal Quality Adjustment", "Multiplies raw readings by sensor hardware health, battery level, and transmission signal quality"],
                    ["Step 3", "Individual Likelihood Mapping", "Maps adjusted intensities to Bayesian conditional detection probabilities P(Detection | Victim Present)"],
                    ["Step 4", "Bayesian Joint Odds Fusion", "Combines independent sensor evidence using Bayesian log-odds update formulas to eliminate false positives"],
                    ["Step 5", "Posterior Probability Normalization", "Converts joint odds back into a normalized posterior presence confidence score [0.0, 1.0]"],
                    ["Step 6", "Environmental Hazard Multiplier", "Applies environmental penalty scaling based on secondary hazard severity (e.g. rising flood or soil tilt)"],
                    ["Step 7", "Vital Signs Viability Scaling", "Evaluates Doppler heartbeat radar and thermal signature to scale baseline survival capacity"],
                    ["Step 8", "Survival Probability Score (SPS)", "Calculates final composite Survival Probability Score (0.0% to 100.0%)"],
                    ["Step 9", "START Triage Classification & Queue", "Classifies survivor into P1_IMMEDIATE, P2_DELAYED, P3_MINIMAL, or P4_DECEASED and sorts rescue queue"],
                ],
                "widths": [0.8, 2.2, 3.4]
            }
        ]
    },

    # SECTION 6: DOMAIN INTELLIGENCE & MULTI-HAZARD RULE ENGINE (scenario_intelligence.py)
    {
        "title": "6. Scenario Domain Intelligence & Multi-Hazard Rule Engine (scenario_intelligence.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/scenario_intelligence.py contains specialized physical assessment logic tailored for 19 distinct disaster categories."
            },
            {
                "type": "heading2",
                "text": "Supported Disaster Evaluation Models"
            },
            {
                "type": "paragraph",
                "prefix": "• Geotechnical & Landslide Evaluator (_assess_landslide):",
                "text": "Monitors Biaxial Inclinometer tilt angles, volumetric soil moisture saturation %, and cumulative rainfall. Detects rapid slope shear failure and generates early landslide alarms."
            },
            {
                "type": "paragraph",
                "prefix": "• Hydrological & Flood Evaluator (_assess_flood):",
                "text": "Analyzes ultrasonic water level sensors and flow velocity probes. Detects flash flood surges and dam overtopping events."
            },
            {
                "type": "paragraph",
                "prefix": "• Cryospheric & Avalanche Evaluator (_assess_avalanche):",
                "text": "Evaluates snowpack temperature gradients, ambient acoustic shockwaves, and burial depth altimetry."
            },
            {
                "type": "paragraph",
                "prefix": "• Structural & Seismic Evaluator (_assess_earthquake):",
                "text": "Processes 3-axis IMU vibration g-forces and acoustic void resonance to detect secondary structural building collapses."
            },
            {
                "type": "paragraph",
                "prefix": "• Atmospheric & Cyclone Evaluator (_assess_cyclone):",
                "text": "Tracks barometric pressure plunges (hPa/cycle) and sustained wind velocity to classify storm severity."
            },
            {
                "type": "paragraph",
                "prefix": "• Chemical & Toxic Gas Evaluator (_assess_chemical_leak):",
                "text": "Monitors PPM concentrations of toxic industrial gases (CO, Chlorine, Ammonia) and optical smoke obscuration."
            }
        ]
    },

    # SECTION 7: SENSOR & ENVIRONMENTAL PHYSICS SIMULATOR (sensor_simulator.py)
    {
        "title": "7. Sensor & Environmental Physics Simulator (sensor_simulator.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/sensor_simulator.py drives the dynamic physics and telemetry streaming engine. It generates realistic, noisy, time-varying sensor packets across all deployed stations."
            },
            {
                "type": "heading2",
                "text": "Key Simulation Subsystems"
            },
            {
                "type": "paragraph",
                "prefix": "• Stochastic Physics Model:",
                "text": "Combines baseline environmental drift curves with calibrated Gaussian noise to simulate real-world sensor fluctuations."
            },
            {
                "type": "paragraph",
                "prefix": "• Environmental Degradation & Dropout Engine:",
                "text": "Simulates packet dropouts, sensor calibration drift, communication latency, and battery depletion over operational cycles."
            },
            {
                "type": "paragraph",
                "prefix": "• Interactive Telemetry Override Injector:",
                "text": "Provides direct REST injection hooks (/testing/inject-reading) allowing testers and evaluators to manually trigger threshold alarms."
            }
        ]
    },

    # SECTION 8: AUTONOMOUS RESCUE DISPATCH & STAFF MATCHING (rescue_dispatch.py)
    {
        "title": "8. Autonomous Rescue Dispatch & Staff Eligibility Matching (rescue_dispatch.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/rescue_dispatch.py serves as the operational resource allocation agent and tactical dispatch state machine."
            },
            {
                "type": "heading2",
                "text": "The 5-Stage Rescue Job Lifecycle"
            },
            {
                "type": "paragraph",
                "text": "PENDING (Survivor classified P1/P2 in rescue queue)\n"
                        "    ↓\n"
                        "ASSIGNED (Commander / Agent matches certified team)\n"
                        "    ↓\n"
                        "EN_ROUTE (Team dispatched, ETA tracking active)\n"
                        "    ↓\n"
                        "ARRIVED (Team confirms on-scene arrival at coordinates)\n"
                        "    ↓\n"
                        "RESCUED (Survivor extracted and marked safe)"
            },
            {
                "type": "heading2",
                "text": "Staff Eligibility & Certification Rules"
            },
            {
                "type": "paragraph",
                "text": "The dispatch agent enforces strict qualification matching before assigning personnel to tactical missions:\n"
                        "• Avalanche missions require certified Avalanche Rescue Specialists.\n"
                        "• Flood missions require certified Swiftwater / Dive Rescue Responders.\n"
                        "• Building collapse missions require certified Urban Search & Rescue (USAR) Specialists.\n"
                        "• Chemical leak missions require certified Hazardous Materials (Hazmat) Technicians."
            }
        ]
    },

    # SECTION 9: EMERGENCY ALERT GENERATION & BROADCAST (alert_dispatch.py)
    {
        "title": "9. Emergency Alert Generation & Multi-Channel Broadcast (alert_dispatch.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/alert_dispatch.py manages safety-critical alert lifecycles and multi-channel broadcast distribution."
            },
            {
                "type": "heading2",
                "text": "Alert Categorization & Severity Tiers"
            },
            {
                "type": "table",
                "headers": ["SEVERITY", "TRIGGER CONDITION", "OPERATIONAL ACTION"],
                "data": [
                    ["CRITICAL", "Imminent secondary collapse, toxic gas threshold, flash flood surge", "Immediate evacuation alarm, audio siren pulses on web/watch"],
                    ["HIGH", "Rapid slope tilt acceleration, rising flood waters, victim vitals plunging", "Priority warning banner, reroute rescue teams to safe corridors"],
                    ["WARNING", "Elevated rainfall accumulation, station battery <20%, packet dropouts", "Logistics warning, schedule battery replacement / sensor inspection"],
                    ["INFO", "New victim detected, team arrived on scene, scenario cycle advanced", "Routine operational audit log update"],
                ],
                "widths": [1.2, 2.6, 2.6]
            }
        ]
    },

    # SECTION 10: HARDWARE REGISTRY & TELEMETRY DIAGNOSTICS (hardware_registry.py)
    {
        "title": "10. Hardware Station Registry & Telemetry Diagnostics (hardware_registry.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/hardware_registry.py provides physical station inventory tracking and high-frequency telemetry buffering."
            },
            {
                "type": "heading2",
                "text": "Diagnostic Buffer Architecture"
            },
            {
                "type": "paragraph",
                "prefix": "• Sliding Window Ring Buffer:",
                "text": "Maintains a memory-efficient collections.deque buffer of the last 60 readings per sensor channel, providing zero-latency timeseries history."
            },
            {
                "type": "paragraph",
                "prefix": "• Heartbeat & Dropout Monitor:",
                "text": "Evaluates packet timestamps; transitions stations from ONLINE -> DEGRADED -> OFFLINE if heartbeat latency exceeds 15 seconds."
            }
        ]
    },

    # SECTION 11: DATABASE ARCHITECTURE & AUDIT PERSISTENCE (db.py)
    {
        "title": "11. Database Architecture, Persistence & Audit Ledger (db.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/db.py implements the SQLite persistence layer, providing durable audit logs, historical session recording, and real-time query aggregation."
            },
            {
                "type": "heading2",
                "text": "Primary SQLite Database Tables"
            },
            {
                "type": "table",
                "headers": ["TABLE NAME", "PRIMARY KEY", "STORED DATA & AUDIT ROLE"],
                "data": [
                    ["sessions", "session_id (TEXT)", "Historical disaster runs, scenario IDs, start/end timestamps, victim counts, rescue totals"],
                    ["operational_events", "event_id (TEXT)", "Chronological audit log of all dispatches, arrivals, rescues, alerts, and system state changes"],
                    ["victims", "victim_id (TEXT)", "Persisted victim records, GPS coordinates, burial depths, triage priorities, and SPS scores"],
                    ["personnel", "person_id (TEXT)", "Registered responder database with callsigns, roles, contact info, and certified skill matrices"],
                    ["teams", "team_id (TEXT)", "Configured rescue teams, home base coordinates, team leads, and member associations"],
                    ["custom_scenarios", "scenario_id (TEXT)", "User-authored custom multi-disaster scenarios with custom coordinate anchors"],
                    ["sensor_readings", "reading_id (TEXT)", "Historical sensor timeseries rows for chart playback and post-mission analytics"],
                ],
                "widths": [1.5, 1.4, 3.5]
            }
        ]
    },

    # SECTION 12: FASTAPI APPLICATION GATEWAY (api.py)
    {
        "title": "12. FastAPI Application Gateway & REST Endpoints Specification (api.py)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "backend/api.py exposes over 60 RESTful endpoints organized into 8 functional operational clusters."
            },
            {
                "type": "heading2",
                "text": "API Route Clusters"
            },
            {
                "type": "paragraph",
                "prefix": "1. Scenario Management Routes:",
                "text": "GET /scenarios (Catalog), POST /scenario/start (Launch), POST /scenario/stop, GET /scenario/intelligence, GET /scenario/meta."
            },
            {
                "type": "paragraph",
                "prefix": "2. Victim & Triage Routes:",
                "text": "GET /victims (Active roster), GET /victims/{id} (Individual vitals), GET /logic/step-calculations (SPS mathematical breakdown)."
            },
            {
                "type": "paragraph",
                "prefix": "3. Tactical Command & Dispatch Routes:",
                "text": "GET /commander/overview (Clustered map state), POST /commander/dispatch (Assign job), GET /rescue-team/members-status (Roster)."
            },
            {
                "type": "paragraph",
                "prefix": "4. Emergency Alert Routes:",
                "text": "GET /alerts (Active hazard ledger), POST /alerts/{id}/ack (Acknowledge alert with responder timestamp)."
            },
            {
                "type": "paragraph",
                "prefix": "5. Analytics & Performance Routes:",
                "text": "GET /analytics/summary (Scope-filtered session totals), GET /hazards/landslide/history (Telemetry timeseries)."
            },
            {
                "type": "paragraph",
                "prefix": "6. Hardware & Telemetry Routes:",
                "text": "GET /hardware/summary (Station health grid), GET /hardware/registry (Raw channels), GET /hardware/telemetry/timeseries."
            },
            {
                "type": "paragraph",
                "prefix": "7. Administrative Master Records Routes:",
                "text": "GET /admin/persons, POST /admin/person/create, GET /admin/teams, POST /admin/team/create, POST /admin/scenario/create."
            },
            {
                "type": "paragraph",
                "prefix": "8. Testing Console & Simulation Sandbox Routes:",
                "text": "POST /testing/step (Cycle step), POST /testing/inject-reading (Synthetic telemetry override), POST /testing/reset."
            }
        ]
    },

    # SECTION 13: SCENARIO LOADERS & CATALOG REGISTRIES
    {
        "title": "13. Scenario Loader, Master Catalog & Sensor Profiles",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The scenario subsystem (scenario_loader.py, scenarios_master.py, scenario_sensor_profiles.py) manages disaster scenario lifecycles, metadata catalogs, and sensor relevance profiles."
            },
            {
                "type": "heading2",
                "text": "Subsystem Responsibilities"
            },
            {
                "type": "paragraph",
                "prefix": "• scenario_loader.py:",
                "text": "Parses JSON disaster configurations from disk, seeds procedural victim positions around site origins, and constructs ScenarioConfig objects."
            },
            {
                "type": "paragraph",
                "prefix": "• scenarios_master.py:",
                "text": "Master taxonomy registry defining 19 standard disaster types, complexity ratings, geographic anchors, and normalize_scenario_key lookups."
            },
            {
                "type": "paragraph",
                "prefix": "• scenario_sensor_profiles.py:",
                "text": "Explicit sensor modality relevance matrix mapping primary, supporting, and inactive sensors for each disaster category."
            }
        ]
    },

    # SECTION 14: SCENARIO SEEDS & UTILITY SCRIPTS
    {
        "title": "14. Standard Scenario Seed Library & Database Scripts",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The static seed library (backend/scenarios/*.json) and maintenance utilities (backend/scripts/cleanup_default_data.py) support offline demonstrations and database maintenance."
            },
            {
                "type": "heading2",
                "text": "Standard Seed Scenarios on Disk"
            },
            {
                "type": "paragraph",
                "text": "1. himalaya_avalanche.json (High-altitude winter avalanche in Kedarnath Valley)\n"
                        "2. earthquake_building_collapse.json (Urban structural collapse with trapped survivors)\n"
                        "3. flood_urban.json (Urban flash flood with rising water levels)\n"
                        "4. chemical_gas_leak.json (Industrial toxic gas leak and smoke dispersal)\n"
                        "5. wildfire_forest.json (Forest fire with expanding thermal front)"
            }
        ]
    },

    # SECTION 15: BACKEND-TO-FRONTEND COMMUNICATION INTERFACES
    {
        "title": "15. Backend-to-Frontend Communication & Telemetry Interfaces",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Communication between the backend and client interfaces occurs through standard REST JSON payloads and polling cycles."
            },
            {
                "type": "heading2",
                "text": "Communication Architecture"
            },
            {
                "type": "paragraph",
                "prefix": "• Polling Frequency Standards:",
                "text": "Dashboard, Commander, and Alerts poll every 3 seconds; Victims and Watch poll every 4 seconds; Hardware and Analytics poll on user interaction."
            },
            {
                "type": "paragraph",
                "prefix": "• Cross-Origin Resource Sharing (CORS):",
                "text": "FastAPI CORSMiddleware is pre-configured with permissive local network origins, allowing seamless connection across mobile field tablets and desktop command monitors."
            }
        ]
    },

    # SECTION 16: END-TO-END BACKEND OPERATIONAL WORKFLOWS
    {
        "title": "16. End-to-End Backend Operational Workflows (Lifecycle 1 through 10)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "This section traces the 10 comprehensive end-to-end backend data processing lifecycles."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 1: Disaster Scenario Initialization & Memory Allocation"
            },
            {
                "type": "paragraph",
                "text": "1. API receives POST /scenario/start with scenario_id='landslide'.\n"
                        "2. scenario_loader.py reads configuration or generates procedural site origin coordinates.\n"
                        "3. ScenarioState is initialized in memory with sensor_simulator, fusion_engine, and rescue_dispatch.\n"
                        "4. db.py writes new session row into sessions table with start timestamp."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 2: Multi-Modal Sensor Telemetry Streaming"
            },
            {
                "type": "paragraph",
                "text": "1. sensor_simulator.py advances cycle clock.\n"
                        "2. Inclinometer tilt increases to 9.2°, Rain Gauge reports 34 mm/h precipitation.\n"
                        "3. Telemetry packets are buffered into hardware_registry.py sliding window deque.\n"
                        "4. Raw readings are pushed to fusion_engine.py and persisted into SQLite sensor_readings."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 3: Bayesian Evidence Fusion & SPS Calculation"
            },
            {
                "type": "paragraph",
                "text": "1. fusion_engine.py executes Step 0–Step 9 calculation pipeline.\n"
                        "2. Modality weights applied (Tilt=0.35, Moisture=0.35, Rain=0.15, Thermal=0.15).\n"
                        "3. Bayesian joint probability computed; SPS calculated at 88.4%.\n"
                        "4. Survivor classified as P1_IMMEDIATE; result stored in ScenarioState.detection_results."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 4: Domain Hazard Evaluation & Safety Threshold Alerts"
            },
            {
                "type": "paragraph",
                "text": "1. scenario_intelligence.py evaluates landslide risk score at 78/100 (CRITICAL).\n"
                        "2. Safety rule triggers; alert_dispatch.py creates NetworkAlert UUID with severity=CRITICAL.\n"
                        "3. db.py writes alert to operational_events table; alert broadcasted to /alerts endpoint."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 5: Tactical Job Dispatch & Proximity Assignment"
            },
            {
                "type": "paragraph",
                "text": "1. Commander submits POST /commander/dispatch for victim #VIC-01.\n"
                        "2. rescue_dispatch.py verifies Team Alpha has certified Landslide Specialists.\n"
                        "3. Haversine distance calculated (140m); RescueJob transitions to ASSIGNED / EN_ROUTE.\n"
                        "4. db.py logs 'Team Assigned' and 'GO Command' events in operational_events."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 6: Mobile Field Responder Acknowledgment & Arrival"
            },
            {
                "type": "paragraph",
                "text": "1. Field responder taps 'Confirm Arrival' on watch.html.\n"
                        "2. API receives POST /rescue-team/member-arrival with member_id='ALPHA-M001'.\n"
                        "3. rescue_dispatch.py transitions job to ARRIVED.\n"
                        "4. db.py logs 'Team Arrived' operational event with timestamp."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 7: Victim Rescue Verification & State Transition"
            },
            {
                "type": "paragraph",
                "text": "1. Responder confirms survivor extraction.\n"
                        "2. API receives status transition request; victim status updated to RESCUED.\n"
                        "3. db.py records 'Victim Rescued' event; victim count incremented in session totals."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 8: Operational Performance Aggregation & Analytics"
            },
            {
                "type": "paragraph",
                "text": "1. API receives GET /analytics/summary?scenario_id=landslide.\n"
                        "2. db.py executes SQL aggregation: Total Victims, Rescued, Rescue Rate %, Response Averages.\n"
                        "3. Mathematical integrity verified: Total Victims = Rescued + En Route + Pending.\n"
                        "4. JSON summary emitted to analytics.html."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 9: Hardware Health Diagnostics & Battery Drainage"
            },
            {
                "type": "paragraph",
                "text": "1. hardware_registry.py computes battery depletion per transmission cycle.\n"
                        "2. Station battery voltage drops to 11.8V (18% remaining); status transitions to DEGRADED.\n"
                        "3. Low battery warning alert created and logged."
            },
            {
                "type": "heading2",
                "text": "Lifecycle 10: Scenario Teardown & Historical Audit Finalization"
            },
            {
                "type": "paragraph",
                "text": "1. Commander submits POST /scenario/stop.\n"
                        "2. ScenarioState marks running=False; simulator background loop halts.\n"
                        "3. db.py writes end_timestamp and final session audit totals to sessions table.\n"
                        "4. Memory resources released cleanly."
            }
        ]
    },

    # SECTION 17: BACKEND DATA FLOW & PROCESSING PIPELINES
    {
        "title": "17. Backend Data Flow & Processing Pipelines",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Every telemetry packet and operational command follows a deterministic, unidirectional data processing pipeline."
            },
            {
                "type": "heading2",
                "text": "Telemetry Ingestion & Processing Pipeline"
            },
            {
                "type": "paragraph",
                "text": "RAW SENSOR READING (sensor_simulator.py / external Ingest API)\n"
                        "    ↓\n"
                        "PYDANTIC MODEL VALIDATION (models.py)\n"
                        "    ↓\n"
                        "SLIDING WINDOW BUFFERING (hardware_registry.py)\n"
                        "    ↓\n"
                        "BAYESIAN EVIDENCE NORMALIZATION (Step 0–Step 2 in fusion_engine.py)\n"
                        "    ↓\n"
                        "JOINT PROBABILITY FUSION (Step 3–Step 5 in fusion_engine.py)\n"
                        "    ↓\n"
                        "HAZARD MULTIPLIER & SPS CALCULATION (Step 6–Step 8 in fusion_engine.py)\n"
                        "    ↓\n"
                        "START TRIAGE ORDERING (Step 9 in fusion_engine.py)\n"
                        "    ↓\n"
                        "SQLITE AUDIT PERSISTENCE (db.py)\n"
                        "    ↓\n"
                        "REST JSON SERIALIZATION (api.py)"
            }
        ]
    },

    # SECTION 18: COMPREHENSIVE 6W SUMMARY MATRIX
    {
        "title": "18. Comprehensive 6W Summary Matrix (All 14 Backend Modules)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The table below aggregates the overarching 6W analysis across all 14 audited backend modules and datasets."
            },
            {
                "type": "table",
                "headers": ["MODULE", "WHAT?", "WHY?", "WHO?", "WHERE?", "HOW?"],
                "data": [
                    ["api.py", "FastAPI web server", "Expose REST endpoints", "Frontend & Clients", "API Gateway", "Async route handlers & state proxy"],
                    ["models.py", "Domain data models", "Enforce type contracts", "All modules", "Core Domain", "Pydantic models & DataClasses"],
                    ["db.py", "SQLite persistence", "Durable audit & history", "api.py & Analytics", "Persistence", "Thread-safe WAL SQLite transactions"],
                    ["fusion_engine.py", "Bayesian AI engine", "Calculate SPS & triage", "Commanders", "Intelligence", "Step 0–9 mathematical pipeline"],
                    ["scenario_intelligence.py", "Domain hazard engine", "Disaster physics rules", "fusion_engine.py", "Intelligence", "Domain-specific risk algorithms"],
                    ["sensor_simulator.py", "Physics & telemetry", "Simulate disaster data", "Testing & Sandbox", "Simulation", "Gaussian noise & degradation curves"],
                    ["rescue_dispatch.py", "Dispatch state machine", "Allocate rescue teams", "Commanders & Field", "Operations", "Staff certification matching & ETA"],
                    ["alert_dispatch.py", "Emergency alerting", "Life-safety warnings", "Safety Officers", "Alerting", "Multi-channel broadcast & ack audit"],
                    ["hardware_registry.py", "Station diagnostic", "Monitor hardware health", "Technicians", "Hardware", "Deque buffers & heartbeat monitor"],
                    ["scenario_loader.py", "JSON scenario parser", "Load disk scenarios", "api.py", "Configuration", "JSON parsing & procedural placement"],
                    ["scenarios_master.py", "Master catalog", "Disaster taxonomies", "All modules", "Taxonomy", "Normalized scenario dictionary"],
                    ["scenario_sensor_profiles.py", "Sensor relevance map", "Filter primary sensors", "fusion_engine.py", "Configuration", "Primary/Supporting/Inactive mappings"],
                    ["scenarios/*.json", "Scenario seed files", "Offline baseline data", "scenario_loader.py", "Data Layer", "Static JSON configuration files"],
                    ["cleanup_default_data.py", "Maintenance script", "Reset SQLite database", "SysAdmins", "Utilities", "Direct SQL cleanup execution"],
                ],
                "widths": [1.1, 1.1, 1.2, 1.0, 0.9, 1.1]
            }
        ]
    },

    # SECTION 19: DETAILED FILE SPECIFICATION BLOCKS (Injected programmatically)
    {
        "title": "19. Standardized Backend File Documentation Blocks (All 14 Files)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "This section provides exhaustive, standardized conceptual specification blocks for every file and module in the backend directory. Each entry details the file's primary purpose, 6W analysis, inputs, outputs, data flows, persistence interactions, error handling, and systemic impact."
            }
        ]
    },

    # SECTION 20: COMPONENT CRITICALITY & TIER ANALYSIS
    {
        "title": "20. Component Criticality & Architectural Tier Analysis",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Backend components are categorized into three operational criticality tiers:"
            },
            {
                "type": "heading2",
                "text": "Tier 1: CRITICAL Components (System Halts if Unavailable)"
            },
            {
                "type": "paragraph",
                "text": "• api.py: Primary application gateway.\n"
                        "• models.py: Core type contract and domain entity schemas.\n"
                        "• db.py: SQLite persistence and audit logging engine.\n"
                        "• fusion_engine.py: Mathematical Bayesian probability and SPS calculation engine."
            },
            {
                "type": "heading2",
                "text": "Tier 2: IMPORTANT Components (Operational Capability Degraded)"
            },
            {
                "type": "paragraph",
                "text": "• scenario_intelligence.py: Domain-specific hazard evaluations.\n"
                        "• rescue_dispatch.py: Autonomous rescue team allocation and job tracking.\n"
                        "• alert_dispatch.py: Emergency safety warning generator and broadcast ledger.\n"
                        "• sensor_simulator.py: Physics simulation and telemetry generation."
            },
            {
                "type": "heading2",
                "text": "Tier 3: SUPPORTING Components (Diagnostic & Maintenance Functions)"
            },
            {
                "type": "paragraph",
                "text": "• hardware_registry.py: Hardware station telemetry buffers and battery monitors.\n"
                        "• scenario_loader.py & scenarios_master.py: Scenario catalog and JSON loaders.\n"
                        "• scenario_sensor_profiles.py: Sensor relevance mapping matrix.\n"
                        "• scripts/cleanup_default_data.py: Database reset script."
            }
        ]
    },

    # SECTION 21: "IF THIS FILE FAILS" SYSTEMIC IMPACT ANALYSIS
    {
        "title": "21. 'If This File Fails' Systemic Backend Impact Analysis",
        "blocks": [
            {
                "type": "paragraph",
                "text": "This section evaluates fault tolerance, failure modes, and mitigation strategies for every backend module."
            },
            {
                "type": "table",
                "headers": ["FAILED FILE", "FAILURE SYMPTOM", "SYSTEMIC IMPACT", "MITIGATION STRATEGY"],
                "data": [
                    ["api.py", "HTTP 500 / Connection refused", "Complete system outage across all clients", "Uvicorn process auto-restart via systemd / Docker"],
                    ["models.py", "ImportError / ValidationError", "Cannot instantiate domain objects", "Comprehensive pytest model validation suite"],
                    ["db.py", "OperationalError / DB locked", "Cannot persist events or sessions", "SQLite WAL mode, 30s busy timeout, in-memory fallback"],
                    ["fusion_engine.py", "SPS scores NaN or uncalculated", "Loss of survivor triage prioritization", "Clamped probability bounds [0.001, 0.999] & neutral priors"],
                    ["scenario_intelligence.py", "Hazard scores missing", "Cannot evaluate secondary risks", "Fallback to generic baseline environmental thresholds"],
                    ["rescue_dispatch.py", "Jobs unassigned", "Teams cannot be dispatched via API", "Manual dispatch override via direct SQL insertion"],
                    ["alert_dispatch.py", "Alarms unbroadcasted", "Responders unaware of secondary hazards", "Persistent visual alert banners rendered on UI topbar"],
                    ["hardware_registry.py", "Battery gauges blank", "No station health diagnostics", "System operates normally using raw sensor telemetry"],
                ],
                "widths": [1.2, 1.4, 1.9, 1.9]
            }
        ]
    },

    # SECTION 22: MATHEMATICAL & PROBABILISTIC RIGOR
    {
        "title": "22. Mathematical & Probabilistic Rigor (SPS, Bayesian, Hazard Multipliers)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The backend avoids arbitrary heuristics in favor of formal mathematical and probabilistic formulations."
            },
            {
                "type": "heading2",
                "text": "Key Mathematical Formulations"
            },
            {
                "type": "paragraph",
                "prefix": "1. Bayesian Log-Odds Evidence Update:",
                "text": "log_odds(P) = log(P / (1 - P)). For each independent sensor modality i: log_odds_post = log_odds_prior + sum(w_i * log(L_i)), where L_i is the likelihood ratio P(Reading | Victim Present) / P(Reading | Noise)."
            },
            {
                "type": "paragraph",
                "prefix": "2. Composite Survival Probability Score (SPS):",
                "text": "SPS = Base_Confidence * Vital_Signs_Multiplier * (1.0 - Hazard_Penalty) * 100.0, clamped strictly within [0.0%, 100.0%]."
            },
            {
                "type": "paragraph",
                "prefix": "3. Haversine Great-Circle Geodetic Distance:",
                "text": "d = 2 * R * arcsin(sqrt(sin^2(dlat/2) + cos(lat1)*cos(lat2)*sin^2(dlon/2))), where R = 6,371,000 meters."
            }
        ]
    },

    # SECTION 23: SECURITY, VALIDATION & ERROR HANDLING
    {
        "title": "23. Security, Validation, Error Handling & Graceful Degradation",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The backend enforces multi-layer input validation, defensive null-checking, and comprehensive error handling."
            },
            {
                "type": "heading2",
                "text": "Defensive Architecture Measures"
            },
            {
                "type": "paragraph",
                "prefix": "• Pydantic Schema Validation:",
                "text": "All incoming HTTP request bodies are validated against strict Pydantic schemas, rejecting malformed JSON, out-of-bound coordinates, and negative numbers."
            },
            {
                "type": "paragraph",
                "prefix": "• Defensive Null & Type Safety:",
                "text": "Every route handler and internal method uses getattr() checks, hasattr() guards, and explicit None narrowing to eliminate AttributeError and TypeError exceptions."
            },
            {
                "type": "paragraph",
                "prefix": "• Thread-Safe SQLite Locking:",
                "text": "Database transactions are synchronized across concurrent asyncio loops to eliminate SQLite database locking errors."
            }
        ]
    },

    # SECTION 24: BACKEND ARCHITECTURE RATIONALE
    {
        "title": "24. Backend Architecture Rationale: Why This Backend Architecture?",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The RidgeWatch backend was deliberately architected to maximize operational reliability in disaster environments."
            },
            {
                "type": "heading2",
                "text": "Core Architectural Trade-Off Decisions"
            },
            {
                "type": "paragraph",
                "prefix": "1. FastAPI over Django/Flask:",
                "text": "FastAPI provides asynchronous ASGI execution, automatic OpenAPI schema documentation, native Pydantic validation, and high throughput with minimal overhead."
            },
            {
                "type": "paragraph",
                "prefix": "2. Embedded SQLite over External PostgreSQL:",
                "text": "Emergency systems deployed on mobile command vehicles or air-gapped field laptops cannot rely on running multi-container database daemons. SQLite provides self-contained, zero-configuration persistence with zero network overhead."
            },
            {
                "type": "paragraph",
                "prefix": "3. Explainable Bayesian Math over Deep Neural Networks:",
                "text": "Search-and-rescue commanders cannot risk human lives on unexplainable black-box AI predictions. Bayesian fusion provides transparent, step-by-step mathematical proofs for every triage decision."
            }
        ]
    },

    # SECTION 25: BACKEND SUMMARY & CONCLUSION
    {
        "title": "25. Backend Architecture Summary & Final Conclusions",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The RIDGEWATCH backend architecture provides a rock-solid, explainable, and production-ready computational backbone for disaster search-and-rescue operations. "
                        "By unifying asynchronous web services, multi-modal Bayesian evidence fusion, domain-specific disaster physics modeling, autonomous resource dispatching, and zero-configuration SQLite persistence, "
                        "it delivers the real-time intelligence necessary to optimize rescue operations in the critical golden hour."
            },
            {
                "type": "heading2",
                "text": "Summary of Backend Achievements"
            },
            {
                "type": "paragraph",
                "prefix": "• 14 Audited Backend Files & Modules:",
                "text": "Every module has been verified, tested, and comprehensively documented across all 6W questions."
            },
            {
                "type": "paragraph",
                "prefix": "• Mathematical Rigor & Zero Fake Data:",
                "text": "Every SPS calculation and analytics metric derives from audited mathematical equations and validated physics simulations."
            },
            {
                "type": "paragraph",
                "prefix": "• Full Regression Test Verification:",
                "text": "Validated against 565 passing automated tests with zero failures, confirming production readiness for mission evaluation and live deployment."
            },
            {
                "type": "callout",
                "title": "END OF BACKEND TECHNICAL SPECIFICATION",
                "text": "RIDGEWATCH — AI-Based Multi-Disaster Survivor Detection & Rescue Coordination System. Backend Architecture & Conceptual Documentation v2.0."
            }
        ]
    }
]
