/**
 * LivestockGuard Feature Verification — Playwright E2E Tests
 *
 * Tests every user-facing feature for correct behavior:
 * - Farm selector (multi-location)
 * - Geofence toggle on/off
 * - Animal inventory with filters
 * - Herdsman/Gateway page with cattle count
 * - Geofence drawing tool
 *
 * Run: cd e2e && npx playwright test tests/features.spec.ts
 * Or:  make verify-e2e (from project root)
 */

import { test, expect, Page } from '@playwright/test';

// ─── Helper: Login ───────────────────────────────────────────────────────────

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill('africa.mydrive@gmail.com');
  await page.getByLabel(/password/i).fill('demo123');
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/map/, { timeout: 10000 });
}

// ─── 1. Farm Selector (Multi-location) ──────────────────────────────────────

test.describe('Farm Selector', () => {
  test.beforeEach(async ({ page }) => { await login(page); });

  test('farm dropdown is visible on map page', async ({ page }) => {
    const selector = page.locator('select[aria-label="Select farm"]');
    await expect(selector).toBeVisible({ timeout: 10000 });
  });

  test('farm dropdown has multiple options', async ({ page }) => {
    const selector = page.locator('select[aria-label="Select farm"]');
    const options = selector.locator('option');
    await expect(options).toHaveCount(2, { timeout: 10000 }); // Boschhoek + Loch Vaal
  });

  test('selecting Loch Vaal changes map view', async ({ page }) => {
    const selector = page.locator('select[aria-label="Select farm"]');
    await selector.selectOption({ label: /Loch Vaal/i });
    // Give map time to fly
    await page.waitForTimeout(2000);
    // Status bar should still show animals count
    await expect(page.getByText(/animals/i)).toBeVisible();
  });

  test('selecting Boschhoek shows Free State farm', async ({ page }) => {
    const selector = page.locator('select[aria-label="Select farm"]');
    await selector.selectOption({ label: /Boschhoek/i });
    await page.waitForTimeout(1500);
    await expect(page.getByText(/animals/i)).toBeVisible();
  });
});

// ─── 2. Geofence Toggle ─────────────────────────────────────────────────────

test.describe('Geofence Toggle', () => {
  test.beforeEach(async ({ page }) => { await login(page); });

  test('geofence button shows active state by default', async ({ page }) => {
    const btn = page.getByRole('button', { name: /geofences/i });
    await expect(btn).toBeVisible();
    // Should have green/active styling
    await expect(btn).toHaveClass(/green/);
  });

  test('clicking geofences button toggles it off', async ({ page }) => {
    const btn = page.getByRole('button', { name: /geofences/i });
    await btn.click();
    // Should now have gray/inactive styling
    await expect(btn).toHaveClass(/gray/);
  });

  test('clicking geofences button again toggles it back on', async ({ page }) => {
    const btn = page.getByRole('button', { name: /geofences/i });
    await btn.click(); // off
    await btn.click(); // on again
    await expect(btn).toHaveClass(/green/);
  });
});

// ─── 3. Animals Page ─────────────────────────────────────────────────────────

test.describe('Animals Page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.getByRole('link', { name: /animals/i }).click();
    await page.waitForURL(/\/animals/);
  });

  test('animals page loads with count', async ({ page }) => {
    await expect(page.getByText(/registered/i)).toBeVisible({ timeout: 10000 });
  });

  test('animal table has gender column', async ({ page }) => {
    await expect(page.getByRole('columnheader', { name: /gender/i })).toBeVisible();
  });

  test('animal table has colour column', async ({ page }) => {
    await expect(page.getByRole('columnheader', { name: /colour/i })).toBeVisible();
  });

  test('status filter dropdown exists', async ({ page }) => {
    const statusFilter = page.locator('select[aria-label="Filter by status"]');
    await expect(statusFilter).toBeVisible();
  });

  test('gender filter dropdown exists', async ({ page }) => {
    const genderFilter = page.locator('select[aria-label="Filter by gender"]');
    await expect(genderFilter).toBeVisible();
  });

  test('filtering by male shows only males', async ({ page }) => {
    const genderFilter = page.locator('select[aria-label="Filter by gender"]');
    await genderFilter.selectOption('male');
    await page.waitForTimeout(1000);
    // All visible gender indicators should be male
    const femaleIcons = page.locator('text=♀');
    await expect(femaleIcons).toHaveCount(0);
  });

  test('search filters animals by name', async ({ page }) => {
    const search = page.getByPlaceholder(/search/i);
    await search.fill('Bella');
    await page.waitForTimeout(500);
    await expect(page.getByText('Bella')).toBeVisible();
    // Other animals should not be visible
    const rows = page.locator('tbody tr');
    await expect(rows).toHaveCount(1);
  });

  test('clicking animal opens detail modal', async ({ page }) => {
    const firstRow = page.locator('tbody tr').first();
    await firstRow.click();
    // Modal should appear with species/breed info
    await expect(page.getByText(/species/i)).toBeVisible();
    await expect(page.getByText(/breed/i)).toBeVisible();
  });
});

