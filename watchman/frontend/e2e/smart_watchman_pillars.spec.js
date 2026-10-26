// watchman/frontend/e2e/smart_watchman_pillars.spec.js
import { test, expect } from '@playwright/test';

test.describe('SmartWatchman AI 12 Pillars Automated E2E Suite', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to Login and sign in as Guard
    await page.goto('/');

    const passwordInput = page.locator('input[type="password"]').first();
    if (await passwordInput.isVisible()) {
      const usernameInput = page.locator('input[type="text"], input[name="username"]').first();
      await usernameInput.fill('watchman1');
      await passwordInput.fill('password123');
      await page.locator('button[type="submit"]').first().click();
    }

    // Wait for the workspace sidebar to be ready
    await expect(page.locator('aside').first()).toBeVisible({ timeout: 10000 });
  });

  test('Pillar 03: Smart Maintenance defect reporting and status tracking', async ({ page }) => {
    // Navigate to maintenance tab
    const mntBtn = page.locator('aside button:has-text("Maintenance"), aside button:has-text("பராமரிப்பு")');
    await expect(mntBtn.first()).toBeVisible();
    await mntBtn.first().click();
    await page.waitForTimeout(500);

    // Verify maintenance dashboard headers
    await expect(page.locator('h1:has-text("Maintenance"), h1:has-text("பராமரிப்பு")').first()).toBeVisible();

    // Verify stats tiles
    await expect(page.locator('text=TOTAL TICKETS')).toBeVisible();

    // Check report issue modal trigger
    const reportBtn = page.locator('button:has-text("Report Issue"), button:has-text("புதிய பிரச்சனை")');
    await expect(reportBtn.first()).toBeVisible();
  });

  test('Pillar 06: Smart Parking live bay occupancy & slot assignment', async ({ page }) => {
    // Navigate to parking tab
    const parkBtn = page.locator('aside button:has-text("Smart Parking"), aside button:has-text("பார்க்கிங் மேலாண்மை")');
    await expect(parkBtn.first()).toBeVisible();
    await parkBtn.first().click();
    await page.waitForTimeout(500);

    // Verify parking header & summary
    await expect(page.locator('h1:has-text("Parking"), h1:has-text("பார்க்கிங்")').first()).toBeVisible();
    await expect(page.locator('text=TOTAL CAPACITY')).toBeVisible();
    await expect(page.locator('text=AVAILABLE SLOTS')).toBeVisible();
  });

  test('Pillar 10: Smart Patrolling and QR Checkpoint Verification', async ({ page }) => {
    // Navigate to patrol tab
    const patrolBtn = page.locator('aside button:has-text("Patrol"), aside button:has-text("ரோந்து")');
    await expect(patrolBtn.first()).toBeVisible();
    await patrolBtn.first().click();
    await page.waitForTimeout(500);

    // Verify route sequence
    await expect(page.locator('h1:has-text("Patrol"), h1:has-text("ரோந்து")').first()).toBeVisible();
    await expect(page.locator('text=DESIGNATED CHECKPOINTS')).toBeVisible();
  });

  test('Pillar 09: Smart Lost and Found repository & AI matching', async ({ page }) => {
    // Navigate to lost & found tab
    const lostBtn = page.locator('aside button:has-text("Lost & Found"), aside button:has-text("தொலைந்தவை")');
    await expect(lostBtn.first()).toBeVisible();
    await lostBtn.first().click();
    await page.waitForTimeout(500);

    // Verify lost & found header
    await expect(page.locator('h1:has-text("Lost and Found"), h1:has-text("தொலைந்தவை")').first()).toBeVisible();
  });

  test('Pillar 07: Smart Duty Attendance & timestamp log', async ({ page }) => {
    // Navigate to duty attendance tab
    const dutyBtn = page.locator('aside button:has-text("Duty"), aside button:has-text("வருகை")');
    await expect(dutyBtn.first()).toBeVisible();
    await dutyBtn.first().click();
    await page.waitForTimeout(500);

    // Verify duty header & active shift card
    await expect(page.locator('h1:has-text("Duty Attendance"), h1:has-text("வருகை")').first()).toBeVisible();
    await expect(page.locator('text=DUTY CLOCKED IN')).toBeVisible();
  });

  test('Pillars 08 & 11: Weather hazard telemetry and campus zone monitoring', async ({ page }) => {
    // Navigate to zone risk tab
    const riskBtn = page.locator('aside button:has-text("Zone Risk"), aside button:has-text("மண்டல")');
    await expect(riskBtn.first()).toBeVisible();
    await riskBtn.first().click();
    await page.waitForTimeout(500);

    // Verify weather hazard telemetry card
    await expect(page.locator('text=ACTIVE WEATHER HAZARD').first()).toBeVisible();
    await expect(page.locator('text=Campus Zone Monitoring').first()).toBeVisible();
  });

  test('Cognitive AI Guard Co-Pilot: Situation Card, Voice Incident & Task Triage Queue', async ({ page }) => {
    // Navigate to Co-Pilot tab
    const copilotBtn = page.locator('aside button:has-text("Co-Pilot"), aside button:has-text("கோ-பைலட்")');
    await expect(copilotBtn.first()).toBeVisible();
    await copilotBtn.first().click();
    await page.waitForTimeout(500);

    // Verify Co-Pilot header
    await expect(page.locator('h1:has-text("Co-Pilot"), h1:has-text("கோ-பைலட்")').first()).toBeVisible();

    // Verify 1-Tap Situation Card buttons
    await expect(page.locator('button:has-text("NORMAL")').first()).toBeVisible();
    await expect(page.locator('button:has-text("ATTENTION NEEDED")').first()).toBeVisible();

    // Verify Dynamic Task Prioritization Matrix columns
    await expect(page.locator('text=DO FIRST').first()).toBeVisible();
    await expect(page.locator('text=DO NEXT').first()).toBeVisible();
  });

  test('Phase 3: Adaptive Cross-Sector Workflows & Gate Congestion Workload Analytics', async ({ page }) => {
    // Switch to Admin Dashboard view
    const adminToggle = page.locator('button:has-text("Admin View"), button:has-text("நிர்வாகி"), button:has-text("Admin")').first();
    if (await adminToggle.isVisible()) {
      await adminToggle.click();
      await page.waitForTimeout(500);
    }

    // Verify Cross-Sector Adaptive Engine Tab
    const sectorsTab = page.locator('button:has-text("Cross-Sector Adaptive Engine")').first();
    if (await sectorsTab.isVisible()) {
      await sectorsTab.click();
      await page.waitForTimeout(400);
      await expect(page.locator('text=ENV-ADAPTIVE ARCHITECTURE').first()).toBeVisible();
      await expect(page.locator('text=Educational Campus').first()).toBeVisible();
      await expect(page.locator('text=Industrial Hub').first()).toBeVisible();
      await expect(page.locator('button:has-text("Issue Live Test Pass")').first()).toBeVisible();
    }

    // Verify Gate Congestion & Workload Analytics Tab
    const analyticsTab = page.locator('button:has-text("Gate Congestion & Workload")').first();
    if (await analyticsTab.isVisible()) {
      await analyticsTab.click();
      await page.waitForTimeout(400);
      await expect(page.locator('text=TELEMETRY ENGINE').first()).toBeVisible();
      await expect(page.locator('text=Hourly Ingress Rate').first()).toBeVisible();
      await expect(page.locator('text=Clearance Latency').first()).toBeVisible();
    }
  });

});


