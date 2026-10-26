# 🌐 CampusHub — Enterprise Multi-App Workspace & Launchpad

> Production-grade Multi-Project Workspace Gateway with Automated Playwright Testing, Docker Containerization, and GitHub Actions CI/CD Pipeline.

---

## 🏛️ Architecture Overview

The Enterprise Portal serves as a **Zero-Touch Gateway** to manage and launch all 4 campus projects while maintaining strict independent authentication and security isolation:

```
                          🌐 [ CampusHub Portal ]
                           (http://localhost:3000)
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
  [ Landing Page ]            [ Launchpad Grid ]         [ Application Gateway ]
  - Hero Scenic Backdrop      - 4 Squircle Apps          - Isolated Authentication
  - "MY APPS →" CTA Button    - "+ Add apps" Modal       - Target Ports & Workspaces
  - System Highlights         - Live Server Monitoring   - Deep-Link Launcher
                                     │
         ┌───────────────────┬───────┴───────────┬───────────────┐
         ▼                   ▼                   ▼               ▼
    App 1: Face AI       App 2: Watchman     App 3: Disaster     App 4: SMS Gateway
    (:5173 / :8000)      (:8080 / :3000)     (:5000 / :3002)     (:8082)
```

---

## 🚀 Quick Start (Local Development)

```bash
# 1. Navigate to portal directory
cd enterprise_portal

# 2. Install dependencies
npm install

# 3. Start local development server
npm run dev -- --port 3000
```

Open **[http://localhost:3000](http://localhost:3000)** in your browser.

---

## 🎭 Automated Testing with Playwright

Playwright is fully configured for automated End-to-End (E2E) testing across Chromium, Firefox, WebKit, and Mobile viewport emulation:

```bash
# 1. Install Playwright browser drivers (first time only)
npx playwright install chromium

# 2. Run automated test suite headlessly
npm run test:e2e

# 3. Run interactive Playwright UI mode (Visual Test Runner)
npm run test:e2e:ui

# 4. View detailed HTML test execution report
npm run test:e2e:report
```

### 📋 Test Cases Covered in `e2e/portal.spec.js`:
- **TC01**: Landing page renders with brand, scenic hero, and "+ WELCOME TO SAMPLE WORKSPACE" badge.
- **TC02**: Navigation between Landing Page and Launchpad via "MY APPS" CTA.
- **TC03**: All 4 core app squircles and "+ Add apps" button are verified in the grid.
- **TC04**: Launch modal displays application details, target port, and isolated auth notice.
- **TC05**: Dynamic custom app registration form updates the launchpad without page reload.

---

## 🐳 Docker Production Deployment

### Option A: Docker Compose (Single Command)
```bash
docker compose up -d --build
```
The portal will be running in a high-performance **Nginx** container on `http://localhost:3000`.

### Option B: Manual Docker Build
```bash
docker build -t campushub-portal:latest .
docker run -d -p 3000:80 --name campushub_portal campushub-portal:latest
```

---

## 🔄 GitHub Actions CI/CD Pipeline

The `.github/workflows/ci-cd.yml` pipeline triggers automatically on any push or pull request:

```
[ Git Push / PR ] 
       │
       ▼
 [ Stage 1: Quality Gate ]
   ├── Lint & Syntax Analysis (`oxlint`)
   ├── Production Build Verification (`vite build`)
   └── Playwright Automated E2E Testing (`playwright test`)
       │
       ▼
 [ Stage 2: Containerization ]
   ├── Multi-stage Docker Image Build
   └── Automated Security / Healthcheck Verification
       │
       ▼
 [ Stage 3: Continuous Deployment ]
   └── Production Release Deployment
```