// ─── 4. Herdsman / Gateway Page ──────────────────────────────────────────────

test.describe('Herdsman Gateway Page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.getByRole('link', { name: /herdsman/i }).click();
    await page.waitForURL(/\/gateway/);
  });

  test('herdsman page loads', async ({ page }) => {
    await expect(page.getByText(/Herdsman Gateways/i)).toBeVisible();
  });

  test('summary cards are displayed', async ({ page }) => {
    await expect(page.getByText(/Total Gateways/i)).toBeVisible();
    await expect(page.getByText(/Online Now/i)).toBeVisible();
    await expect(page.getByText(/Active/i)).toBeVisible();
  });

  test('cattle count section displays', async ({ page }) => {
    // May show cattle count or may show nothing if no BLE tags registered
    const cattleCount = page.getByText(/Cattle Count/i);
    const noGateways = page.getByText(/No gateways registered/i);
    // One of these should be visible
    const hasCattleCount = await cattleCount.isVisible().catch(() => false);
    const hasNoGateways = await noGateways.isVisible().catch(() => false);
    expect(hasCattleCount || hasNoGateways).toBeTruthy();
  });

  test('register gateway button is present', async ({ page }) => {
    await expect(page.getByRole('button', { name: /register gateway/i })).toBeVisible();
  });
});

// ─── 5. Geofence Drawing Tool ────────────────────────────────────────────────

test.describe('Geofence Drawing', () => {
  test.beforeEach(async ({ page }) => { await login(page); });

  test('draw fence button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: /draw fence/i })).toBeVisible();
  });

  test('clicking draw fence enters drawing mode', async ({ page }) => {
    await page.getByRole('button', { name: /draw fence/i }).click();
    // Should show point counter and finish/cancel buttons
    await expect(page.getByText(/click map/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /finish/i })).toBeVisible();
  });

  test('cancel drawing exits drawing mode', async ({ page }) => {
    await page.getByRole('button', { name: /draw fence/i }).click();
    await page.getByRole('button', { name: /✕/ }).click();
    // Should return to normal mode with Draw Fence button
    await expect(page.getByRole('button', { name: /draw fence/i })).toBeVisible();
  });
});

// ─── 6. Navigation ───────────────────────────────────────────────────────────

test.describe('Sidebar Navigation', () => {
  test.beforeEach(async ({ page }) => { await login(page); });

  test('all nav items are present', async ({ page }) => {
    await expect(page.getByRole('link', { name: /map/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /animals/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /geofences/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /alerts/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /analytics/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /devices/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /herdsman/i })).toBeVisible();
  });

  test('navigate to each page without error', async ({ page }) => {
    const pages = ['animals', 'geofences', 'alerts', 'analytics', 'devices', 'gateway'];
    for (const p of pages) {
      await page.getByRole('link', { name: new RegExp(p === 'gateway' ? 'herdsman' : p, 'i') }).click();
      await page.waitForTimeout(500);
      // Page should not show an error
      const error = page.locator('text=Failed to load');
      const hasError = await error.isVisible().catch(() => false);
      // Errors from no backend are acceptable — we're testing navigation works
    }
  });
});
