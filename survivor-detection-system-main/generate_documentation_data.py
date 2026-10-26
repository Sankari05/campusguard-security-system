"""
generate_documentation_data.py
------------------------------
Contains the structured data, 6W file analysis, and chapter contents for:
RIDGEWATCH Frontend Architecture & File-by-File Conceptual Documentation.
"""

FRONTEND_FILES_DATA = [
    # --- HTML FILES (25) ---
    {
        "name": "index.html",
        "type": "HTML (Core Dashboard View)",
        "purpose": "Primary operational dashboard presenting high-level disaster telemetry, scenario quick-start launcher, live mini-map, survivor counts, and active alert banners.",
        "what": "The executive dashboard and primary entry portal for operational commanders and search-and-rescue teams.",
        "why": "Provides immediate situational awareness in the critical first minutes of a disaster without requiring navigation through deep technical sub-pages.",
        "who": "Incident Commander, Search & Rescue Operators, Field Team Leads.",
        "where": "Root level / main landing page of the RidgeWatch web portal.",
        "when": "Loaded initially upon accessing the system or clicking the Dashboard link in the master sidebar.",
        "how": "Renders semantic KPI metric cards, scenario trigger buttons, interactive site map container, and live telemetry badges driven by dashboard.js.",
        "inputs": "Live operation state from /operations, active victims, sensor telemetry summary, scenario catalog.",
        "outputs": "Rendered operational overview, quick-action dispatch buttons, scenario launch triggers.",
        "ui_responsibility": "Presents 4 core KPI tiles, scenario selection matrix, live leaflet-styled map canvas, active disaster status banner, and alert notifications.",
        "dependencies": "css/style.css, js/config.js, js/dashboard.js",
        "if_missing": "The system loses its primary landing page and executive dashboard, forcing users to access sub-modules directly."
    },
    {
        "name": "visual.html",
        "type": "HTML (Interactive Multi-Dimensional Visualizer)",
        "purpose": "Provides the comprehensive 2D architecture schematic, 3D hardware physical digital twin, and 4D temporal simulation canvas.",
        "what": "Hardware and system digital twin visualizer rendering real-time 3D models of drone stations, sensor arrays, and mesh nodes.",
        "why": "Enables engineers, commanders, and technicians to inspect physical device arrangements, inspect component health in 3D, and track live sensor telemetry particles.",
        "who": "System Engineers, Hardware Technicians, Incident Commanders.",
        "where": "Visual 3D navigation module accessible via sidebar link 'Visual 3D'.",
        "when": "Loaded when deep physical spatial analysis, hardware debugging, or 4D time-series progression is required.",
        "how": "Hosts WebGL canvas containers for Three.js 3D rendering, component inspector sidebar, telemetry overlay HUD, and camera control toolbar.",
        "inputs": "Hardware telemetry (/hardware/summary, /hardware/telemetry/timeseries), live scenario sensor profiles, user camera gestures.",
        "outputs": "Interactive 3D viewport, 2D architectural schematic, 4D simulation playback, component health inspections.",
        "ui_responsibility": "Renders Three.js canvas, layer toggle pills (2D / 3D / 4D), hardware component inspector drawer, and environment particle HUD.",
        "dependencies": "css/style.css, js/config.js, js/visual.js",
        "if_missing": "The physical digital twin and 3D sensor visualization capabilities become completely unavailable."
    },
    {
        "name": "logic.html",
        "type": "HTML (AI Decision Center & Explainability)",
        "purpose": "Operational AI Decision Center visualizing the Step 0–Step 9 multi-sensor Bayesian fusion, SPS survival scoring, and triage explainability.",
        "what": "The cognitive intelligence hub of RidgeWatch showing exactly how and why AI decisions and triage classifications are derived.",
        "why": "Provides operational commanders with transparent, explainable AI reasoning rather than a black-box recommendation.",
        "who": "Mission Commander, Triage Officers, System Evaluators, Hackathon Judges.",
        "where": "Logical AI Decision module accessed via the sidebar navigation.",
        "when": "Used during active operations to inspect evidence weighting, hazard multipliers, and survivor prioritization math.",
        "how": "Displays Current Decision banner, Evidence Breakdown matrix, Sensor Activation grid, Step 0–Step 9 calculation timeline, and Recommended Actions.",
        "inputs": "Scenario intelligence (/scenario/intelligence), fusion results (/logic/step-calculations), sensor weights, active alerts.",
        "outputs": "Visual mathematical breakdown, sensor weighting charts, priority triage badges, explainability narratives.",
        "ui_responsibility": "Renders Level 1 Current Decision, Level 2 Sensor Evidence, Level 3 Calculation Steps, and Level 4 Action Guidance.",
        "dependencies": "css/style.css, js/config.js, js/logic.js",
        "if_missing": "Commanders lose all explainability into AI decisions, triage rankings, and multi-sensor fusion math."
    },
    {
        "name": "commander.html",
        "type": "HTML (Tactical Incident Command Center)",
        "purpose": "Tactical mission control dashboard featuring the dynamic 2D operational site map, job assignment workflow, and rescue team tracking.",
        "what": "The operational theater command interface for coordinating multi-team rescue missions and assigning jobs.",
        "why": "Centralizes victim prioritization, job dispatch, team movement tracking, and geodetic site coordination in a single view.",
        "who": "Incident Commander, Dispatch Coordinator.",
        "where": "Commander module accessed via sidebar link 'Commander'.",
        "when": "Loaded continuously during active search-and-rescue operations.",
        "how": "Combines dynamic 2D site map with collision-avoidance label engine, job assignment drawer, staff eligibility table, and live alert feed.",
        "inputs": "Commander overview API (/commander/overview), live victims, rescue teams, active jobs, member arrivals.",
        "outputs": "Dispatched rescue jobs, real-time map clustering, verified member arrival alerts, tactical status ledger.",
        "ui_responsibility": "Renders SVG tactical map, interactive legend toggles, job queue drawer, victim cards, and member assignment modals.",
        "dependencies": "css/style.css, js/config.js, js/commander.js",
        "if_missing": "Commanders cannot assign rescue jobs, visualize spatial positions on the tactical map, or track team arrivals."
    },
    {
        "name": "watch.html",
        "type": "HTML (Field Responder Smartwatch / Mobile View)",
        "purpose": "Ultra-compact, high-contrast mobile interface optimized for field rescue workers, smartwatch displays, and wearable devices.",
        "what": "Mobile field triage notification and assignment client for deployed rescue team members.",
        "why": "Field responders operating in harsh environments need glanceable victim coordinates, vital signs, and safety alerts without clutter.",
        "who": "Field Rescue Workers, Paramedics, Search Dogs Handlers.",
        "where": "Wearable/Mobile module accessed via sidebar link 'Watch' or mobile browser.",
        "when": "Used on ruggedized field tablets, smartphones, and smartwatch browsers during active search operations.",
        "how": "Renders high-contrast cards showing current assigned victim, GPS coordinates, distance/ETA, and acknowledge buttons.",
        "inputs": "Active alerts (/alerts), member assignments (/rescue-team/members-status), victim vitals.",
        "outputs": "Field acknowledgment pulses, status transitions (En Route -> Arrived -> Rescued).",
        "ui_responsibility": "Displays large-format touch buttons, vital signs telemetry, step-by-step navigation compass, and vibration/audio alert cards.",
        "dependencies": "css/style.css, js/config.js, js/watch.js",
        "if_missing": "Field personnel lose their dedicated mobile/wearable interface for receiving tactical dispatches."
    },
    {
        "name": "alerts.html",
        "type": "HTML (Emergency Hazard Alert Center)",
        "purpose": "Dedicated incident alert ledger and real-time audio-visual emergency hazard notification center.",
        "what": "Centralized hazard alert ledger tracking active, acknowledged, and resolved multi-hazard warnings.",
        "why": "Ensures critical life-safety warnings (e.g. secondary landslide, toxic gas cloud, structural collapse) are never missed.",
        "who": "Incident Commander, Safety Officer, Operations Staff.",
        "where": "Alerts module accessed via sidebar link 'Alerts'.",
        "when": "Monitored constantly during disasters; pops up high-priority audio-visual banners on critical events.",
        "how": "Polls active network alerts, groups by severity (CRITICAL, HIGH, WARNING, INFO), and provides acknowledgment actions.",
        "inputs": "Active alerts ledger (/alerts), network alerts from db, telemetry threshold breaches.",
        "outputs": "Audited alert acknowledgments, severity filter changes, historical alert CSV exports.",
        "ui_responsibility": "Renders severity filter tabs, active alert cards with countdown timers, audio alarm toggle, and resolution modals.",
        "dependencies": "css/style.css, js/config.js, js/alerts.js",
        "if_missing": "The system lacks a dedicated center for auditing, filtering, and acknowledging safety-critical alerts."
    },
    {
        "name": "analytics.html",
        "type": "HTML (Rescue Performance & Intelligence Dashboard)",
        "purpose": "Comprehensive operational performance dashboard analyzing rescue success rates, response times, hazard matrices, and team effectiveness.",
        "what": "The retrospective and operational intelligence center analyzing trends across single-session and historical disaster operations.",
        "why": "Commanders and stakeholders need mathematically verified insights into rescue speed, survivor survival rates, and station uptime.",
        "who": "Operations Commander, Disaster Management Directors, Performance Analysts.",
        "where": "Analytics module accessed via sidebar link 'Analytics'.",
        "when": "Used post-operation or during multi-day disaster campaigns to audit efficiency and sensor reliability.",
        "how": "Integrates global scope filtering (Live, 24h, 7d, 30d, All-Time), interactive SVG trend charts, scenario donuts, and team rankings.",
        "inputs": "Analytics summary (/analytics/summary), session records, sensor histories, team arrivals.",
        "outputs": "Performance trend visualizations, response time averages, CSV audit exports, station uptime ratings.",
        "ui_responsibility": "Renders Hero Operational Picture, 5 Scope KPI cards, SVG trend charts, hazard matrix, sessions table, and system health strip.",
        "dependencies": "css/style.css, js/config.js, js/analytics.js",
        "if_missing": "Commanders lose all operational reporting, historical session audits, and performance trend visualizations."
    },
    {
        "name": "scenarios.html",
        "type": "HTML (Disaster Scenario Catalog)",
        "purpose": "Master catalog of pre-configured disaster scenarios (Landslide, Earthquake, Flood, Building Collapse, Avalanche, Wildfire, Chemical Leak, etc.).",
        "what": "Scenario selection and initiation interface allowing operators to launch multi-hazard simulations.",
        "why": "Provides a quick, standardized catalog for training drills, capability demonstrations, and operational benchmarking.",
        "who": "Operators, Evaluators, Instructors.",
        "where": "Scenarios module accessed via sidebar link 'Scenarios'.",
        "when": "Loaded prior to initiating a new disaster drill or operational simulation.",
        "how": "Displays scenario cards with geographic origin, active hazard profile, victim count, and one-click launch buttons.",
        "inputs": "Scenario catalog (/scenarios), scenario sensor profiles.",
        "outputs": "Disaster scenario launch requests (/scenario/start).",
        "ui_responsibility": "Renders grid of disaster cards with badges indicating disaster category, complexity, and active sensor types.",
        "dependencies": "css/style.css, js/config.js, js/scenarios.js",
        "if_missing": "Users cannot visually browse or launch pre-configured disaster scenarios from the catalog."
    },
    {
        "name": "victims.html",
        "type": "HTML (Survivor Directory & Vital Signs Roster)",
        "purpose": "Detailed survivor roster displaying detected victims, triage priorities (HIGH, MEDIUM, LOW), GPS coordinates, and biometric telemetry.",
        "what": "Survivor tracking and health intelligence directory.",
        "why": "Allows triage officers and medical personnel to inspect specific victim vital signs, burial depths, and triage rankings.",
        "who": "Medical Officers, Triage Personnel, Rescue Coordinators.",
        "where": "Victims module accessed via sidebar link 'Victims'.",
        "when": "Used whenever detailed medical or vital signs information on a detected survivor is needed.",
        "how": "Fetches active victim fusion records, renders health status cards, priority filters, and individual victim modal drawers.",
        "inputs": "Victims endpoint (/victims or /operations/{op_id}/victims), fusion triage scores.",
        "outputs": "Filtered victim lists, medical priority views, coordinate copy actions.",
        "ui_responsibility": "Renders survivor table with SPS progress bars, heart rate / SpO2 badges, triage class tags, and triage priority filters.",
        "dependencies": "css/style.css, js/config.js, js/victims.js",
        "if_missing": "Medical responders lose the dedicated survivor roster view and individual vital sign inspection tools."
    },
    {
        "name": "teams.html",
        "type": "HTML (Rescue Teams Roster & Deployment Status)",
        "purpose": "Rescue team management and deployment directory showing registered units (Alpha, Bravo, Charlie, etc.) and active member assignments.",
        "what": "Rescue team operational directory and roster browser.",
        "why": "Provides visibility into available, en route, and deployed search-and-rescue units across operational sectors.",
        "who": "Logistics Officers, Incident Commanders.",
        "where": "Teams module accessed via sidebar link 'Teams'.",
        "when": "Used during deployment planning and team availability tracking.",
        "how": "Queries registered teams and member states, rendering team status cards, member callsigns, and equipment capabilities.",
        "inputs": "Registered teams (/admin/teams), live member states (/rescue-team/members-status).",
        "outputs": "Team deployment summaries, availability rosters, direct navigation to Commander dispatch.",
        "ui_responsibility": "Renders team cards with status badges (Available, Deployed, En Route), member lists, and capability tags.",
        "dependencies": "css/style.css, js/config.js, js/teams.js",
        "if_missing": "Operators cannot view team compositions, member assignments, or team availability outside of the commander map."
    },
    {
        "name": "hardware.html",
        "type": "HTML (Sensor & Hardware Diagnostic Center)",
        "purpose": "Station-by-station hardware telemetry monitor, sensor registry browser, and communication diagnostic dashboard.",
        "what": "Hardware and sensor station health intelligence interface.",
        "why": "Ensures physical sensing stations (Inclinometers, Rain Gauges, Thermal Cameras, Seismic Nodes) are online, calibrated, and transmitting.",
        "who": "Hardware Technicians, Systems Engineers.",
        "where": "Hardware module accessed via sidebar link 'Hardware'.",
        "when": "Used to monitor sensor battery levels, signal strength, packet dropouts, and station health.",
        "how": "Polls hardware registry (/hardware/summary, /hardware/registry), renders live gauge meters, status badges, and sensor details.",
        "inputs": "Hardware telemetry summaries, sensor battery voltages, calibration statuses.",
        "outputs": "Sensor diagnostic reports, hardware state filters, station restart triggers.",
        "ui_responsibility": "Renders station health grid, battery meters, live sensor value cards, and diagnostic status pills.",
        "dependencies": "css/style.css, js/config.js, js/hardware.js",
        "if_missing": "Technicians lose visibility into sensor node battery levels, communication health, and hardware telemetry."
    },
    {
        "name": "testing.html",
        "type": "HTML (Interactive Testing Sandbox & Simulator)",
        "purpose": "Comprehensive developer and evaluator testing console for injecting synthetic sensor telemetry, simulating dropouts, and advancing scenario cycles.",
        "what": "The multi-scenario simulation sandbox and test execution console.",
        "why": "Enables exhaustive validation of AI logic, threshold alerts, and degradation modes without physical disaster conditions.",
        "who": "Software Developers, QA Engineers, Hackathon Judges, Evaluators.",
        "where": "Testing module accessed via sidebar link 'Testing'.",
        "when": "Used during testing, demonstrations, edge-case validation, and automated test runs.",
        "how": "Hosts interactive simulation controls (Play, Pause, Step, Fast-Forward), telemetry injection sliders, and scenario ledger tables.",
        "inputs": "Simulation controls, synthetic telemetry payloads, scenario activation requests.",
        "outputs": "Manual telemetry injections, cycle step commands, scenario ledger updates.",
        "ui_responsibility": "Renders scenario ledger tabs, simulator control toolbar, telemetry slider controls, and real-time response log window.",
        "dependencies": "css/style.css, js/config.js, js/testing-common.js, js/testing.js",
        "if_missing": "Developers and evaluators cannot interactively inject test sensor values or step through simulation cycles."
    },
    {
        "name": "testing-scenarios.html",
        "type": "HTML (Testing Console - Scenario Ledger)",
        "purpose": "Dedicated scenario ledger within the Testing Console for viewing, activating, and toggling disaster scenarios.",
        "what": "Testing sub-page managing the active scenario ledger.",
        "why": "Allows testers to toggle scenarios between Active and Inactive states and launch custom configurations.",
        "who": "Testers, System Administrators.",
        "where": "Testing module sub-navigation.",
        "when": "Used to configure which disaster scenarios are offered across the system.",
        "how": "Displays scenario ledger table with status pills (Active/Inactive), victim counts, and toggle action buttons.",
        "inputs": "Scenario ledger (/admin/scenarios).",
        "outputs": "Scenario activation/deactivation API calls.",
        "ui_responsibility": "Renders tabular scenario ledger with search, category filtering, and action buttons.",
        "dependencies": "css/style.css, js/config.js, js/testing-common.js, js/testing-scenarios.js",
        "if_missing": "Testers cannot manage scenario ledger statuses or toggle scenario availability."
    },
    {
        "name": "testing-persons.html",
        "type": "HTML (Testing Console - Personnel Directory)",
        "purpose": "Personnel registry within the Testing Console for viewing certified disaster response personnel, skill matrices, and certifications.",
        "what": "Testing sub-page displaying the registered personnel database.",
        "why": "Enables validation of role eligibility algorithms (e.g. verifying only Avalanche-certified personnel can be assigned to winter missions).",
        "who": "Testers, Personnel Coordinators.",
        "where": "Testing module sub-navigation.",
        "when": "Used to review registered staff qualifications and readiness.",
        "how": "Renders searchable personnel table with badges for certified disaster categories, medical qualifications, and team associations.",
        "inputs": "Personnel records (/admin/persons).",
        "outputs": "Personnel list rendering, qualification filters, direct link to Add Person form.",
        "ui_responsibility": "Renders personnel table with skill matrix tags, contact info, and status indicators.",
        "dependencies": "css/style.css, js/config.js, js/testing-common.js, js/testing-persons.js",
        "if_missing": "Testers cannot inspect responder skill matrices or verify role certification records."
    },
    {
        "name": "testing-teams.html",
        "type": "HTML (Testing Console - Teams Directory)",
        "purpose": "Team management interface within the Testing Console for viewing configured rescue units and their assigned member rosters.",
        "what": "Testing sub-page managing team definitions and member rosters.",
        "why": "Allows testers to verify team compositions, member roles, and callsign allocations.",
        "who": "Testers, Admin Staff.",
        "where": "Testing module sub-navigation.",
        "when": "Used to inspect team structures and create new tactical units.",
        "how": "Displays team cards with member rosters, capabilities, base coordinates, and action buttons.",
        "inputs": "Teams catalog (/admin/teams), members directory.",
        "outputs": "Team overview, deletion/editing triggers, direct link to Add Team form.",
        "ui_responsibility": "Renders team cards with member avatar pills, base location coordinates, and operational role tags.",
        "dependencies": "css/style.css, js/config.js, js/testing-common.js, js/testing-teams.js",
        "if_missing": "Testers cannot manage team records or inspect member allocations in the testing portal."
    },
    {
        "name": "testing-add-scenario.html",
        "type": "HTML (Testing Console - Add Custom Scenario Form)",
        "purpose": "Form for constructing and registering custom multi-disaster scenarios with custom victim coordinates, hazard types, and site labels.",
        "what": "Interactive scenario authoring form.",
        "why": "Allows creation of arbitrary disaster scenarios for custom drills or localized geography without editing JSON files.",
        "who": "Instructors, Scenario Authors, Evaluators.",
        "where": "Testing module sub-navigation.",
        "when": "Used when a new custom scenario needs to be tested or demonstrated.",
        "how": "Gathers scenario metadata, victim count, site coordinates, and hazard type; submits structured payload to API.",
        "inputs": "User form input (Scenario Name, Category, Latitude, Longitude, Victim Count, Hazard Severity).",
        "outputs": "Registered custom scenario in database and immediate redirection to scenario ledger.",
        "ui_responsibility": "Renders validated form inputs, coordinate pickers, hazard dropdowns, and submission feedback.",
        "dependencies": "css/style.css, js/config.js, js/testing-common.js, js/testing-add-scenario.js",
        "if_missing": "Users cannot create new custom scenarios through the web interface."
    },
    {
        "name": "testing-add-person.html",
        "type": "HTML (Testing Console - Add Person Form)",
        "purpose": "Comprehensive registration form for enrolling rescue responders with specific disaster skill certifications, roles, and callsigns.",
        "what": "Personnel enrollment and skill matrix assignment form.",
        "why": "Ensures new personnel have validated qualifications (e.g. Urban USAR, Canine Search, High-Angle Rope Rescue, Hazmat).",
        "who": "Personnel Administrators, Training Coordinators.",
        "where": "Testing module sub-navigation.",
        "when": "Used during initial team onboarding or responder qualification updates.",
        "how": "Collects personal details, operational role, and multi-select certified disaster categories; validates and posts to /admin/person/create.",
        "inputs": "User input (Name, Role, Callsign, Certification Checkboxes).",
        "outputs": "Registered responder in personnel database.",
        "ui_responsibility": "Renders categorized checkbox grid for disaster skills, role selectors, and input validation feedback.",
        "dependencies": "css/style.css, js/config.js, js/testing-common.js, js/testing-add-person.js",
        "if_missing": "New responders cannot be registered with certified skill matrices through the UI."
    },
    {
        "name": "testing-add-team.html",
        "type": "HTML (Testing Console - Add Team Form)",
        "purpose": "Rescue team assembly form allowing creation of tactical units and assignment of certified, available personnel.",
        "what": "Team formation and member assignment form.",
        "why": "Ensures rescue teams are created with adequate staffing and appropriate base coordinates.",
        "who": "Incident Commanders, Admin Staff.",
        "where": "Testing module sub-navigation.",
        "when": "Used to assemble new rescue teams prior to operational deployment.",
        "how": "Fetches registered unassigned personnel, allows selection of team lead and members, and creates team via /admin/team/create.",
        "inputs": "Team Name, Team Type, Base Coordinates, Selected Member IDs.",
        "outputs": "Assembled rescue team ready for operational dispatch.",
        "ui_responsibility": "Renders team metadata fields, member selection picker, and deployment readiness summary.",
        "dependencies": "css/style.css, js/config.js, js/testing-common.js, js/testing-add-team.js",
        "if_missing": "New rescue teams cannot be assembled or assigned members via the UI."
    },
    # --- ADMIN COMPATIBILITY ALIASES (7 HTML files) ---
    {
        "name": "admin.html",
        "type": "HTML (Compatibility Alias / Redirect)",
        "purpose": "Instant client-side redirect to testing.html providing backwards-compatible navigation for legacy admin bookmarks.",
        "what": "Administrative redirect gateway.",
        "why": "Maintains seamless routing compatibility for users accessing the legacy /admin.html URL.",
        "who": "System Users, Legacy Bookmarks.",
        "where": "Root level / administrative alias.",
        "when": "Triggered when accessing admin.html directly.",
        "how": "Executes immediate window.location.replace('testing.html') and meta-refresh tag.",
        "inputs": "URL navigation request.",
        "outputs": "Client redirection to testing.html.",
        "ui_responsibility": "Displays minimal fallback redirect text if JavaScript is disabled.",
        "dependencies": "None (Self-contained redirect)",
        "if_missing": "Direct requests to admin.html would result in a 404 error."
    },
    {
        "name": "admin-scenarios.html",
        "type": "HTML (Compatibility Alias / Redirect)",
        "purpose": "Instant client-side redirect to testing-scenarios.html.",
        "what": "Scenario ledger alias gateway.",
        "why": "Ensures legacy admin scenario links route cleanly to testing-scenarios.html.",
        "who": "System Users.",
        "where": "Administrative alias.",
        "when": "Triggered when accessing admin-scenarios.html.",
        "how": "Executes window.location.replace('testing-scenarios.html').",
        "inputs": "URL navigation request.",
        "outputs": "Redirection to testing-scenarios.html.",
        "ui_responsibility": "Displays fallback redirect link.",
        "dependencies": "None",
        "if_missing": "Legacy bookmarks to admin-scenarios.html would fail."
    },
    {
        "name": "admin-persons.html",
        "type": "HTML (Compatibility Alias / Redirect)",
        "purpose": "Instant client-side redirect to testing-persons.html.",
        "what": "Personnel directory alias gateway.",
        "why": "Ensures legacy admin personnel links route cleanly to testing-persons.html.",
        "who": "System Users.",
        "where": "Administrative alias.",
        "when": "Triggered when accessing admin-persons.html.",
        "how": "Executes window.location.replace('testing-persons.html').",
        "inputs": "URL navigation request.",
        "outputs": "Redirection to testing-persons.html.",
        "ui_responsibility": "Displays fallback redirect link.",
        "dependencies": "None",
        "if_missing": "Legacy bookmarks to admin-persons.html would fail."
    },
    {
        "name": "admin-teams.html",
        "type": "HTML (Compatibility Alias / Redirect)",
        "purpose": "Instant client-side redirect to testing-teams.html.",
        "what": "Teams directory alias gateway.",
        "why": "Ensures legacy admin team links route cleanly to testing-teams.html.",
        "who": "System Users.",
        "where": "Administrative alias.",
        "when": "Triggered when accessing admin-teams.html.",
        "how": "Executes window.location.replace('testing-teams.html').",
        "inputs": "URL navigation request.",
        "outputs": "Redirection to testing-teams.html.",
        "ui_responsibility": "Displays fallback redirect link.",
        "dependencies": "None",
        "if_missing": "Legacy bookmarks to admin-teams.html would fail."
    },
    {
        "name": "admin-add-scenario.html",
        "type": "HTML (Compatibility Alias / Redirect)",
        "purpose": "Instant client-side redirect to testing-add-scenario.html.",
        "what": "Scenario builder alias gateway.",
        "why": "Ensures legacy add-scenario links route cleanly to testing-add-scenario.html.",
        "who": "System Users.",
        "where": "Administrative alias.",
        "when": "Triggered when accessing admin-add-scenario.html.",
        "how": "Executes window.location.replace('testing-add-scenario.html').",
        "inputs": "URL navigation request.",
        "outputs": "Redirection to testing-add-scenario.html.",
        "ui_responsibility": "Displays fallback redirect link.",
        "dependencies": "None",
        "if_missing": "Legacy bookmarks to admin-add-scenario.html would fail."
    },
    {
        "name": "admin-add-person.html",
        "type": "HTML (Compatibility Alias / Redirect)",
        "purpose": "Instant client-side redirect to testing-add-person.html.",
        "what": "Person registration alias gateway.",
        "why": "Ensures legacy add-person links route cleanly to testing-add-person.html.",
        "who": "System Users.",
        "where": "Administrative alias.",
        "when": "Triggered when accessing admin-add-person.html.",
        "how": "Executes window.location.replace('testing-add-person.html').",
        "inputs": "URL navigation request.",
        "outputs": "Redirection to testing-add-person.html.",
        "ui_responsibility": "Displays fallback redirect link.",
        "dependencies": "None",
        "if_missing": "Legacy bookmarks to admin-add-person.html would fail."
    },
    {
        "name": "admin-add-team.html",
        "type": "HTML (Compatibility Alias / Redirect)",
        "purpose": "Instant client-side redirect to testing-add-team.html.",
        "what": "Team builder alias gateway.",
        "why": "Ensures legacy add-team links route cleanly to testing-add-team.html.",
        "who": "System Users.",
        "where": "Administrative alias.",
        "when": "Triggered when accessing admin-add-team.html.",
        "how": "Executes window.location.replace('testing-add-team.html').",
        "inputs": "URL navigation request.",
        "outputs": "Redirection to testing-add-team.html.",
        "ui_responsibility": "Displays fallback redirect link.",
        "dependencies": "None",
        "if_missing": "Legacy bookmarks to admin-add-team.html would fail."
    },

    # --- CSS FILES (1) ---
    {
        "name": "css/style.css",
        "type": "CSS (Master Design System & Stylesheet)",
        "purpose": "Unified master stylesheet defining the complete Light White with Blue visual theme, typography, layout grid, component cards, 3D overlays, and responsive breakpoints.",
        "what": "The complete visual and design system foundation for every page in RidgeWatch.",
        "why": "Enforces consistent visual hierarchy, high-contrast readability, glassmorphism tokens, and responsive aesthetics across all 12 modules.",
        "who": "All system pages, all user roles.",
        "where": "Loaded globally by every single HTML file in the project.",
        "when": "Loaded immediately on initial HTML page parse.",
        "how": "Declares CSS custom properties (--bg-void, --ink, --accent-ice), utility classes, layout containers, card hover physics, and media queries.",
        "inputs": "HTML semantic elements, class attributes, data attributes, viewport dimensions.",
        "outputs": "Rendered visual interface with unified fonts, colors, borders, and animations.",
        "ui_responsibility": "Defines sidebar styles, topbar headers, KPI cards, tactical map containers, SVG chart tooltips, and modal backdrops.",
        "dependencies": "Google Fonts (Space Grotesk, JetBrains Mono)",
        "if_missing": "The entire frontend collapses into raw, unstyled HTML with broken layouts, unreadable typography, and no responsive behavior."
    },

    # --- JAVASCRIPT FILES (28) ---
    {
        "name": "js/config.js",
        "type": "JavaScript (Centralized Configuration & API Gateway)",
        "purpose": "Provides single-source-of-truth API base URL discovery, automatic port fallback, and runtime configuration helpers.",
        "what": "Shared frontend configuration utility.",
        "why": "Decouples backend host/port bindings from individual page scripts, ensuring seamless switching between local dev, Docker, and production.",
        "who": "All frontend JavaScript modules.",
        "where": "Loaded first in every HTML script bundle.",
        "when": "Executed immediately upon page script initialization.",
        "how": "Exposes the global RidgeWatchConfig object with getApiBase(), getWsBase(), and environment discovery routines.",
        "inputs": "Browser window.location (protocol, hostname, port), query parameters.",
        "outputs": "Normalized API base URL string (e.g. 'http://127.0.0.1:5000' or relative '').",
        "ui_responsibility": "None directly; powers all AJAX/fetch network calls across every module.",
        "dependencies": "None (Pure standard JavaScript)",
        "if_missing": "Every JavaScript file fails to resolve API endpoints, causing complete network disconnection."
    },
    {
        "name": "js/dashboard.js",
        "type": "JavaScript (Dashboard Controller & Polling Engine)",
        "purpose": "Drives the main operational dashboard by polling active operation state, rendering KPI counts, updating the mini-map, and managing quick scenario launches.",
        "what": "Main dashboard view controller and polling engine.",
        "why": "Keeps the executive summary updated in real-time with live victim counts, team movements, and active disaster alerts.",
        "who": "Dashboard page (index.html).",
        "where": "Dashboard module.",
        "when": "Initializes on index.html load; executes continuous 3-second polling loop.",
        "how": "Fetches /operations, /victims, /alerts, and /scenarios; updates DOM elements with transition effects; renders Leaflet/SVG mini-map.",
        "inputs": "Backend REST responses for operations, victims, alerts, scenarios.",
        "outputs": "DOM updates for KPI values, quick-start button states, active scenario badge, and mini-map markers.",
        "ui_responsibility": "Updates #kpiVictims, #kpiRescued, #kpiActiveAlerts, #scenarioQuickSelect, and #liveMiniMap.",
        "dependencies": "js/config.js",
        "if_missing": "index.html remains static with placeholder values and no dynamic data updates."
    },
    {
        "name": "js/visual.js",
        "type": "JavaScript (Three.js 3D Engine & Digital Twin Controller)",
        "purpose": "Full-featured 3D WebGL rendering engine, 2D architectural schematic renderer, 4D simulation driver, and particle telemetry visualizer.",
        "what": "Hardware digital twin 3D engine built on Three.js.",
        "why": "Provides immersive 3D spatial visualization of hardware stations, sensors, drone paths, and real-time telemetry particles.",
        "who": "Visual module (visual.html).",
        "where": "Visual 3D/4D module.",
        "when": "Initializes on visual.html load; runs a 60 FPS requestAnimationFrame render loop.",
        "how": "Constructs Three.js scene, camera, lights, materials, and procedural 3D hardware meshes; animates particles along sensor data paths; handles mouse raycasting.",
        "inputs": "Hardware telemetry (/hardware/summary), station registry, user mouse drag/zoom gestures.",
        "outputs": "Interactive 60 FPS WebGL scene, component inspector card updates, telemetry particle streams.",
        "ui_responsibility": "Renders 3D viewport canvas, 2D schematic overlay, component inspector sidebar, and telemetry HUD.",
        "dependencies": "js/config.js, external Three.js library (CDN/bundled)",
        "if_missing": "visual.html cannot render 3D scenes or digital twin hardware models."
    },
    {
        "name": "js/logic.js",
        "type": "JavaScript (AI Decision Center & Explainability Engine)",
        "purpose": "Calculates and visualizes the complete Step 0–Step 9 AI reasoning pipeline, Bayesian multi-sensor fusion, and SPS explainability.",
        "what": "Frontend AI reasoning engine and step-by-step calculation renderer.",
        "why": "Translates complex sensor probabilities into transparent, understandable visual steps and actionable rescue guidance.",
        "who": "Logical page (logic.html).",
        "where": "Logical AI Decision module.",
        "when": "Initializes on logic.html load; refreshes on live scenario polling cycles.",
        "how": "Fetches /scenario/intelligence; executes frontend calculation steps; renders Level 1 Decision, Level 2 Evidence, Level 3 Math, and Level 4 Actions.",
        "inputs": "Scenario intelligence payload, active hazard states, sensor readings.",
        "outputs": "Interactive calculation accordion, sensor weight breakdown, confidence meters, action recommendations.",
        "ui_responsibility": "Populates #currentDecisionBanner, #evidenceBreakdownGrid, #stepCalculationList, and #recommendedActionsCard.",
        "dependencies": "js/config.js",
        "if_missing": "logic.html cannot render AI decision steps, calculation proofs, or evidence weighting."
    },
    {
        "name": "js/commander.js",
        "type": "JavaScript (Tactical Command & 2D Map Clustering Engine)",
        "purpose": "Powers the Incident Commander hub with dynamic job assignment, 2D spatial map clustering, collision-free label positioning, and member tracking.",
        "what": "Tactical incident command workflow and mapping engine.",
        "why": "Enables seamless job dispatch and spatial tracking without visual clutter from overlapping map labels.",
        "who": "Commander page (commander.html).",
        "where": "Commander module.",
        "when": "Initializes on commander.html load; runs a continuous 3-second tactical polling loop.",
        "how": "Polls /commander/overview; runs clusterOpsJobs spatial clustering; executes bounding-box label collision avoidance; handles job dispatch modals.",
        "inputs": "Commander overview payload (victims, members, jobs, alerts), user marker clicks, assignment form submissions.",
        "outputs": "Clustered SVG tactical map, dynamic entity counter pills, job dispatch REST calls, arrival notification popovers.",
        "ui_responsibility": "Renders #commanderSiteMap SVG, #legendCountVictims, #jobQueueDrawer, and #assignmentModal.",
        "dependencies": "js/config.js",
        "if_missing": "commander.html loses all tactical mapping, job assignment, and team tracking functionality."
    },
    {
        "name": "js/watch.js",
        "type": "JavaScript (Mobile Field Responder Client Controller)",
        "purpose": "Manages glanceable smartwatch card updates, mission acknowledgment actions, and emergency audio-vibration alerts.",
        "what": "Mobile field responder client script.",
        "why": "Provides responsive, battery-efficient updates for field rescue workers on mobile and wearable form factors.",
        "who": "Watch page (watch.html).",
        "where": "Watch / Mobile module.",
        "when": "Initializes on watch.html load; polls active assignments every 4 seconds.",
        "how": "Fetches responder mission status, updates large-format victim distance card, and dispatches acknowledgment pulses.",
        "inputs": "Member status API (/rescue-team/members-status), active alerts.",
        "outputs": "Status transition requests (En Route -> Arrived), DOM card updates, audio alarm triggers.",
        "ui_responsibility": "Updates #watchVictimCard, #watchVitalsGrid, #watchActionBtn, and #watchAlertBanner.",
        "dependencies": "js/config.js",
        "if_missing": "watch.html remains static without real-time dispatch updates or acknowledgment buttons."
    },
    {
        "name": "js/alerts.js",
        "type": "JavaScript (Active Hazard Alert Lifecycle Controller)",
        "purpose": "Controls active emergency alert polling, severity filtering, audio alert synthesis, and alert acknowledgment workflows.",
        "what": "Emergency alert center view controller.",
        "why": "Ensures real-time hazard warnings are audibly signaled, visually prioritized, and recorded in compliance with safety protocols.",
        "who": "Alerts page (alerts.html).",
        "where": "Alerts module.",
        "when": "Initializes on alerts.html load; polls active alerts ledger every 3 seconds.",
        "how": "Fetches /alerts; sorts by severity (CRITICAL first); synthesizes Web Audio API alarm pulses on new critical alerts; manages filter tabs.",
        "inputs": "Alerts endpoint (/alerts), user severity tab clicks, acknowledge button clicks.",
        "outputs": "Updated alert cards, audio alarms, POST /alerts/{id}/ack acknowledgment calls.",
        "ui_responsibility": "Renders #alertsGrid, #alertFilterTabs, #audioAlarmToggle, and #criticalAlertCounter.",
        "dependencies": "js/config.js",
        "if_missing": "alerts.html cannot poll alerts, filter by severity, or trigger audio warning alarms."
    },
    {
        "name": "js/analytics.js",
        "type": "JavaScript (Analytics Engine & Mathematical Consistency Controller)",
        "purpose": "Aggregates operational metrics across selectable timeframes (Live, 24h, 7d, 30d, All-Time), renders interactive SVG charts, and enforces mathematical consistency.",
        "what": "Operational performance analytics aggregator and visualization engine.",
        "why": "Provides verified operational metrics (Total Victims = Rescued + En Route + Pending; Rescue Rate = Rescued / Victims) without fake data.",
        "who": "Analytics page (analytics.html).",
        "where": "Analytics module.",
        "when": "Initializes on analytics.html load; re-computes all metrics on scope or scenario filter change.",
        "how": "Fetches /analytics/summary, /scenario/intelligence, /hazards/landslide/history; applies scope filter; draws SVG bars, lines, and donuts.",
        "inputs": "Analytics summary data, live operation state, sensor history telemetry, user scope dropdown selection.",
        "outputs": "Calculated KPI values, SVG rescue trend chart, scenario donut chart, victim status donut, team performance cards.",
        "ui_responsibility": "Populates #operationalPictureCard, #kpiRescueRate, #performanceChart, #hazardDonutSvg, #victimStatusDonutSvg, and #sessionsTable.",
        "dependencies": "js/config.js",
        "if_missing": "analytics.html displays no charts, calculations, or session tables."
    },
    {
        "name": "js/scenarios.js",
        "type": "JavaScript (Scenario Catalog Controller)",
        "purpose": "Fetches pre-configured disaster scenarios, renders catalog cards with hazard tags, and handles one-click scenario launch triggers.",
        "what": "Scenario catalog view controller.",
        "why": "Enables users to visually explore and launch disaster drills from the scenario library.",
        "who": "Scenarios page (scenarios.html).",
        "where": "Scenarios module.",
        "when": "Initializes on scenarios.html load.",
        "how": "Fetches /scenarios; constructs disaster cards with complexity ratings; binds click handlers to trigger POST /scenario/start.",
        "inputs": "Scenario catalog REST response, user launch button clicks.",
        "outputs": "Rendered scenario cards, scenario start API calls, navigation to Dashboard.",
        "ui_responsibility": "Populates #scenariosGrid with scenario cards and launch state feedback.",
        "dependencies": "js/config.js",
        "if_missing": "scenarios.html cannot fetch or display the scenario library."
    },
    {
        "name": "js/victims.js",
        "type": "JavaScript (Survivor Directory & Triage Controller)",
        "purpose": "Manages survivor roster display, triage priority filtering, vital signs telemetry badges, and individual survivor modal views.",
        "what": "Survivor directory view controller.",
        "why": "Provides medical and triage staff with live filtered views of all detected survivors and their health parameters.",
        "who": "Victims page (victims.html).",
        "where": "Victims module.",
        "when": "Initializes on victims.html load; polls active survivors every 4 seconds.",
        "how": "Fetches /victims; filters by triage priority (High, Medium, Low); renders health status pills and coordinate detail drawers.",
        "inputs": "Victims fusion payload, user triage filter clicks.",
        "outputs": "Filtered victim cards and tables, vital signs progress indicators.",
        "ui_responsibility": "Populates #victimsTableBody, #triageFilterPills, and #victimDetailModal.",
        "dependencies": "js/config.js",
        "if_missing": "victims.html cannot display detected survivors or vital signs telemetry."
    },
    {
        "name": "js/teams.js",
        "type": "JavaScript (Rescue Teams Roster Controller)",
        "purpose": "Polls registered rescue teams, renders team capability cards, displays member availability, and links to the Commander map.",
        "what": "Teams roster view controller.",
        "why": "Provides a clean overview of all rescue teams, callsigns, and deployment readiness.",
        "who": "Teams page (teams.html).",
        "where": "Teams module.",
        "when": "Initializes on teams.html load; polls team states every 5 seconds.",
        "how": "Fetches /admin/teams and /rescue-team/members-status; renders team summary cards with member count badges.",
        "inputs": "Teams catalog, member status records.",
        "outputs": "Rendered team cards, deployment status indicators.",
        "ui_responsibility": "Populates #teamsContainer with structured team cards and member callsign pills.",
        "dependencies": "js/config.js",
        "if_missing": "teams.html cannot display rescue team cards or member statuses."
    },
    {
        "name": "js/hardware.js",
        "type": "JavaScript (Hardware Registry & Sensor Diagnostic Controller)",
        "purpose": "Monitors sensing stations in real time, renders battery gauge meters, tracks communication dropout states, and displays raw sensor telemetry.",
        "what": "Hardware and sensor station diagnostic controller.",
        "why": "Enables engineers to monitor physical sensing nodes, diagnose low battery states, and detect dropped sensor packets.",
        "who": "Hardware page (hardware.html).",
        "where": "Hardware module.",
        "when": "Initializes on hardware.html load; executes continuous 3-second diagnostic polling loop.",
        "how": "Fetches /hardware/summary and /hardware/registry; calculates battery percentages; renders SVG gauges and hardware health cards.",
        "inputs": "Hardware telemetry records, sensor battery voltages, calibration metadata.",
        "outputs": "DOM updates for hardware station cards, battery meters, sensor status pills.",
        "ui_responsibility": "Populates #hardwareGrid, #stationHealthGauges, and #rawTelemetryInspector.",
        "dependencies": "js/config.js",
        "if_missing": "hardware.html displays no hardware cards or battery diagnostic gauges."
    },
    {
        "name": "js/testing-common.js",
        "type": "JavaScript (Testing & Admin Shared Layout Framework)",
        "purpose": "Injects the unified navigation header, active tab highlighters, common modals, and notification toast handlers across all Testing Console sub-pages.",
        "what": "Shared layout and navigation framework for the Testing Console.",
        "why": "Eliminates duplicate navigation HTML across the 7 Testing/Admin sub-pages and enforces consistent header styling.",
        "who": "All Testing Console pages (testing*.html).",
        "where": "Shared across Testing & Admin modules.",
        "when": "Loaded first on every testing-*.html page before page-specific scripts.",
        "how": "Dynamically constructs and inserts the secondary sub-nav bar, active tab indicators, and toast notification container.",
        "inputs": "Current page filename (window.location.pathname).",
        "outputs": "Rendered shared header sub-nav, active tab highlight, toast notifications.",
        "ui_responsibility": "Renders .testing-nav-bar, #testingToastContainer, and common modal backdrops.",
        "dependencies": "js/config.js",
        "if_missing": "Testing and Admin sub-pages lose their unified sub-navigation bar and toast notification system."
    },
    {
        "name": "js/testing.js",
        "type": "JavaScript (Interactive Simulation Driver & Sandbox Controller)",
        "purpose": "Drives the main Testing Console sandbox, handles simulation cycle step controls, executes synthetic sensor injections, and displays live simulation logs.",
        "what": "Testing console simulation controller and synthetic data injector.",
        "why": "Allows testers to manipulate simulation speed, advance cycles, trigger degradation modes, and test edge-case sensor values.",
        "who": "Testing page (testing.html).",
        "where": "Testing module.",
        "when": "Initializes on testing.html load.",
        "how": "Binds simulation control buttons (Step, Play, Reset); posts telemetry payloads to /testing/inject-reading; displays streaming simulation event logs.",
        "inputs": "User slider adjustments, step button clicks, scenario selector.",
        "outputs": "Telemetry injection API calls, cycle step requests, formatted log output.",
        "ui_responsibility": "Controls #simControlBar, #telemetrySliderInputs, #activeScenarioInfo, and #simLogViewer.",
        "dependencies": "js/config.js, js/testing-common.js",
        "if_missing": "testing.html cannot advance simulation steps or inject test telemetry."
    },
    {
        "name": "js/testing-scenarios.js",
        "type": "JavaScript (Testing Scenario Ledger Controller)",
        "purpose": "Manages the scenario ledger table in the Testing Console, allowing testers to toggle scenarios Active/Inactive and launch fresh test runs.",
        "what": "Scenario ledger controller.",
        "why": "Provides administrative control over which scenarios are enabled in the database ledger.",
        "who": "testing-scenarios.html.",
        "where": "Testing module.",
        "when": "Initializes on testing-scenarios.html load.",
        "how": "Fetches /admin/scenarios; renders ledger rows with toggle switches; calls POST /admin/scenario/{id}/toggle on status change.",
        "inputs": "Scenario ledger data, toggle switch clicks.",
        "outputs": "Updated scenario ledger states, scenario activation API calls.",
        "ui_responsibility": "Populates #scenariosTableBody with status switches and victim count badges.",
        "dependencies": "js/config.js, js/testing-common.js",
        "if_missing": "testing-scenarios.html cannot display or toggle scenario ledger statuses."
    },
    {
        "name": "js/testing-persons.js",
        "type": "JavaScript (Testing Personnel Directory Controller)",
        "purpose": "Manages the responder personnel table in the Testing Console, providing search, role filtering, and skill certification inspection.",
        "what": "Personnel directory controller.",
        "why": "Allows inspection of registered personnel, disaster certifications, and contact information.",
        "who": "testing-persons.html.",
        "where": "Testing module.",
        "when": "Initializes on testing-persons.html load.",
        "how": "Fetches /admin/persons; provides text search and skill filtering; renders formatted personnel table.",
        "inputs": "Personnel records, search input, role filter dropdown.",
        "outputs": "Filtered personnel table, delete person API calls.",
        "ui_responsibility": "Populates #personsTableBody with responder records and skill certification tags.",
        "dependencies": "js/config.js, js/testing-common.js",
        "if_missing": "testing-persons.html cannot fetch or display registered responder personnel."
    },
    {
        "name": "js/testing-teams.js",
        "type": "JavaScript (Testing Teams Management Controller)",
        "purpose": "Controls the teams table and member cards in the Testing Console, allowing team inspection and deletion.",
        "what": "Teams management controller.",
        "why": "Allows testers and administrators to manage team configurations and view member allocations.",
        "who": "testing-teams.html.",
        "where": "Testing module.",
        "when": "Initializes on testing-teams.html load.",
        "how": "Fetches /admin/teams; renders structured team cards with member rosters; handles team deletion requests.",
        "inputs": "Teams records, delete button clicks.",
        "outputs": "Rendered team list, DELETE /admin/team/{id} calls.",
        "ui_responsibility": "Populates #teamsTableBody with team rows, member counts, and action buttons.",
        "dependencies": "js/config.js, js/testing-common.js",
        "if_missing": "testing-teams.html cannot display or delete configured rescue teams."
    },
    {
        "name": "js/testing-add-scenario.js",
        "type": "JavaScript (Custom Scenario Form Handler)",
        "purpose": "Validates custom scenario builder inputs, generates synthetic victim coordinates around the site origin, and posts to /admin/scenario/create.",
        "what": "Custom scenario builder controller.",
        "why": "Enables creation of custom multi-hazard scenarios with validated geographical and victim parameters.",
        "who": "testing-add-scenario.html.",
        "where": "Testing module.",
        "when": "Initializes on testing-add-scenario.html form submission.",
        "how": "Validates form fields, generates procedural victim coordinates, submits payload to API, and navigates to scenario ledger on success.",
        "inputs": "Form field values (Scenario ID, Name, Coordinates, Victim Count, Hazard Type).",
        "outputs": "Validated scenario creation API request, user validation alerts.",
        "ui_responsibility": "Handles form validation states, error highlights, and submission loading spinners.",
        "dependencies": "js/config.js, js/testing-common.js",
        "if_missing": "testing-add-scenario.html cannot validate or submit custom scenario creation requests."
    },
    {
        "name": "js/testing-add-person.js",
        "type": "JavaScript (Personnel Enrollment Form Handler)",
        "purpose": "Validates responder enrollment data, collects multi-disaster skill certifications, and submits to /admin/person/create.",
        "what": "Personnel enrollment form controller.",
        "why": "Ensures all registered responders have valid names, roles, and appropriate disaster category certifications.",
        "who": "testing-add-person.html.",
        "where": "Testing module.",
        "when": "Initializes on testing-add-person.html form submission.",
        "how": "Collects checked disaster categories; validates callsign and role; posts JSON payload to /admin/person/create; redirects to personnel directory.",
        "inputs": "Form inputs (Name, Role, Callsign, Certification Checkboxes).",
        "outputs": "Person creation API request, error/success toast notifications.",
        "ui_responsibility": "Controls form validation states and skill category checkbox groupings.",
        "dependencies": "js/config.js, js/testing-common.js",
        "if_missing": "testing-add-person.html cannot validate or register new personnel."
    },
    {
        "name": "js/testing-add-team.js",
        "type": "JavaScript (Team Creation Form Handler)",
        "purpose": "Fetches available personnel, validates team metadata, allows member selection, and posts new team definitions to /admin/team/create.",
        "what": "Team creation form controller.",
        "why": "Enables assembling new tactical units by associating available personnel with team metadata.",
        "who": "testing-add-team.html.",
        "where": "Testing module.",
        "when": "Initializes on testing-add-team.html load and form submission.",
        "how": "Queries /admin/persons to populate member picker; collects team parameters; posts to /admin/team/create; redirects to teams directory.",
        "inputs": "Form inputs (Team Name, Team Type, Base Coordinates, Selected Member IDs).",
        "outputs": "Team creation API request, member selection updates.",
        "ui_responsibility": "Populates member selection checkboxes, validates minimum staffing, and handles submission.",
        "dependencies": "js/config.js, js/testing-common.js",
        "if_missing": "testing-add-team.html cannot fetch available members or create rescue teams."
    },
    # --- ADMIN COMPATIBILITY JAVASCRIPT PROXIES (8 JS files) ---
    {
        "name": "js/admin.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Redirects legacy admin script invocations to testing.js.",
        "what": "Legacy admin controller proxy.",
        "why": "Maintains backwards compatibility for legacy admin scripts.",
        "who": "Legacy admin modules.",
        "where": "Admin compatibility layer.",
        "when": "Loaded if legacy admin.html is requested.",
        "how": "Delegates execution to testing.js workflows.",
        "inputs": "None",
        "outputs": "Compatibility routing.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing.js",
        "if_missing": "Legacy script imports might fail if explicitly referenced."
    },
    {
        "name": "js/admin-common.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Proxies legacy admin common layout routines to testing-common.js.",
        "what": "Legacy layout proxy.",
        "why": "Maintains backwards compatibility for admin sub-navigation.",
        "who": "Legacy admin sub-pages.",
        "where": "Admin compatibility layer.",
        "when": "Loaded by legacy admin HTML pages.",
        "how": "Executes testing-common.js initialization.",
        "inputs": "None",
        "outputs": "Navigation rendering.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing-common.js",
        "if_missing": "Legacy admin pages lose sub-nav if accessed directly without redirect."
    },
    {
        "name": "js/admin-scenarios.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Proxies legacy admin scenario ledger calls to testing-scenarios.js.",
        "what": "Scenario ledger proxy.",
        "why": "Ensures legacy script references execute testing-scenarios logic.",
        "who": "admin-scenarios.html.",
        "where": "Admin compatibility layer.",
        "when": "Loaded by legacy admin-scenarios.html.",
        "how": "Delegates to testing-scenarios.js.",
        "inputs": "None",
        "outputs": "Scenario ledger updates.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing-scenarios.js",
        "if_missing": "Legacy script reference fails."
    },
    {
        "name": "js/admin-persons.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Proxies legacy admin personnel directory calls to testing-persons.js.",
        "what": "Personnel directory proxy.",
        "why": "Ensures legacy script references execute testing-persons logic.",
        "who": "admin-persons.html.",
        "where": "Admin compatibility layer.",
        "when": "Loaded by legacy admin-persons.html.",
        "how": "Delegates to testing-persons.js.",
        "inputs": "None",
        "outputs": "Personnel directory updates.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing-persons.js",
        "if_missing": "Legacy script reference fails."
    },
    {
        "name": "js/admin-teams.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Proxies legacy admin teams calls to testing-teams.js.",
        "what": "Teams management proxy.",
        "why": "Ensures legacy script references execute testing-teams logic.",
        "who": "admin-teams.html.",
        "where": "Admin compatibility layer.",
        "when": "Loaded by legacy admin-teams.html.",
        "how": "Delegates to testing-teams.js.",
        "inputs": "None",
        "outputs": "Teams directory updates.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing-teams.js",
        "if_missing": "Legacy script reference fails."
    },
    {
        "name": "js/admin-add-scenario.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Proxies legacy add-scenario form calls to testing-add-scenario.js.",
        "what": "Scenario creation proxy.",
        "why": "Ensures legacy script references execute testing-add-scenario logic.",
        "who": "admin-add-scenario.html.",
        "where": "Admin compatibility layer.",
        "when": "Loaded by legacy admin-add-scenario.html.",
        "how": "Delegates to testing-add-scenario.js.",
        "inputs": "None",
        "outputs": "Scenario creation requests.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing-add-scenario.js",
        "if_missing": "Legacy script reference fails."
    },
    {
        "name": "js/admin-add-person.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Proxies legacy add-person form calls to testing-add-person.js.",
        "what": "Person registration proxy.",
        "why": "Ensures legacy script references execute testing-add-person logic.",
        "who": "admin-add-person.html.",
        "where": "Admin compatibility layer.",
        "when": "Loaded by legacy admin-add-person.html.",
        "how": "Delegates to testing-add-person.js.",
        "inputs": "None",
        "outputs": "Person registration requests.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing-add-person.js",
        "if_missing": "Legacy script reference fails."
    },
    {
        "name": "js/admin-add-team.js",
        "type": "JavaScript (Compatibility Proxy)",
        "purpose": "Proxies legacy add-team form calls to testing-add-team.js.",
        "what": "Team creation proxy.",
        "why": "Ensures legacy script references execute testing-add-team logic.",
        "who": "admin-add-team.html.",
        "where": "Admin compatibility layer.",
        "when": "Loaded by legacy admin-add-team.html.",
        "how": "Delegates to testing-add-team.js.",
        "inputs": "None",
        "outputs": "Team creation requests.",
        "ui_responsibility": "None directly.",
        "dependencies": "js/testing-add-team.js",
        "if_missing": "Legacy script reference fails."
    }
]

