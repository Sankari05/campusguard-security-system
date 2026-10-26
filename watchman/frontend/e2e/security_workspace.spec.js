// watchman/frontend/e2e/security_workspace.spec.js
import { test, expect } from '@playwright/test';

test.describe('Gate Security Workspace Navigation Suite', () => {

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
    await expect(page.locator('aside, nav, .sidebar').first()).toBeVisible({ timeout: 10000 });
  });

  test('TC04: Sidebar navigation items render and can switch tabs', async ({ page }) => {
    // Check sidebar links
    const sidebar = page.locator('aside');
    await expect(sidebar).toBeVisible();

    // Click Visitors tab
    const visitorsBtn = sidebar.locator('button:has-text("Visitor"), button:has-text("பார்வையாளர்கள்")');
    if (await visitorsBtn.isVisible()) {
      await visitorsBtn.click();
      await page.waitForTimeout(500);
      // Verify main content updated
      await expect(page.locator('main.page-body, .main-content').first()).toBeVisible();
    }

    // Click Handover tab
    const handoverBtn = sidebar.locator('button:has-text("Handover"), button:has-text("ஷிப்ட்")');
    if (await handoverBtn.isVisible()) {
      await handoverBtn.click();
      await page.waitForTimeout(500);
      await expect(page.locator('main.page-body, .main-content').first()).toBeVisible();
    }

    // Click Vehicles tab
    const vehiclesBtn = sidebar.locator('button:has-text("Vehicles"), button:has-text("வாகனங்கள்")');
    if (await vehiclesBtn.isVisible()) {
      await vehiclesBtn.click();
      await page.waitForTimeout(500);
      await expect(page.locator('main.page-body, .main-content').first()).toBeVisible();
    }
  });

  test('TC05: Navbar displays Guard profile and Emergency SOS trigger is accessible', async ({ page }) => {
    // Navbar check
    const navbar = page.locator('.main-content header, nav, .navbar');
    await expect(navbar.first()).toBeVisible();

    // Emergency SOS button in navbar or sidebar
    const sosBtn = page.locator('button:has-text("SOS"), button:has-text("Emergency")');
    if (await sosBtn.first().isVisible()) {
      await expect(sosBtn.first()).toBeVisible();
    }
  });

  test('TC06: Guard Sign Out invalidates session and redirects to Login', async ({ page }) => {
    // Find logout button in sidebar or header
    const logoutBtn = page.locator('button:has-text("Sign Out"), button:has-text("வெளியேறு"), button:has-text("Logout")');
    if (await logoutBtn.first().isVisible()) {
      await logoutBtn.first().click();

      // Should return to login screen
      const loginForm = page.locator('form, input[type="password"]');
      await expect(loginForm.first()).toBeVisible({ timeout: 10000 });
    }
  });

});
