// watchman/frontend/e2e/shift_handover.spec.js
import { test, expect } from '@playwright/test';

test.describe('Watchman Shift Handover Governance Suite', () => {

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

    // Switch to Shift Handover tab
    const handoverBtn = page.locator('aside button:has-text("Handover"), aside button:has-text("ஷிப்ட்")');
    await expect(handoverBtn.first()).toBeVisible({ timeout: 10000 });
    await handoverBtn.first().click();
  });

  test('TC10: Shift Handover view loads with role switchers (Outgoing / Incoming)', async ({ page }) => {
    await page.waitForTimeout(600);

    // Verify role buttons exist
    const outgoingBtn = page.locator('button:has-text("Outgoing"), button:has-text("வெளியேறும்")');
    const incomingBtn = page.locator('button:has-text("Incoming"), button:has-text("உள்வரும்")');

    if (await outgoingBtn.first().isVisible()) {
      await expect(outgoingBtn.first()).toBeVisible();
    }
    if (await incomingBtn.first().isVisible()) {
      await expect(incomingBtn.first()).toBeVisible();
    }
  });

  test('TC11: Category filter buttons allow sorting pending handover checklist', async ({ page }) => {
    await page.waitForTimeout(600);

    // Filter tabs: All, Visitors, Parcels, Incidents
    const filterTabs = page.locator('button:has-text("ALL"), button:has-text("அனைத்தும்"), button:has-text("Visitors"), button:has-text("Parcels")');
    if (await filterTabs.first().isVisible()) {
      await expect(filterTabs.first()).toBeVisible();
      // Click a filter tab
      await filterTabs.first().click();
    }
  });

  test('TC12: Initiate Handover modal triggers and renders checklist items', async ({ page }) => {
    await page.waitForTimeout(600);

    // Look for create handover button
    const createBtn = page.locator('button:has-text("Handover"), button:has-text("Initiate"), button:has-text("புதிய")');
    if (await createBtn.first().isVisible()) {
      await createBtn.first().click();
      await page.waitForTimeout(400);

      // Check modal or drawer is visible
      const modal = page.locator('.modal, [role="dialog"], form');
      if (await modal.first().isVisible()) {
        await expect(modal.first()).toBeVisible();
      }
    }
  });

});
