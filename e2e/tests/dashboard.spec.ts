import { test, expect } from '@playwright/test';

/**
 * Dashboard tests assume user is logged in.
 * Uses storageState or logs in before each test.
 */

test.describe('Dashboard Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('africa.mydrive@gmail.com');
    await page.getByLabel(/password/i).fill('demo123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/map/, { timeout: 10000 });
  });

  test('sidebar navigation links are visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: /map/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /animals/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /geofences/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /alerts/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /analytics/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /devices/i })).toBeVisible();
  });

  test('navigate to animals page', async ({ page }) => {
    await page.getByRole('link', { name: /animals/i }).click();
    await expect(page).toHaveURL(/\/animals/);
    await expect(page.getByRole('heading', { name: /animals/i })).toBeVisible();
  });

  test('navigate to alerts page', async ({ page }) => {
    await page.getByRole('link', { name: /alerts/i }).click();
    await expect(page).toHaveURL(/\/alerts/);
    await expect(page.getByRole('heading', { name: /alerts/i })).toBeVisible();
  });

  test('navigate to analytics page', async ({ page }) => {
    await page.getByRole('link', { name: /analytics/i }).click();
    await expect(page).toHaveURL(/\/analytics/);
    await expect(page.getByRole('heading', { name: /analytics/i })).toBeVisible();
  });

  test('navigate to devices page', async ({ page }) => {
    await page.getByRole('link', { name: /devices/i }).click();
    await expect(page).toHaveURL(/\/devices/);
    await expect(page.getByRole('heading', { name: /devices/i })).toBeVisible();
  });

  test('navigate to geofences page', async ({ page }) => {
    await page.getByRole('link', { name: /geofences/i }).click();
    await expect(page).toHaveURL(/\/geofences/);
    await expect(page.getByRole('heading', { name: /geofences/i })).toBeVisible();
  });
});