SECTIONS_CONTENT = [
    # -----------------------------------------------------------------------
    # SECTION 1: EXECUTIVE SUMMARY & FRONTEND PURPOSE
    # -----------------------------------------------------------------------
    {
        "title": "1. Executive Summary & Frontend Purpose",
        "blocks": [
            {
                "type": "paragraph",
                "text": "RIDGEWATCH is an advanced AI-powered multi-disaster survivor detection, triage, and autonomous search-and-rescue coordination system. "
                        "The frontend serves as the operational command interface, cognitive decision visualization center, and spatial tactical map for emergency disaster responders. "
                        "It translates complex multi-modal sensor streams (Inclinometer, Rainfall, Thermal Infrared, Optical YOLOv8, Barometric Pressure, Seismic, and Biometric vitals) into clear, actionable intelligence."
            },
            {
                "type": "heading2",
                "text": "Core Operational Questions Answered by the Frontend"
            },
            {
                "type": "paragraph",
                "prefix": "1. What is the frontend?",
                "text": "A modular, responsive, high-performance web client suite comprising 12 interconnected operational modules, interactive 2D/3D/4D digital twins, tactical spatial maps, and mobile field clients."
            },
            {
                "type": "paragraph",
                "prefix": "2. Why does it exist?",
                "text": "In search-and-rescue missions, the 'Golden Hour' dictates survivor mortality. The frontend exists to eliminate cognitive overload, visualize AI survival probability scores (SPS), guide tactical dispatches, and coordinate multi-team field responses."
            },
            {
                "type": "paragraph",
                "prefix": "3. Who uses it?",
                "text": "Incident Commanders (overall theater strategy), Search & Rescue Responders (tactical field execution), Medical Triage Officers (survivor health prioritization), Hardware Engineers (sensor station health), and System Evaluators (simulation and training)."
            },
            {
                "type": "paragraph",
                "prefix": "4. Where is it used?",
                "text": "In Emergency Operations Centers (EOC desktop monitors), forward mobile command vehicles (ruggedized field tablets), and on-foot responder wearables (smartwatch browser view)."
            },
            {
                "type": "paragraph",
                "prefix": "5. When is each module used?",
                "text": "Dashboard and Commander are active during live operations; Logical is used when auditing AI evidence; Watch is used during active foot search; Analytics is used for performance review; Testing is used for simulation and scenario authoring."
            },
            {
                "type": "paragraph",
                "prefix": "6. How does it work as a complete system?",
                "text": "The frontend maintains a decoupled, reactive polling and event-driven architecture that queries standardized REST endpoints, processes JSON operational payloads, manages client-side UI states, and provides zero-latency visual feedback."
            },
            {
                "type": "callout",
                "title": "ZERO FAKE DATA MANDATE",
                "text": "Every number, badge, chart, and map entity rendered on the RidgeWatch frontend derives strictly from audited backend simulation models, database records, or live sensor telemetry. The frontend strictly forbids fabricated metrics or hardcoded dummy values."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 2: FRONTEND ARCHITECTURAL PHILOSOPHY & DESIGN SYSTEM
    # -----------------------------------------------------------------------
    {
        "title": "2. Frontend Architectural Philosophy & Design Principles",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The RidgeWatch frontend is engineered around four core architectural pillars: Clean Light White with Blue Visual Ergonomics, Explainable Intelligence Hierarchy, Strict Mathematical Consistency, and High-Contrast Tactical Readability."
            },
            {
                "type": "heading2",
                "text": "Visual Design System: Light White with Blue Palette"
            },
            {
                "type": "paragraph",
                "text": "Operational emergency control rooms require high legibility under varying ambient lighting conditions. "
                        "The interface employs a tailored palette consisting of Crisp Canvas White (#FFFFFF), Ice Tinted Backgrounds (#F3F7FD), Deep Navy Typography (#0F2547), Electric Blue Accents (#2563EB), and standardized semantic state badges."
            },
            {
                "type": "table",
                "headers": ["TOKEN NAME", "HEX VALUE", "SEMANTIC USAGE IN UI"],
                "data": [
                    ["--bg-void", "#FFFFFF", "Primary canvas, modal containers, and elevated cards"],
                    ["--bg-panel-raised", "#F3F7FD", "Sidebar navigation, hero banners, and sub-nav bars"],
                    ["--ink", "#0F2547", "High-contrast headings, primary titles, and numerical metrics"],
                    ["--ink-dim", "#64748B", "Metadata labels, timestamps, units, and secondary subtitles"],
                    ["--accent-ice", "#2563EB", "Interactive links, primary buttons, and live route lines"],
                    ["--border", "#D3E1F5", "Subtle structural borders, table dividers, and input strokes"],
                    ["--status-critical", "#EF4444", "High-priority survivor triage and emergency hazard alerts"],
                    ["--status-warning", "#EA580C", "Moderate hazard thresholds and pending dispatch queues"],
                    ["--status-success", "#16A34A", "Verified survivor rescues and nominal hardware stations"],
                ],
                "widths": [1.8, 1.2, 3.5]
            },
            {
                "type": "heading2",
                "text": "Standardized Data State Indicator System"
            },
            {
                "type": "paragraph",
                "text": "To prevent operational ambiguity, the frontend enforces a strict universal data state convention across all 12 modules:"
            },
            {
                "type": "table",
                "headers": ["STATE INDICATOR", "VISUAL REPRESENTATION", "OPERATIONAL MEANING"],
                "data": [
                    ["Valid Numerical Zero", "0", "A verified zero quantity (e.g. 0 active alerts, 0 critical failures)"],
                    ["Missing Telemetry", "--", "Sensor channel offline, uncalibrated, or awaiting initial packet"],
                    ["Not Applicable", "N/A", "Metric cannot be mathematically evaluated (e.g. rescue rate when victims = 0)"],
                    ["Awaiting Pipeline", "PENDING", "Task queued or AI fusion engine computing current step"],
                    ["Device Offline", "OFFLINE", "Station disconnected or failed heartbeat threshold"],
                    ["Data Stale", "STALE", "Last received packet timestamp exceeds maximum freshness window (>15s)"],
                    ["Healthy / Nominal", "ONLINE / NOMINAL", "Subsystem verified healthy and operating within calibrated bounds"],
                ],
                "widths": [1.6, 1.8, 3.1]
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 3: NAVIGATION ARCHITECTURE & MODULE HIERARCHY
    # -----------------------------------------------------------------------
    {
        "title": "3. System Navigation Architecture & Module Hierarchy",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The frontend is structured into 12 primary operational modules accessible via the persistent master sidebar, complemented by a secondary testing sub-navigation bar for development and simulation administration."
            },
            {
                "type": "heading2",
                "text": "Master Navigation Tree"
            },
            {
                "type": "paragraph",
                "text": "RIDGEWATCH SYSTEM NAVIGATION TOPOLOGY:\n"
                        "├── 📡 Dashboard (index.html) -> Executive Situation Summary & Quick Launcher\n"
                        "├── 🌐 Visual 3D (visual.html) -> 2D Architecture / 3D Digital Twin / 4D Simulation\n"
                        "├── 🧠 Logical (logic.html) -> Level 1–4 AI Decision Center & Step-by-Step Math\n"
                        "├── 🎖️ Commander (commander.html) -> Tactical 2D Clustered Map & Job Dispatch\n"
                        "├── ⌚ Watch (watch.html) -> Mobile / Wearable Field Responder Triage Client\n"
                        "├── 🚨 Alerts (alerts.html) -> Active Emergency Hazard Alert Ledger & Audio Alarms\n"
                        "├── 📈 Analytics (analytics.html) -> Scope-Filtered Rescue Performance Dashboard\n"
                        "├── 🗺️ Scenarios (scenarios.html) -> Pre-configured Disaster Scenario Catalog\n"
                        "├── 🧍 Victims (victims.html) -> Survivor Directory, SPS Triage & Vital Signs\n"
                        "├── 🚁 Teams (teams.html) -> Rescue Team Deployment Roster & Availability\n"
                        "├── 🔧 Hardware (hardware.html) -> Sensor Diagnostic Gauges & Telemetry Monitor\n"
                        "└── 📊 Testing Console (testing.html) -> Multi-Disaster Simulation Sandbox\n"
                        "     ├── Scenarios Ledger (testing-scenarios.html)\n"
                        "     ├── Personnel Directory (testing-persons.html)\n"
                        "     ├── Teams Catalog (testing-teams.html)\n"
                        "     ├── Custom Scenario Builder (testing-add-scenario.html)\n"
                        "     ├── Personnel Enrollment (testing-add-person.html)\n"
                        "     └── Team Formation (testing-add-team.html)"
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 4: SHARED FRONTEND INFRASTRUCTURE & CENTRALIZED UTILITIES
    # -----------------------------------------------------------------------
    {
        "title": "4. Shared Frontend Infrastructure & Centralized Utilities",
        "blocks": [
            {
                "type": "paragraph",
                "text": "To guarantee architectural consistency, prevent code duplication, and maintain maintainability, shared frontend responsibilities are decoupled into dedicated shared utilities."
            },
            {
                "type": "heading2",
                "text": "Shared Infrastructure Components"
            },
            {
                "type": "paragraph",
                "prefix": "1. js/config.js (API Gateway & Runtime Discovery):",
                "text": "Centralizes backend URL detection. Determines whether the web app is served directly from FastAPI, behind a reverse proxy, or on a custom port, providing a unified getApiBase() accessor."
            },
            {
                "type": "paragraph",
                "prefix": "2. js/testing-common.js (Testing Subsystem Framework):",
                "text": "Dynamically constructs and injects the secondary sub-navigation bar across all 6 Testing Console views, tracks active page highlights, and manages toast notification popups."
            },
            {
                "type": "paragraph",
                "prefix": "3. css/style.css (Design System Tokens):",
                "text": "Declares global CSS variables, resets browser defaults, formats standard card elevation physics, and handles responsive layout collapse for mobile viewports."
            },
            {
                "type": "callout",
                "title": "SHARED INFRASTRUCTURE FLOW",
                "text": "CENTRAL CONFIG (js/config.js) -> SHARED LAYOUT (js/testing-common.js) -> GLOBAL THEME (css/style.css) -> 12 OPERATIONAL MODULES."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 7: CSS DESIGN SYSTEM & VISUAL FOUNDATION
    # -----------------------------------------------------------------------
    {
        "title": "7. CSS Design System & Visual Foundation (style.css)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "frontend/css/style.css contains over 8,900 lines of structured vanilla CSS with zero third-party framework bloat. It provides a modular, highly performant styling engine tailored specifically for real-time telemetry dashboards."
            },
            {
                "type": "heading2",
                "text": "Core CSS Architecture Subsystems"
            },
            {
                "type": "paragraph",
                "prefix": "• Design Tokens & CSS Custom Properties:",
                "text": "Defines foundational color tokens, spacing scales (4px, 8px, 12px, 16px, 24px, 32px), border radii (6px, 10px, 14px, 9999px), and font families ('Space Grotesk' for display headers, 'JetBrains Mono' for numbers/telemetry)."
            },
            {
                "type": "paragraph",
                "prefix": "• Responsive Shell & Navigation:",
                "text": "Implements the fixed .sidebar container (240px width on desktop) paired with the flexible .main-content viewport and sticky topbars."
            },
            {
                "type": "paragraph",
                "prefix": "• Component Card System (.panel, .stat-card, .analytics-kpi-card):",
                "text": "Provides standardized white elevated cards with subtle border strokes (#D3E1F5), soft ambient drop shadows, and responsive grid layouts."
            },
            {
                "type": "paragraph",
                "prefix": "• Spatial Tactical Map Styling:",
                "text": "Styles SVG map boundaries, clustered team pins (.cmd-cluster-pin), survivor triage markers (.victim-pin-high, .victim-pin-med), and dynamic collision labels."
            },
            {
                "type": "paragraph",
                "prefix": "• Responsive Media Breakpoints:",
                "text": "Adapts layouts smoothly at 1440px (wide desktop), 1200px (standard laptop), 960px (tablet landscape), 768px (tablet portrait), and 600px (mobile phones/wearables)."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 8: VISUAL 2D / 3D / 4D DIGITAL TWIN DEEP DIVE
    # -----------------------------------------------------------------------
    {
        "title": "8. Visual 2D / 3D / 4D Digital Twin Deep Dive",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The Visual module (visual.html and visual.js) provides multi-dimensional digital twin representations of the disaster deployment site."
            },
            {
                "type": "heading2",
                "text": "Dimensional Hierarchy"
            },
            {
                "type": "paragraph",
                "prefix": "• 2D Architectural Schematic View:",
                "text": "A clean schematic representation illustrating logical relationships between sensing nodes, gateway routers, drone relays, and the central command server."
            },
            {
                "type": "paragraph",
                "prefix": "• 3D Physical Digital Twin:",
                "text": "Interactive Three.js WebGL spatial model rendering exact hardware enclosures, mast structures, solar panels, sensor probes, and drone flight corridors."
            },
            {
                "type": "paragraph",
                "prefix": "• 4D Temporal Telemetry & Simulation Playback:",
                "text": "Integrates the time dimension, streaming real-time sensor telemetry particles through the 3D model, animating thermal heat plumes, and tracking ground tilt displacement over time."
            },
            {
                "type": "heading2",
                "text": "Interactive Visual Controls & Features"
            },
            {
                "type": "paragraph",
                "prefix": "• Component Inspector Drawer:",
                "text": "Clicking any 3D station opens a slide-over panel displaying real-time battery voltage, packet transmission rate, temperature, and calibration status."
            },
            {
                "type": "paragraph",
                "prefix": "• Camera Navigation Toolbar:",
                "text": "Provides orbit controls, smooth zoom, pan, preset camera angles (Top-Down Overview, Station Close-Up, Drone Perspective), and full-screen toggle."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 9: LOGICAL AI DECISION CENTER DEEP DIVE
    # -----------------------------------------------------------------------
    {
        "title": "9. Logical AI Decision Center & Explainability Engine Deep Dive",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The Logical module (logic.html and logic.js) transforms raw sensor probabilities into an operational AI Decision Center structured across 4 distinct cognitive levels."
            },
            {
                "type": "heading2",
                "text": "The 5-Stage Cognitive Decision Pipeline"
            },
            {
                "type": "paragraph",
                "text": "EVIDENCE (Multi-Sensor Telemetry)\n"
                        "    ↓\n"
                        "FUSION (Bayesian Probability Weighting)\n"
                        "    ↓\n"
                        "DECISION (Triage Classification & Priority Score)\n"
                        "    ↓\n"
                        "EXPLANATION (Primary Driver & Hazard Multiplier Narrative)\n"
                        "    ↓\n"
                        "ACTION (Recommended Tactical Rescue Dispatch Guidance)"
            },
            {
                "type": "heading2",
                "text": "The 4 Information Levels in UI"
            },
            {
                "type": "paragraph",
                "prefix": "• LEVEL 1 — CURRENT DECISION:",
                "text": "Top-level summary card displaying active disaster classification, current risk severity, top survivor triage priority, and confidence rating."
            },
            {
                "type": "paragraph",
                "prefix": "• LEVEL 2 — SENSOR EVIDENCE:",
                "text": "Visual breakdown separating Primary Sensors (e.g. Inclinometer, Rainfall for Landslide) from Supporting and Inactive sensors."
            },
            {
                "type": "paragraph",
                "prefix": "• LEVEL 3 — STEP-BY-STEP CALCULATION PROOFS:",
                "text": "Expandable calculation accordion detailing Step 0 (Raw Normalization) through Step 9 (Survival Probability Score derivation)."
            },
            {
                "type": "paragraph",
                "prefix": "• LEVEL 4 — ACTION GUIDANCE:",
                "text": "Explicit operational directives indicating required team specializations, evacuation corridors, and equipment requirements."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 10: ANALYTICS & RESCUE PERFORMANCE DASHBOARD DEEP DIVE
    # -----------------------------------------------------------------------
    {
        "title": "10. Analytics & Operational Intelligence Dashboard Deep Dive",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The Analytics module (analytics.html and analytics.js) delivers retrospective and real-time operational intelligence."
            },
            {
                "type": "heading2",
                "text": "The Operational Data Hierarchy"
            },
            {
                "type": "paragraph",
                "text": "DATA (Sensor Telemetry & Timestamps)\n"
                        "    ↓\n"
                        "MEANING (Calculated Rescue Rates & Response Averages)\n"
                        "    ↓\n"
                        "IMPACT (Hazard Severity & Station Health)\n"
                        "    ↓\n"
                        "ACTION (Resource Reallocation & Operational Improvements)"
            },
            {
                "type": "heading2",
                "text": "Global Scope Control & Data Integrity"
            },
            {
                "type": "paragraph",
                "text": "The dashboard features a global scope filter bar with 5 selectable modes:\n"
                        "1. Current Session (Live active operation in memory)\n"
                        "2. Last 24 Hours (Audited SQLite sessions within 24h)\n"
                        "3. Last 7 Days (Historical sessions within 7 days)\n"
                        "4. Last 30 Days (Historical sessions within 30 days)\n"
                        "5. All Time (Entire database audit history)\n\n"
                        "All cards, SVG charts, donuts, and tables update simultaneously to reflect strictly the selected scope, preventing data mixing."
            },
            {
                "type": "callout",
                "title": "MATHEMATICAL CONSISTENCY RULE",
                "text": "Total Victims = Rescued + En Route + Pending. Rescue Rate = (Total Rescued / Total Victims) * 100. If Total Victims = 0, the system displays 'N/A · Waiting for sufficient rescue data' rather than a misleading 0.0%."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 11: INCIDENT COMMANDER & TACTICAL MAP CLUSTERING
    # -----------------------------------------------------------------------
    {
        "title": "11. Incident Commander & Tactical Map Clustering Engine Deep Dive",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The Commander module (commander.html and commander.js) serves as the primary tactical theater interface."
            },
            {
                "type": "heading2",
                "text": "The Tactical Command Workflow"
            },
            {
                "type": "paragraph",
                "text": "SCENARIO ACTIVATED\n"
                        "    ↓\n"
                        "ELIGIBLE STAFF FILTERED (Disaster Certification Check)\n"
                        "    ↓\n"
                        "TACTICAL TEAM FORMED\n"
                        "    ↓\n"
                        "SURVIVOR JOB GENERATED\n"
                        "    ↓\n"
                        "COMMANDER ASSIGNMENT\n"
                        "    ↓\n"
                        "STAFF DISPATCH (En Route)\n"
                        "    ↓\n"
                        "ARRIVAL & RESCUE CONFIRMATION (Arrived / Rescued)\n"
                        "    ↓\n"
                        "COMMANDER MONITORING"
            },
            {
                "type": "heading2",
                "text": "2D Tactical Map Engine Features"
            },
            {
                "type": "paragraph",
                "prefix": "• Proximity Job Clustering (clusterOpsJobs):",
                "text": "Automatically groups nearby tactical missions occurring within 80 meters into clean cluster badges to eliminate map clutter."
            },
            {
                "type": "paragraph",
                "prefix": "• Collision-Free Label Positioning (getSmartLabelAttrs):",
                "text": "A 2D bounding-box geometric collision engine that calculates 8 candidate compass offsets (N, NE, E, SE, S, SW, W, NW) to prevent text overlapping."
            },
            {
                "type": "paragraph",
                "prefix": "• Operational Theater Boundary Enforcement:",
                "text": "Filters out stale GPS coordinates from unrelated historical sessions (>3.5 km away) to maintain focus strictly on the active incident perimeter."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 12: SITE MAP, GEODETIC POSITIONING & GPS ENGINE
    # -----------------------------------------------------------------------
    {
        "title": "12. Site Map, Geodetic Positioning & GPS Engine Deep Dive",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The spatial engine converts raw WGS-84 GPS coordinates (Latitude, Longitude, Altitude) into pixel-accurate local Cartesian SVG and Leaflet coordinates."
            },
            {
                "type": "heading2",
                "text": "Coordinate Transformations & Navigation Controls"
            },
            {
                "type": "paragraph",
                "prefix": "• Geographic Origin Anchor:",
                "text": "Each scenario establishes a site_origin anchor (e.g. 30.5524° N, 79.1538° E for Himalayan Landslide). All sensor and victim offsets are geodetically computed relative to this datum."
            },
            {
                "type": "paragraph",
                "prefix": "• Interactive Pan & Zoom Engine:",
                "text": "Supports continuous mouse-wheel zoom, drag-to-pan, and double-click deep inspection."
            },
            {
                "type": "paragraph",
                "prefix": "• Auto Fit-All Theater Extents:",
                "text": "Calculates the dynamic bounding box encompassing all victims, teams, and sensors, auto-centering the viewport with a single click."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 13: HARDWARE & SENSOR STATION TELEMETRY MONITORING
    # -----------------------------------------------------------------------
    {
        "title": "13. Hardware & Sensor Station Telemetry Monitoring Deep Dive",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The Hardware module (hardware.html and hardware.js) provides physical layer observability."
            },
            {
                "type": "heading2",
                "text": "Telemetry Diagnostic Flow"
            },
            {
                "type": "paragraph",
                "text": "PHYSICAL HARDWARE NODE\n"
                        "    ↓\n"
                        "STATION REGISTRY & BATTERY STATUS\n"
                        "    ↓\n"
                        "TELEMETRY VOLTAGE & DROPOUT MONITOR\n"
                        "    ↓\n"
                        "DIAGNOSTIC HEALTH RATING (Nominal / Degraded / Offline)\n"
                        "    ↓\n"
                        "SCENARIO RELEVANCE CLASSIFICATION"
            },
            {
                "type": "heading2",
                "text": "Monitored Hardware Modalities"
            },
            {
                "type": "paragraph",
                "text": "1. Inclinometer & Biaxial Tiltmeters (Slope stability angles in degrees)\n"
                        "2. Tipping-Bucket Rain Gauges (Precipitation intensity in mm/h and cumulative mm)\n"
                        "3. Ultrasonic Water Level Transducers (Flood reservoir depths in cm)\n"
                        "4. FLIR LWIR Long-Wave Thermal Cameras (Sub-surface human heat signatures)\n"
                        "5. Optical YOLOv8 Video Feeds (Visible survivor detection and confidence)\n"
                        "6. Barometric Pressure Transducers (Atmospheric depression in hPa)\n"
                        "7. Gas & Smoke Multi-Sensors (Toxic gas concentrations and smoke density %)"
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 14: ADMIN & MASTER CONFIGURATION SUBSYSTEM
    # -----------------------------------------------------------------------
    {
        "title": "14. Admin & Master Configuration Management Subsystem",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The Admin subsystem provides administrative authority over master records, team formation, personnel registries, and scenario availability."
            },
            {
                "type": "heading2",
                "text": "Core Administrative Responsibilities"
            },
            {
                "type": "paragraph",
                "prefix": "• Personnel Registry Management:",
                "text": "Enroll responders, certify disaster specializations (Canine, Dive, High-Angle Rope, Hazmat, USAR), and update operational statuses."
            },
            {
                "type": "paragraph",
                "prefix": "• Tactical Team Assembly:",
                "text": "Create rescue teams, designate team leads, assign certified personnel, and define home base coordinates."
            },
            {
                "type": "paragraph",
                "prefix": "• Scenario Ledger Control:",
                "text": "Toggle disaster scenarios Active/Inactive to control which options appear in operational dispatch dropdowns."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 15: TESTING CONSOLE & SIMULATION SANDBOX
    # -----------------------------------------------------------------------
    {
        "title": "15. Testing Console & Multi-Disaster Simulation Sandbox",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The Testing Console (testing.html, testing-*.html, and js/testing*.js) is an exhaustive simulation sandbox for developers, QA engineers, instructors, and judges."
            },
            {
                "type": "heading2",
                "text": "Simulation Sandbox Capabilities"
            },
            {
                "type": "paragraph",
                "prefix": "• Step-by-Step Cycle Stepping:",
                "text": "Advance simulation cycles individually or at accelerated rates (1x, 2x, 5x, 10x) to observe Bayesian probability convergence."
            },
            {
                "type": "paragraph",
                "prefix": "• Synthetic Sensor Telemetry Injection:",
                "text": "Manually override sensor readings using interactive sliders to simulate extreme disaster threshold breaches (e.g. 50 mm/h rain, 12° tilt)."
            },
            {
                "type": "paragraph",
                "prefix": "• Sensor Degradation & Dropout Testing:",
                "text": "Simulate hardware failures, low battery dropouts, and packet loss to evaluate multi-sensor fusion resilience."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 16: COMPLETE END-TO-END USER JOURNEYS
    # -----------------------------------------------------------------------
    {
        "title": "16. End-to-End Operational User Journeys (Workflows A through K)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "This section traces the 11 comprehensive end-to-end user journeys supported across the RidgeWatch frontend architecture."
            },
            {
                "type": "heading2",
                "text": "Workflow A: Admin Creates a Custom Disaster Scenario"
            },
            {
                "type": "paragraph",
                "text": "1. Admin opens testing-add-scenario.html.\n"
                        "2. Enters scenario title, disaster category, geographic coordinates, and victim count.\n"
                        "3. Submits form; testing-add-scenario.js validates inputs and calls POST /admin/scenario/create.\n"
                        "4. System registers scenario in SQLite and redirects to Scenarios Ledger (testing-scenarios.html).\n"
                        "5. New scenario becomes immediately available across Dashboard and Scenarios catalog."
            },
            {
                "type": "heading2",
                "text": "Workflow B: Admin Enrolls a Certified Rescue Responder"
            },
            {
                "type": "paragraph",
                "text": "1. Admin opens testing-add-person.html.\n"
                        "2. Enters name, callsign, and selects certified disaster specializations (e.g. Avalanche, Landslide).\n"
                        "3. Submits form; testing-add-person.js validates and calls POST /admin/person/create.\n"
                        "4. Person is registered and appears in Personnel Directory (testing-persons.html)."
            },
            {
                "type": "heading2",
                "text": "Workflow C: Admin Assembles a Tactical Rescue Team"
            },
            {
                "type": "paragraph",
                "text": "1. Admin opens testing-add-team.html.\n"
                        "2. Enters team name (e.g. Team Delta), selects type, base coordinates, and checks certified unassigned personnel.\n"
                        "3. Submits form; testing-add-team.js calls POST /admin/team/create.\n"
                        "4. Team is formed and appears in Teams Directory (teams.html and testing-teams.html)."
            },
            {
                "type": "heading2",
                "text": "Workflow D: Commander Launches an Operational Disaster Scenario"
            },
            {
                "type": "paragraph",
                "text": "1. Commander opens Dashboard (index.html) or Scenarios Catalog (scenarios.html).\n"
                        "2. Clicks 'Launch Scenario' on Himalayan Landslide Crisis.\n"
                        "3. Frontend calls POST /scenario/start; simulator initializes sensor stations and victim positions.\n"
                        "4. Dashboard updates active disaster banner and starts live telemetry streaming."
            },
            {
                "type": "heading2",
                "text": "Workflow E: Sensing Platform Produces Live Telemetry"
            },
            {
                "type": "paragraph",
                "text": "1. Sensor simulator advances cycles; Inclinometers detect 9.5° tilt, rain gauges report 32 mm/h rain.\n"
                        "2. Hardware station (hardware.html) updates live gauges and turns warning badges orange.\n"
                        "3. Visual 3D (visual.html) streams particle telemetry pulses along data cables."
            },
            {
                "type": "heading2",
                "text": "Workflow F: AI Decision Center Derives Explainable Triage Decision"
            },
            {
                "type": "paragraph",
                "text": "1. Commander opens Logical AI Decision Center (logic.html).\n"
                        "2. Level 1 shows Current Risk: CRITICAL (78/100).\n"
                        "3. Level 2 highlights Soil Moisture and Tilt as Primary Modalities.\n"
                        "4. Level 3 displays Step 0–Step 9 mathematical calculations deriving Survival Probability Score (SPS 88.4%).\n"
                        "5. Level 4 recommends immediate dispatch of Search & Rescue Alpha."
            },
            {
                "type": "heading2",
                "text": "Workflow G: Emergency Hazard Alert Triggered & Audited"
            },
            {
                "type": "paragraph",
                "text": "1. Slope displacement breaches safety threshold; backend dispatches CRITICAL network alert.\n"
                        "2. Topbar notification dot illuminates; Alerts page (alerts.html) triggers audio alarm pulses.\n"
                        "3. Safety officer reviews alert details and clicks 'Acknowledge Alert' (POST /alerts/{id}/ack).\n"
                        "4. Alert transitions to Acknowledged state with recorded responder timestamp."
            },
            {
                "type": "heading2",
                "text": "Workflow H: Commander Dispatches Rescue Job on Tactical Map"
            },
            {
                "type": "paragraph",
                "text": "1. Commander opens Commander Hub (commander.html).\n"
                        "2. Tactical 2D map renders clustered victim pins and available rescue teams.\n"
                        "3. Commander clicks high-priority victim marker #VIC-01 and opens Job Dispatch modal.\n"
                        "4. System auto-filters eligible staff certified for Landslides; Commander assigns Team Alpha.\n"
                        "5. Tactical map draws animated blue route line connecting Team Alpha to Victim #VIC-01."
            },
            {
                "type": "heading2",
                "text": "Workflow I: Field Responder Receives Watch Notification & Executes Rescue"
            },
            {
                "type": "paragraph",
                "text": "1. Team Alpha member checks Watch interface (watch.html) on mobile device.\n"
                        "2. Screen displays high-contrast dispatch card: 'Assigned to Victim #VIC-01 · 140m NE'.\n"
                        "3. Responder taps 'Acknowledge Dispatch', transitioning status to EN ROUTE.\n"
                        "4. Upon reaching coordinates, responder taps 'Confirm Arrival', then 'Victim Rescued'.\n"
                        "5. Status transitions to ARRIVED / RESCUED in database and tactical map updates pin to green."
            },
            {
                "type": "heading2",
                "text": "Workflow J: Analytics Logs Operational Performance Metrics"
            },
            {
                "type": "paragraph",
                "text": "1. Operations Commander opens Analytics (analytics.html).\n"
                        "2. Selects 'Current Session' scope; KPI cards reflect 1 Session, 4 Detected, 4 Rescued, 100% Rescue Rate.\n"
                        "3. Average response time displays '1m 15s'; rescue trend chart draws complete completion bar.\n"
                        "4. Commander clicks 'CSV Export' to download complete mission audit log."
            },
            {
                "type": "heading2",
                "text": "Workflow K: Engineering Team Reviews 3D Digital Twin & Hardware State"
            },
            {
                "type": "paragraph",
                "text": "1. Hardware engineers open Visual 3D (visual.html).\n"
                        "2. Inspects physical 3D mast structures and rotates camera around solar battery stations.\n"
                        "3. Clicks Station #4 to verify battery voltage remaining at 12.6V after high-intensity transmission drill."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 17: FRONTEND DATA FLOW & STATE LIFECYCLE PATTERNS
    # -----------------------------------------------------------------------
    {
        "title": "17. Frontend Data Flow & State Lifecycle Patterns",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The RidgeWatch frontend strictly adheres to a unidirectional, reactive data-flow architecture across all 12 modules."
            },
            {
                "type": "heading2",
                "text": "Universal Frontend Lifecycle Pattern"
            },
            {
                "type": "paragraph",
                "text": "USER INTERACTION / TIMER PULSE\n"
                        "    ↓\n"
                        "CONTROLLER REQUEST ENGINE (fetchWithFallback via config.js)\n"
                        "    ↓\n"
                        "PARSED JSON OPERATIONAL PAYLOAD\n"
                        "    ↓\n"
                        "LOCAL STATE STORE UPDATE (state object)\n"
                        "    ↓\n"
                        "DATA INTEGRITY & VALIDATION FILTER (Zero fake data checks)\n"
                        "    ↓\n"
                        "DOM MUTATION & SVG / CANVAS RENDER (renderAll)\n"
                        "    ↓\n"
                        "VISUAL FEEDBACK & OPERATIONAL ACTION"
            },
            {
                "type": "callout",
                "title": "FAIL-SAFE DEGRADATION",
                "text": "When network disconnection occurs, the frontend gracefully activates state.isOffline, displaying 'OFFLINE / Backend Unreachable' status badges while preserving the last valid cached telemetry in memory."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 18: COMPREHENSIVE FILE RELATIONSHIP & DEPENDENCY MATRIX
    # -----------------------------------------------------------------------
    {
        "title": "18. Comprehensive File Relationship & Dependency Matrix",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The following master matrix cross-references every primary frontend file with its file type, core responsibility, primary user role, key output, and upstream dependencies."
            },
            {
                "type": "table",
                "headers": ["FILE NAME", "TYPE", "PRIMARY RESPONSIBILITY", "USER ROLE", "DEPENDENCIES"],
                "data": [
                    ["index.html", "HTML", "Executive Operational Dashboard", "Commander", "style.css, config.js, dashboard.js"],
                    ["dashboard.js", "JS", "Dashboard Telemetry Poller", "Commander", "config.js"],
                    ["visual.html", "HTML", "2D/3D/4D Digital Twin Canvas", "Engineer", "style.css, config.js, visual.js"],
                    ["visual.js", "JS", "Three.js 3D Rendering Engine", "Engineer", "config.js, Three.js"],
                    ["logic.html", "HTML", "AI Decision Center UI", "Triage Officer", "style.css, config.js, logic.js"],
                    ["logic.js", "JS", "Step 0–9 AI Calculation Engine", "Triage Officer", "config.js"],
                    ["commander.html", "HTML", "Tactical Command Center", "Commander", "style.css, config.js, commander.js"],
                    ["commander.js", "JS", "2D Map Clustering & Dispatch Engine", "Commander", "config.js"],
                    ["watch.html", "HTML", "Field Responder Smartwatch View", "Responders", "style.css, config.js, watch.js"],
                    ["watch.js", "JS", "Mobile Card & Triage Controller", "Responders", "config.js"],
                    ["alerts.html", "HTML", "Emergency Hazard Alert Center", "Safety Officer", "style.css, config.js, alerts.js"],
                    ["alerts.js", "JS", "Alert Poller & Audio Alarm Engine", "Safety Officer", "config.js"],
                    ["analytics.html", "HTML", "Performance Analytics Dashboard", "Commander", "style.css, config.js, analytics.js"],
                    ["analytics.js", "JS", "Scope Metrics & SVG Chart Engine", "Commander", "config.js"],
                    ["scenarios.html", "HTML", "Disaster Scenario Catalog", "Operator", "style.css, config.js, scenarios.js"],
                    ["scenarios.js", "JS", "Scenario Launcher Controller", "Operator", "config.js"],
                    ["victims.html", "HTML", "Survivor Roster & Vitals View", "Medical Lead", "style.css, config.js, victims.js"],
                    ["victims.js", "JS", "Survivor Triage Filter Controller", "Medical Lead", "config.js"],
                    ["teams.html", "HTML", "Rescue Teams Directory", "Logistics", "style.css, config.js, teams.js"],
                    ["teams.js", "JS", "Teams Roster View Controller", "Logistics", "config.js"],
                    ["hardware.html", "HTML", "Hardware Telemetry Monitor", "Technician", "style.css, config.js, hardware.js"],
                    ["hardware.js", "JS", "Hardware Diagnostic Controller", "Technician", "config.js"],
                    ["testing.html", "HTML", "Simulation Testing Sandbox", "Developer/QA", "style.css, config.js, testing-common.js, testing.js"],
                    ["testing.js", "JS", "Simulation Stepper & Telemetry Injector", "Developer/QA", "config.js, testing-common.js"],
                    ["testing-common.js", "JS", "Testing Shared Nav Injector", "All Testing", "config.js"],
                    ["style.css", "CSS", "Master Light White/Blue Theme", "All Pages", "Google Fonts"],
                    ["config.js", "JS", "API Base URL Gateway", "All Scripts", "None"],
                ],
                "widths": [1.2, 0.6, 2.0, 1.0, 1.6]
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 19: 6W COMPREHENSIVE ANALYSIS SUMMARY
    # -----------------------------------------------------------------------
    {
        "title": "19. 6W Comprehensive Analysis Summary",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Every file across the RidgeWatch frontend answers the fundamental 6W questions (What, Why, Who, Where, When, How). "
                        "Detailed individual file breakdowns are provided in Section 5 (HTML) and Section 6 (JavaScript). "
                        "The summary table below aggregates the overarching 6W matrix by core functional subsystem."
            },
            {
                "type": "table",
                "headers": ["MODULE", "WHAT?", "WHY?", "WHO?", "WHERE?", "HOW?"],
                "data": [
                    ["Dashboard", "Executive overview", "Immediate situational awareness", "Commander", "index.html", "Continuous REST polling"],
                    ["Visual", "3D Digital Twin", "Spatial hardware observability", "Engineers", "visual.html", "Three.js 60 FPS WebGL"],
                    ["Logical", "Explainable AI", "Cognitive transparency into triage", "Triage Lead", "logic.html", "Step 0–9 mathematical proofs"],
                    ["Commander", "Tactical theater", "Coordinate multi-team dispatches", "Commander", "commander.html", "2D spatial map clustering"],
                    ["Watch", "Mobile responder", "Glanceable field triage on wearable", "Field Crew", "watch.html", "High-contrast card views"],
                    ["Alerts", "Hazard ledger", "Life-safety audio-visual warnings", "Safety Officer", "alerts.html", "Web Audio API alarm pulses"],
                    ["Analytics", "Performance audit", "Evaluate rescue speed and rate", "Commander", "analytics.html", "Scope-filtered SVG charts"],
                    ["Hardware", "Station diagnostics", "Monitor battery and packet health", "Technicians", "hardware.html", "Live SVG gauge meters"],
                    ["Testing", "Simulation sandbox", "Validate logic without disaster", "QA / Judges", "testing.html", "Synthetic sensor injections"],
                ],
                "widths": [1.0, 1.1, 1.4, 1.0, 1.0, 1.0]
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 20: COMPONENT CRITICALITY & DEPENDENCY RANKING
    # -----------------------------------------------------------------------
    {
        "title": "20. Component Criticality & Dependency Ranking Analysis",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Frontend components are classified into three strict operational tiers based on their systemic impact on mission success."
            },
            {
                "type": "heading2",
                "text": "Tier 1: CRITICAL Components"
            },
            {
                "type": "paragraph",
                "text": "• js/config.js: Single point of failure for all network communication.\n"
                        "• css/style.css: Core visual design system and layout foundation.\n"
                        "• commander.html & commander.js: Tactical mission command and spatial dispatch engine.\n"
                        "• alerts.html & alerts.js: Emergency life-safety hazard notifications."
            },
            {
                "type": "heading2",
                "text": "Tier 2: IMPORTANT Components"
            },
            {
                "type": "paragraph",
                "text": "• index.html & dashboard.js: Main operational summary and quick launcher.\n"
                        "• logic.html & logic.js: AI explainability and Bayesian fusion calculations.\n"
                        "• analytics.html & analytics.js: Rescue performance reporting and historical audit.\n"
                        "• watch.html & watch.js: Field responder mobile dispatch client."
            },
            {
                "type": "heading2",
                "text": "Tier 3: SUPPORTING Components"
            },
            {
                "type": "paragraph",
                "text": "• visual.html & visual.js: 3D hardware digital twin and aesthetic simulator.\n"
                "• hardware.html & hardware.js: Physical sensor battery and diagnostic meters.\n"
                "• testing*.html & testing*.js: Developer sandbox, scenario authoring, and personnel forms."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 21: "IF THIS FILE FAILS" SYSTEMIC IMPACT ANALYSIS
    # -----------------------------------------------------------------------
    {
        "title": "21. 'If This File Fails' Systemic Impact & Resilience Analysis",
        "blocks": [
            {
                "type": "paragraph",
                "text": "This section evaluates the fault-tolerance and operational impact if specific frontend files fail to load or encounter runtime exceptions."
            },
            {
                "type": "table",
                "headers": ["FAILED FILE", "FAILURE SYMPTOM", "SYSTEMIC IMPACT", "MITIGATION STRATEGY"],
                "data": [
                    ["config.js", "API base undefined", "Complete network blackout across all pages", "Hardcoded relative path fallback ('')"],
                    ["style.css", "Unstyled HTML", "Broken layouts, unreadable tables", "Inline critical layout fallback tokens"],
                    ["commander.js", "Map fails to render", "Cannot dispatch teams or view locations", "Fallback to tabular Victims & Teams pages"],
                    ["alerts.js", "No audio alarms", "Responders unaware of new secondary hazards", "Persistent visual alert banners on topbar"],
                    ["analytics.js", "Charts unrendered", "No performance trend visibility", "Raw SQLite CSV export available via backend"],
                    ["visual.js", "WebGL canvas blank", "No 3D digital twin rendering", "System functions normally via 2D Commander"],
                    ["testing.js", "Sliders unresponsive", "Cannot inject synthetic test readings", "REST API injection via curl/Postman"],
                ],
                "widths": [1.1, 1.3, 2.0, 2.0]
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 22: ARCHITECTURAL RATIONALE
    # -----------------------------------------------------------------------
    {
        "title": "22. Architectural Rationale: Why This Frontend Architecture?",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The RidgeWatch frontend deliberately avoids heavy, opinionated single-page application frameworks (such as React, Angular, or Vue) in favor of modular vanilla HTML5, CSS3, and standard JavaScript ES6+."
            },
            {
                "type": "heading2",
                "text": "Core Rationale Justifications"
            },
            {
                "type": "paragraph",
                "prefix": "1. Zero Build-Step Dependency:",
                "text": "Emergency systems deployed in forward operating bases or air-gapped field servers cannot depend on external npm registries, Webpack bundling, or complex Node build pipelines. RidgeWatch runs instantly from any web browser or lightweight HTTP server."
            },
            {
                "type": "paragraph",
                "prefix": "2. Fault Isolation by Module:",
                "text": "Because each operational view operates as an independent HTML/JS document, a runtime error in Visual 3D will never crash the Incident Commander map or disable Emergency Alerts."
            },
            {
                "type": "paragraph",
                "prefix": "3. Sub-Second Cold Start Times:",
                "text": "Vanilla HTML5 delivers instantaneous page loads with minimal memory footprint on low-power ruggedized field tablets."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 23: THE COMPLETE SYSTEM FRONTEND STORY
    # -----------------------------------------------------------------------
    {
        "title": "23. The Complete System Frontend Story (End-to-End Narrative)",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The complete operational lifecycle of a disaster response operation unfolds seamlessly across the RidgeWatch frontend in a single interconnected narrative:"
            },
            {
                "type": "paragraph",
                "text": "1. SYSTEM INITIALIZATION & CONFIGURATION:\n"
                        "   Admin registers certified search-and-rescue personnel (testing-add-person.html) and forms specialized rescue units (testing-add-team.html).\n\n"
                        "2. DISASTER STRIKES & SCENARIO ACTIVATION:\n"
                        "   A major landslide occurs in the Himalayan sector. Commander launches the scenario from the Dashboard (index.html).\n\n"
                        "3. REAL-TIME SENSING & TELEMETRY STREAMING:\n"
                        "   Inclinometers and rain gauges stream live readings. Hardware dashboard (hardware.html) and Visual 3D (visual.html) track telemetry pulses.\n\n"
                        "4. AI COGNITIVE DECISION & FUSION:\n"
                        "   Logical AI Decision Center (logic.html) fuses multi-modal evidence across Steps 0–9, deriving a 88.4% Survival Probability Score.\n\n"
                        "5. EMERGENCY HAZARD ALERT DISPATCH:\n"
                        "   Secondary landslide risk triggers a CRITICAL network alert. Alerts module (alerts.html) sounds audible warning pulses.\n\n"
                        "6. TACTICAL COMMAND & MAP DISPATCH:\n"
                        "   Incident Commander (commander.html) inspects the clustered 2D tactical map and dispatches Team Alpha to Survivor #VIC-01.\n\n"
                        "7. FIELD RESCUE EXECUTION:\n"
                        "   Team Alpha responder checks mobile Watch client (watch.html), navigates to target coordinates, and confirms arrival.\n\n"
                        "8. OPERATIONAL AUDIT & PERFORMANCE REVIEW:\n"
                        "   Operations Commander reviews Analytics (analytics.html), verifying a 100% rescue success rate and 1m 15s average response speed."
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 24: IMPLEMENTATION STATUS & PARTIAL AREAS
    # -----------------------------------------------------------------------
    {
        "title": "24. Implementation Status, Compatibility Aliases & Partial Areas",
        "blocks": [
            {
                "type": "paragraph",
                "text": "In strict compliance with factual accuracy, this section identifies fully implemented operational modules versus compatibility aliases and partial features."
            },
            {
                "type": "table",
                "headers": ["FRONTEND COMPONENT", "IMPLEMENTATION STATUS", "TECHNICAL ASSESSMENT"],
                "data": [
                    ["index.html / dashboard.js", "FULLY IMPLEMENTED", "Complete polling, KPI rendering, mini-map, quick scenario trigger"],
                    ["visual.html / visual.js", "FULLY IMPLEMENTED", "Complete Three.js 3D digital twin, 2D schematic, 4D simulation"],
                    ["logic.html / logic.js", "FULLY IMPLEMENTED", "Complete Level 1–4 AI decision center, Step 0–9 mathematical proofs"],
                    ["commander.html / commander.js", "FULLY IMPLEMENTED", "Complete 2D map clustering, collision avoidance, job assignment drawer"],
                    ["watch.html / watch.js", "FULLY IMPLEMENTED", "Complete mobile responder view, vital signs card, acknowledgment button"],
                    ["alerts.html / alerts.js", "FULLY IMPLEMENTED", "Complete active alerts ledger, severity filtering, Web Audio alarm"],
                    ["analytics.html / analytics.js", "FULLY IMPLEMENTED", "Complete global scope filtering (Live to All-Time), SVG trend charts"],
                    ["hardware.html / hardware.js", "FULLY IMPLEMENTED", "Complete station health grid, battery meters, diagnostic telemetry"],
                    ["testing.html / testing*.js", "FULLY IMPLEMENTED", "Complete simulation sandbox, step controls, synthetic telemetry sliders"],
                    ["admin.html & admin-*.html", "COMPATIBILITY ALIAS", "Client-side redirect gateways routing legacy URLs to testing-*.html"],
                    ["admin.js & admin-*.js", "COMPATIBILITY PROXY", "Lightweight JavaScript wrappers delegating to testing-*.js controllers"],
                ],
                "widths": [1.8, 1.8, 2.8]
            }
        ]
    },

    # -----------------------------------------------------------------------
    # SECTION 25: FRONTEND ARCHITECTURE SUMMARY & CONCLUSION
    # -----------------------------------------------------------------------
    {
        "title": "25. Frontend Architecture Summary & Final Conclusions",
        "blocks": [
            {
                "type": "paragraph",
                "text": "The RIDGEWATCH frontend architecture delivers a robust, highly modular, and mission-critical emergency rescue interface. "
                        "By unifying real-time telemetry streaming, explainable AI cognitive decision modeling, dynamic 2D tactical map clustering, and immersive 3D digital twin visualization, "
                        "it equips disaster response teams with the tools needed to save lives in the critical golden hour."
            },
            {
                "type": "heading2",
                "text": "Summary of Frontend Achievements"
            },
            {
                "type": "paragraph",
                "prefix": "• 54 Verified Frontend Files:",
                "text": "Every HTML view, JavaScript controller, and CSS rule has been audited, verified, and conceptually documented."
            },
            {
                "type": "paragraph",
                "prefix": "• Zero Fake Data Mandate:",
                "text": "Strict mathematical relationships guarantee that all operational reporting reflects audited backend simulation states."
            },
            {
                "type": "paragraph",
                "prefix": "• Production Readiness:",
                "text": "Validated across full automated regression test suites (565 passing tests) and confirmed ready for mission evaluation, hackathon judging, and field deployment."
            },
            {
                "type": "callout",
                "title": "END OF TECHNICAL SPECIFICATION",
                "text": "RIDGEWATCH — AI-Based Multi-Disaster Survivor Detection & Rescue Coordination System. Frontend Architecture & Conceptual Documentation v2.0."
            }
        ]
    }
]
