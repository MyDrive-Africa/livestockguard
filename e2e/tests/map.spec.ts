import { test, expect } from '@playwright/test';

test.describe('Map Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('africa.mydrive@gmail.com');
    await page.getByLabel(/password/i).fill('demo123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/map/, { timeout: 10000 });
  });

  test('map container is rendered', async ({ page }) => {
    // MapLibre renders into a container
    const mapContainer = page.locator('.maplibregl-map');
    await expect(mapContainer).toBeVisible({ timeout: 15000 });
  });

  test('toolbar shows Live Map title', async ({ page }) => {
    await expect(page.getByText('Live Map')).toBeVisible();
  });

  test('layer toggle buttons are present', async ({ page }) => {
    await expect(page.getByRole('button', { name: /animals/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /geofences/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /trails/i })).toBeVisible();
  });

  test('tile source buttons are present', async ({ page }) => {
    await expect(page.getByRole('button', { name: /street/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /satellite/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /terrain/i })).toBeVisible();
  });

  test('draw fence button is present', async ({ page }) => {
    await expect(page.getByRole('button', { name: /draw fence/i })).toBeVisible();
  });

  test('status bar shows animal count', async ({ page }) => {
    // Wait for data to load
    await page.waitForTimeout(3000);
    await expect(page.getByText(/\d+ animals/)).toBeVisible();
  });

  test('status bar shows geofence count', async ({ page }) => {
    await page.waitForTimeout(3000);
    await expect(page.getByText(/\d+ geofences/)).toBeVisible();
  });
});
