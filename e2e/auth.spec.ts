import { test, expect } from '@playwright/test';

test('redirects to login when unauthenticated', async ({ page }) => {
  await page.goto('/packages');
  await expect(page).toHaveURL(/login/);
  await expect(page.getByText('Admin Portal')).toBeVisible();
});
