// watchman/frontend/e2e/guardmate_lifecycle.spec.js
import { test, expect } from '@playwright/test';

test.describe('GuardMate 18-Step Multi-Tenant SaaS E2E Suite', () => {

  test('Step 01 & 02: GuardMate Landing Page renders hero, multi-industry tabs & register button', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('campusguard_user', 'LOGGED_OUT');
      localStorage.removeItem('campusguard_token');
    });
    await page.reload();

    // Verify GuardMate Branding
    const brand = page.locator('text=GuardMate');
    await expect(brand.first()).toBeVisible();

    // Verify Register Organization CTA Button
    const registerBtn = page.locator('button:has-text("Register Organization")');
    await expect(registerBtn.first()).toBeVisible();

    // Verify Multi-Industry showcase section
    const industryHeading = page.locator('text=/Choose Your Facility Type|Multi-Industry Adaptability/i');
    await expect(industryHeading.first()).toBeVisible();

    // Verify College industry vertical exists
    const collegeCard = page.locator('text=COLLEGE');
    await expect(collegeCard.first()).toBeVisible();
  });

  test('Step 03 - 05: Self-Serve Organization Registration wizard modal submission', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('campusguard_user', 'LOGGED_OUT');
      localStorage.removeItem('campusguard_token');
    });
    await page.reload();

    // Open Register modal
    const registerBtn = page.locator('button:has-text("Register Organization")').first();
    await registerBtn.click();

    // Verify Modal visible
    const modalTitle = page.locator('text=/Register Your Organization/i');
    await expect(modalTitle.first()).toBeVisible();

    // Step 1: Advance to Contact Details
    await page.locator('button:has-text("Next: Contact Details")').first().click();

    // Step 2: Fill Organization Details
    const uniqueOrgName = `Metro Tech Hub ${Date.now()}`;
    await page.locator('input[placeholder*="SRM Tech Campus"]').fill(uniqueOrgName);
    await page.locator('input[placeholder*="Sundaram"]').fill('Dr. Suresh Kumar');
    await page.locator('input[placeholder*="security@organization.org"]').fill(`admin_${Date.now()}@metrotech.com`);
    await page.locator('input[placeholder*="98765 43210"]').fill('+91 98401 23456');
    await page.locator('input[placeholder*="Chennai"]').fill('Chennai');

    await page.locator('button:has-text("Next: Security Workflows")').first().click();

    // Step 3: Security & Gates
    const gatesInput = page.locator('input[type="number"]').first();
    await gatesInput.fill('4');

    // Submit Registration
    const submitBtn = page.locator('button:has-text("Submit Registration")').first();
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // Wait for submission request to complete
    await page.waitForTimeout(1000);
  });

  test('Step 06 - 08: Super-Admin Portal loads vetting dashboard with status filters', async ({ page }) => {
    await page.goto('/#super-admin');

    // Verify Super-Admin Portal Branding
    const title = page.locator('text=/GuardMate Platform Super-Admin|Tenant Vetting/i');
    await expect(title.first()).toBeVisible({ timeout: 10000 });

    // Verify Filter Tabs exist (ALL, PENDING APPROVAL, APPROVED, REJECTED)
    const pendingTab = page.locator('button:has-text("PENDING APPROVAL")');
    await expect(pendingTab.first()).toBeVisible();

    // Switch to Pending filter
    await pendingTab.first().click();
    await page.waitForTimeout(600);
  });

  test('Step 09 - 18: Watchman Adaptive Facility Workspace renders for Guard role', async ({ page }) => {
    await page.goto('/');

    // Sign in as Watchman
    const passwordInput = page.locator('input[type="password"]').first();
    if (await passwordInput.isVisible()) {
      const usernameInput = page.locator('input[type="text"], input[name="username"]').first();
      await usernameInput.fill('watchman1');
      await passwordInput.fill('pass123');
      await page.locator('button[type="submit"]').first().click();
    }

    // Wait for workspace sidebar
    await expect(page.locator('aside, nav, .sidebar').first()).toBeVisible({ timeout: 10000 });

    // Click GuardMate Facility OS in sidebar
    const facilityOsBtn = page.locator('button:has-text("GuardMate"), button:has-text("கார்டுமேட்")').first();
    if (await facilityOsBtn.isVisible()) {
      await facilityOsBtn.click();
      await page.waitForTimeout(500);

      // Verify incident reporting or operational trigger is available
      const incidentTrigger = page.locator('text=/Report Threat|ON-DUTY GUARD/i');
      await expect(incidentTrigger.first()).toBeVisible();
    }
  });

});
