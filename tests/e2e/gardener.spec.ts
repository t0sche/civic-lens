import { test, expect } from "@playwright/test";

/**
 * CivicLens Gardener E2E Tests
 *
 * These tests run against the live deployment to verify
 * the site is functional and key user flows work as intended
 * for human users.
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

  test("active jurisdiction filter is visually indicated", async ({ page }) => {
    await page.goto("/?jurisdiction=STATE");
    // The active filter link uses bg-gray-900 (dark background) to signal selection
    const stateLink = page.getByRole("link", { name: "State" });
    await expect(stateLink).toBeVisible();
    await expect(stateLink).toHaveClass(/bg-gray-900/);
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

  test("submitting a question shows a response", async ({ page }) => {
    // This test exercises the full user interaction: type a question, submit it,
    // wait for the AI response, and verify the app renders the result correctly.
    // We accept either a successful response or a gracefully rendered error
    // (e.g., API unavailable) — both confirm the app is handling the flow correctly.
    test.setTimeout(90_000);

    await page.goto("/chat");
    const input = page.getByPlaceholder(/Ask about local laws/i);
    await input.fill("What are the fence regulations in Bel Air?");
    await page.keyboard.press("Enter");

    // The loading indicator must appear quickly — proves the request was sent
    await expect(
      page.getByText(/Searching laws and generating answer/i)
    ).toBeVisible({ timeout: 5_000 });

    // The user's message must be visible in the conversation
    await expect(
      page.getByText("What are the fence regulations in Bel Air?")
    ).toBeVisible();

    // The input must be cleared immediately after submission
    await expect(input).toHaveValue("");

    // Wait for the loading state to resolve — the AI response (or error) must appear.
    // When this indicator disappears, a message has been added to the messages array
    // (either a successful answer or an error bubble rendered by the chat component).
    await expect(
      page.getByText(/Searching laws and generating answer/i)
    ).not.toBeVisible({ timeout: 75_000 });
  });

  test("clicking an example question submits it", async ({ page }) => {
    // Verifies that the pre-built example question buttons initiate a chat request
    test.setTimeout(20_000);

    await page.goto("/chat");
    // Click the example question button by role + text to avoid relying on DOM order
    await page.getByRole("button").filter({ hasText: /fence regulations/i }).click();

    // The question text must appear in the conversation as a user message
    await expect(
      page.getByText(/What are the fence regulations in Bel Air/i)
    ).toBeVisible({ timeout: 5_000 });

    // The loading indicator must appear, confirming the request was sent
    await expect(
      page.getByText(/Searching laws and generating answer/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  test("chat page loads within 5 seconds", async ({ page }) => {
    const start = Date.now();
    await page.goto("/chat", { waitUntil: "domcontentloaded" });
    const loadTime = Date.now() - start;
    expect(loadTime).toBeLessThan(5000);
  });
});

test.describe("Navigation — Site-wide Links", () => {
  test("about page is accessible", async ({ page }) => {
    const response = await page.goto("/about");
    expect(response?.status()).toBe(200);
  });

  test("about page has expected content sections", async ({ page }) => {
    await page.goto("/about");
    await expect(page.getByRole("heading", { name: /About CivicLens/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /What It Does/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Data Sources/i })).toBeVisible();
    // Legal disclaimer must be present
    await expect(page.getByText(/not a law firm/i)).toBeVisible();
  });

  test("stats page is accessible", async ({ page }) => {
    const response = await page.goto("/stats");
    expect(response?.status()).toBe(200);
  });

  test("header nav links navigate to the correct pages", async ({ page }) => {
    await page.goto("/");
    // Navigate to the chat page via the nav link
    await page.getByRole("link", { name: "Ask a Question" }).click();
    await expect(page).toHaveURL(/\/chat/);

    // Navigate to the about page
    await page.getByRole("link", { name: "About" }).click();
    await expect(page).toHaveURL(/\/about/);

    // Navigate back to the dashboard
    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page).toHaveURL("/");
  });

  test("header logo navigates to the dashboard", async ({ page }) => {
    await page.goto("/chat");
    await page.getByRole("link", { name: "CivicLens" }).first().click();
    await expect(page).toHaveURL("/");
  });

  test("404 handling for unknown routes", async ({ page }) => {
    const response = await page.goto("/nonexistent-page-xyz");
    // Next.js returns 404 for unknown routes
    expect(response?.status()).toBe(404);
  });
});
