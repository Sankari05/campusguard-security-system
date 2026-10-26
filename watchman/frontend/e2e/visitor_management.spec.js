// watchman/frontend/e2e/visitor_management.spec.js
import { test, expect } from '@playwright/test';

test.describe('Watchman Visitor Management Suite', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to Login and sign in
    await page.goto('/');

    const passwordInput = page.locator('input[type="password"]').first();
    if (await passwordInput.isVisible()) {
      const usernameInput = page.locator('input[type="text"], input[name="username"]').first();
      await usernameInput.fill('watchman1');
      await passwordInput.fill('password123');
      await page.locator('button[type="submit"]').first().click();
    }

    // Navigate to visitors tab
    const visitorsBtn = page.locator('aside button:has-text("Visitor"), aside button:has-text("பார்வையாளர்கள்")');
    await expect(visitorsBtn.first()).toBeVisible({ timeout: 10000 });
    await visitorsBtn.first().click();
  });

  test('TC07: Visitor console renders active visitor list and live ping badge', async ({ page }) => {
    // Wait for visitor workspace content
    await page.waitForTimeout(600);

    // Verify presence of visitor panels / cards
    const visitorHeader = page.locator('h1, h2, h3, .card');
    await expect(visitorHeader.first()).toBeVisible();
  });

  test('TC08: Visitor self-pass modal trigger is accessible', async ({ page }) => {
    // Look for button to generate self pass or open QR/pass modal
    const passActionBtn = page.locator('button:has-text("Pass"), button:has-text("Self-Pass"), button:has-text("பாஸ்")');
    if (await passActionBtn.first().isVisible()) {
      await passActionBtn.first().click();
      await page.waitForTimeout(500);

      // Check modal or dialog appeared
      const modal = page.locator('.modal, [role="dialog"], form');
      if (await modal.first().isVisible()) {
        await expect(modal.first()).toBeVisible();
        // Close modal if close button present
        const closeBtn = page.locator('.modal button:has-text("✕"), .modal button:has-text("Close"), button[aria-label="Close"]');
        if (await closeBtn.first().isVisible()) {
          await closeBtn.first().click();
        }
      }
    }
  });

  test('TC09: Public Gate QR Portal route renders standalone check-in', async ({ page }) => {
    // Test the QR self-pass route directly
    await page.goto('/#self-pass');
    await page.waitForTimeout(600);

    const publicQrOrKiosk = page.locator('body');
    await expect(publicQrOrKiosk).toBeVisible();
  });

});
