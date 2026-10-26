// e2e/portal.spec.js
import { test, expect } from '@playwright/test';

test.describe('Enterprise Portal Automated E2E Suite', () => {

  test('TC01: Landing Page loads with header, title, and welcome badge (Image 1)', async ({ page }) => {
    await page.goto('/');

    // Check navbar brand
    const brand = page.locator('.brand-text');
    await expect(brand).toContainText('Gavi');

    // Check hero welcome badge
    const badge = page.locator('.welcome-chip');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText('WELCOME TO GAVI TECHNOLOGIES WORKSPACE');

    // Check main hero title
    const heroTitle = page.locator('.hero-title');
    await expect(heroTitle).toBeVisible();
    await expect(heroTitle).toContainText('Gavi');

    // Check "MY APPS" CTA button
    const myAppsBtn = page.locator('#hero-btn-my-apps');
    await expect(myAppsBtn).toBeVisible();
  });

  test('TC02: Navigation to Launchpad via "MY APPS" CTA (Image 2)', async ({ page }) => {
    await page.goto('/');

    // Click MY APPS CTA
    await page.locator('#hero-btn-my-apps').click();

    // Verify hash changed
    await expect(page).toHaveURL(/.*#my-apps/);

    // Verify Launchpad header & title
    const launchpadTitle = page.locator('.launchpad-title');
    await expect(launchpadTitle).toBeVisible();
    await expect(launchpadTitle).toContainText('Your Launchpad');

    // Verify subtitle mentions apps
    const subtitle = page.locator('.launchpad-subtitle');
    await expect(subtitle).toContainText('apps ready to launch');
  });

  test('TC03: All 4 Core Apps and Add Apps squircle are rendered on Launchpad', async ({ page }) => {
    await page.goto('/#my-apps');

    // Check 4 core app squircles
    await expect(page.locator('#launch-app-face-recognition')).toBeVisible();
    await expect(page.locator('#launch-app-watchman')).toBeVisible();
    await expect(page.locator('#launch-app-disaster-management')).toBeVisible();
    await expect(page.locator('#launch-app-sms-gateway')).toBeVisible();

    // Check "+ Add apps" dotted squircle
    const addAppBtn = page.locator('#btn-add-app');
    await expect(addAppBtn).toBeVisible();
    await expect(addAppBtn).toContainText('Add apps');
  });

  test('TC04: Clicking an app opens the Launcher modal with port & roles info', async ({ page }) => {
    await page.goto('/#my-apps');

    // Click Watchman app squircle
    await page.locator('#launch-app-watchman').click();

    // Verify modal appears
    const modal = page.locator('.modal-content');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('CampusGuard Watchman');
    await expect(modal).toContainText('http://localhost:8080');

    // Verify isolated auth notice is displayed
    await expect(modal).toContainText('Isolated Authentication & Roles');

    // Close modal
    await modal.getByRole('button', { name: 'Cancel' }).click();
    await expect(modal).not.toBeVisible();
  });

  test('TC05: Add New App modal allows registering custom project', async ({ page }) => {
    await page.goto('/#my-apps');

    // Click "+ Add apps"
    await page.locator('#btn-add-app').click();

    // Verify modal form
    const modal = page.locator('.modal-content');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('Add New Application');

    // Fill new app form
    await page.fill('input[placeholder*="Library Management"]', 'Internal DevOps Dashboard');
    await page.fill('input[placeholder*="http://localhost"]', 'http://localhost:9090');
    await page.fill('textarea[placeholder*="Brief description"]', 'Automated cluster monitoring and container stats.');

    // Submit
    await page.click('button:has-text("Add to Launchpad")');

    // Verify modal closed
    await expect(modal).not.toBeVisible();

    // Verify new app appears on launchpad
    await expect(page.locator('.launchpad-wrapper')).toContainText('Internal DevOps Dashboard');
  });

});
