// watchman/frontend/take_copilot_screenshot.js
import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1350 } });
  const page = await context.newPage();

  console.log('Navigating to http://localhost:5173/ ...');
  await page.goto('http://localhost:5173/');
  await page.waitForTimeout(1000);

  const passwordInput = page.locator('input[type="password"]').first();
  if (await passwordInput.isVisible()) {
    const usernameInput = page.locator('input[type="text"]').first();
    await usernameInput.fill('watchman1');
    await passwordInput.fill('password123');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(1000);
  }

  // Navigate to AI Guard Co-Pilot tab
  const copilotBtn = page.locator('aside button:has-text("Co-Pilot"), aside button:has-text("கோ-பைலட்")').first();
  await copilotBtn.click();
  await page.waitForTimeout(2000);

  const targetPath = 'C:/Users/sugan/.gemini/antigravity-ide/brain/532208da-2057-405b-a0dc-2d8fb08c1b28/ai_guard_copilot_complete_view.png';
  await page.screenshot({ path: targetPath, fullPage: false });
  console.log('SUCCESS: Complete view captured at', targetPath);

  await browser.close();
})();
