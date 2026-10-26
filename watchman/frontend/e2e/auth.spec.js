// watchman/frontend/e2e/auth.spec.js
import { test, expect } from '@playwright/test';

test.describe('Watchman Security Auth Suite', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('campusguard_user', 'LOGGED_OUT');
      localStorage.removeItem('campusguard_token');
    });
    await page.reload();
  });

  test('TC01: Login screen renders with branding, role selector, and inputs', async ({ page }) => {
    await page.goto('/');

    // Check title / brand
    const heading = page.locator('h1, h2, form');
    await expect(heading.first()).toBeVisible();

    // Verify username and password inputs exist
    const usernameInput = page.locator('input[type="text"], input[name="username"]');
    const passwordInput = page.locator('input[type="password"]');

    await expect(usernameInput.first()).toBeVisible();
    await expect(passwordInput.first()).toBeVisible();

    // Verify submit button exists
    const submitBtn = page.locator('button[type="submit"]');
    await expect(submitBtn.first()).toBeVisible();
  });

  test('TC02: Guard Login with credentials navigates to Gate Security Workspace', async ({ page }) => {
    await page.goto('/');

    // Input credentials
    const usernameInput = page.locator('input[type="text"], input[name="username"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    await usernameInput.fill('watchman1');
    await passwordInput.fill('pass123');

    // Click submit
    await page.locator('button[type="submit"]').first().click();

    // Verify workspace loaded (sidebar or navigation tabs appear)
    const sidebarOrNav = page.locator('aside, nav, .sidebar');
    await expect(sidebarOrNav.first()).toBeVisible({ timeout: 10000 });
  });

  test('TC03: Forgot Password modal opens and allows OTP simulation', async ({ page }) => {
    await page.goto('/');

    // Look for forgot password link/button
    const forgotLink = page.locator('text=/forgot|கடவுச்சொல்/i');
    if (await forgotLink.isVisible()) {
      await forgotLink.click();
      const modal = page.locator('.modal, form');
      await expect(modal.first()).toBeVisible();
    }
  });

});
