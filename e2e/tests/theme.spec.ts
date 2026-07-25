import { test, expect } from '@playwright/test';

test.describe('Theme System', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('africa.mydrive@gmail.com');
    await page.getByLabel(/password/i).fill('demo123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/map/, { timeout: 10000 });
  });

  test('theme toggle is visible in sidebar', async ({ page }) => {
    const themeButtons = page.locator('button[title]').filter({ hasText: /☀️|🌙|💻/ });
    await expect(themeButtons.first()).toBeVisible();
  });

  test('switching to dark mode adds dark class to html', async ({ page }) => {
    // Click the dark mode button (🌙)
    await page.locator('button[title="Dark"]').click();

    // Verify <html> has class "dark"
    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');
  });

  test('switching to light mode removes dark class', async ({ page }) => {
    // First switch to dark
    await page.locator('button[title="Dark"]').click();

    // Then switch to light
    await page.locator('button[title="Light"]').click();

    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).not.toContain('dark');
  });

  test('theme persists across page reload', async ({ page }) => {
    // Switch to dark
    await page.locator('button[title="Dark"]').click();

    // Reload
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // Should still be dark
    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');
  });

  test('theme stored in localStorage', async ({ page }) => {
    await page.locator('button[title="Dark"]').click();

    const storedTheme = await page.evaluate(() => localStorage.getItem('lg-theme'));
    expect(storedTheme).toBe('dark');
  });
});
