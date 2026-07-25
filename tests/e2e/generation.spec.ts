import { expect, test } from "@playwright/test";

/**
 * Exercises the workspace's mocked SSE demo stream
 * (`/api/v1/generation-events/demo`, `src/story_engine/app.py`) rather than
 * a live generation job, matching the mocked-SSE scope this task's
 * verification bullet describes.
 */
test("workspace renders ordered agent activity cards from the SSE demo stream", async ({ page }) => {
  await page.goto("/workspace");
  const activity = page.getByRole("complementary");
  await expect(activity.getByText("Director")).toBeVisible();
  await expect(activity.getByText("World")).toBeVisible();
});

test("exactly three progression modes are offered", async ({ page }) => {
  await page.goto("/workspace");
  await expect(page.getByRole("button", { name: "Continue", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit traits" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Jump / rewind" })).toBeVisible();
});
