import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('login page renders correctly', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByRole('heading', { name: /livestockguard/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('shows error on invalid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.getByLabel(/email/i).fill('wrong@test.com');
    await page.getByLabel(/password/i).fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/invalid/i)).toBeVisible({ timeout: 5000 });
  });

  test('successful login redirects to map', async ({ page }) => {
    await page.goto('/login');

    await page.getByLabel(/email/i).fill('africa.mydrive@gmail.com');
    await page.getByLabel(/password/i).fill('demo123');
    await page.getByRole('button', { name: /sign in/i }).click();

    // Should redirect to /map
    await expect(page).toHaveURL(/\/map/, { timeout: 10000 });
  });

  test('unauthenticated user redirected to login', async ({ page }) => {
    // Clear any stored auth
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/map');
    await expect(page).toHaveURL(/\/login/);
  });

  test('theme toggle visible on login page', async ({ page }) => {
    await page.goto('/login');

    // Theme toggle should be present (light/dark/auto buttons)
    const themeButtons = page.locator('button[title]').filter({ hasText: /☀️|🌙|💻/ });
    await expect(themeButtons.first()).toBeVisible();
  });
});
