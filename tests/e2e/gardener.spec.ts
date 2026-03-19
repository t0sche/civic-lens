import { test, expect } from "@playwright/test";

/**
 * CivicLens Gardener E2E Tests
 *
 * These tests run against the live deployment to verify
 * the site is functional and key user flows work.
 */

test.describe("Homepage — Legislative Tracker", () => {
  test("renders page title and header", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/CivicLens/i);
    await expect(page.getByRole("heading", { name: /Legislative Tracker/i })).toBeVisible();
  });

  test("jurisdiction filter buttons are present", async ({ page }) => {
    await page.goto("/");
    const filters = ["All", "State", "County", "Municipal"];
    for (const label of filters) {
      await expect(page.getByRole("link", { name: label })).toBeVisible();
    }
  });

  test("page shows legislative items or empty state", async ({ page }) => {
    await page.goto("/");
    // Either we see legislative item cards or the empty state message
    const hasItems = await page.locator('[class*="border-gray-200"]').first().isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/No legislative items found/i).isVisible().catch(() => false);
    expect(hasItems || hasEmptyState).toBe(true);
  });

  test("jurisdiction filter navigation works", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "State" }).click();
    await expect(page).toHaveURL(/jurisdiction=STATE/);
  });

  test("page loads within 5 seconds", async ({ page }) => {
    const start = Date.now();
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const loadTime = Date.now() - start;
    expect(loadTime).toBeLessThan(5000);
  });
});

test.describe("Chat Page — Ask About Local Law", () => {
  test("renders chat header and input", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByRole("heading", { name: /Ask About Local Law/i })).toBeVisible();
    await expect(page.getByPlaceholder(/Ask about local laws/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Ask/i })).toBeVisible();
  });

  test("example question buttons are displayed", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByText(/fence regulations/i)).toBeVisible();
    await expect(page.getByText(/home business/i)).toBeVisible();
    await expect(page.getByText(/noise ordinance/i)).toBeVisible();
  });

  test("input field accepts text", async ({ page }) => {
    await page.goto("/chat");
    const input = page.getByPlaceholder(/Ask about local laws/i);
    await input.fill("What are the parking rules?");
    await expect(input).toHaveValue("What are the parking rules?");
  });

  test("ask button is disabled when input is empty", async ({ page }) => {
    await page.goto("/chat");
    const askButton = page.getByRole("button", { name: /Ask/i });
    await expect(askButton).toBeDisabled();
  });

  test("ask button enables when text is entered", async ({ page }) => {
    await page.goto("/chat");
    const input = page.getByPlaceholder(/Ask about local laws/i);
    const askButton = page.getByRole("button", { name: /Ask/i });
    await input.fill("Test question");
    await expect(askButton).toBeEnabled();
  });

  test("chat page loads within 5 seconds", async ({ page }) => {
    const start = Date.now();
    await page.goto("/chat", { waitUntil: "domcontentloaded" });
    const loadTime = Date.now() - start;
    expect(loadTime).toBeLessThan(5000);
  });
});

test.describe("Navigation", () => {
  test("about page is accessible", async ({ page }) => {
    const response = await page.goto("/about");
    expect(response?.status()).toBe(200);
  });

  test("404 handling for unknown routes", async ({ page }) => {
    const response = await page.goto("/nonexistent-page-xyz");
    // Next.js returns 404 for unknown routes
    expect(response?.status()).toBe(404);
  });
});
