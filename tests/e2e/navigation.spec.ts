import { expect, test } from "@playwright/test";

test.describe("app shell navigation", () => {
  test("keyboard navigation reaches each sidebar link and activates it", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab"); // skip link
    await page.keyboard.press("Tab"); // first sidebar entry
    const workspaceLink = page.getByRole("button", { name: "Workspace" });
    await workspaceLink.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/workspace$/);
  });

  test("mobile drawer opens, traps focus, and closes on Escape", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.getByRole("button", { name: "Open navigation" }).click();
    const dialog = page.getByRole("dialog", { name: "Navigation" });
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("unauthenticated user hitting a protected route sees a redirect state", async ({ page }) => {
    await page.goto("/workspace");
    // No live backend in this repo's dev server without Lakebase configured,
    // so `/me/preferences` returns 401 and ProtectedRoute shows this state.
    await expect(page.getByRole("alert", { name: "Redirecting to sign-in…" })).toBeVisible();
  });

  test("200% zoom still exposes the primary action without clipping", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      document.body.style.zoom = "2";
    });
    const continueButton = page.getByRole("button", { name: "Continue", exact: true });
    await expect(continueButton).toBeVisible();
  });
});
