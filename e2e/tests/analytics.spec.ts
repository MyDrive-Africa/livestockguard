import { test, expect } from '@playwright/test';

test.describe('Analytics Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('africa.mydrive@gmail.com');
    await page.getByLabel(/password/i).fill('demo123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/map/, { timeout: 10000 });

    // Navigate to analytics
    await page.getByRole('link', { name: /analytics/i }).click();
    await page.waitForURL(/\/analytics/);
  });

  test('page title is visible', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /analytics/i })).toBeVisible();
  });

  test('date range picker is present', async ({ page }) => {
    await expect(page.getByRole('button', { name: '24h' })).toBeVisible();
    await expect(page.getByRole('button', { name: '7d' })).toBeVisible();
    await expect(page.getByRole('button', { name: '30d' })).toBeVisible();
  });

  test('summary cards are rendered', async ({ page }) => {
    await expect(page.getByText('Total Distance Today')).toBeVisible();
    await expect(page.getByText('Active Animals')).toBeVisible();
    await expect(page.getByText('Avg. Battery Level')).toBeVisible();
    await expect(page.getByText('Geofence Compliance')).toBeVisible();
  });

  test('charts sections are rendered', async ({ page }) => {
    await expect(page.getByText('Movement Distance')).toBeVisible();
    await expect(page.getByText('Activity Breakdown')).toBeVisible();
    await expect(page.getByText('Geofence Breaches')).toBeVisible();
    await expect(page.getByText('Avg. Battery Level (Today)')).toBeVisible();
  });

  test('compliance table is rendered', async ({ page }) => {
    await expect(page.getByText('Geofence Compliance Detail')).toBeVisible();
    await expect(page.getByText('Main Paddock')).toBeVisible();
    await expect(page.getByText('Road Boundary')).toBeVisible();
  });

  test('recharts SVGs are rendered', async ({ page }) => {
    // Recharts renders SVG elements inside ResponsiveContainer
    const svgs = page.locator('.recharts-wrapper svg');
    await expect(svgs.first()).toBeVisible({ timeout: 5000 });
  });

  test('date range toggle is interactive', async ({ page }) => {
    const btn24h = page.getByRole('button', { name: '24h' });
    await btn24h.click();

    // Button should now have the active styling (shadow-sm or font-medium)
    await expect(btn24h).toHaveClass(/font-medium|shadow/);
  });
});
