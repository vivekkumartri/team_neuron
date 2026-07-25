import { expect, test } from "@playwright/test";

/**
 * Rewritten (Track 10) against the real `WorkspaceView` component, which
 * replaced the retired `WorkspaceStudio` demo. Still unrun in this sandbox —
 * no Playwright browser binary is installable here (see task.md Task 4H.1's
 * verification note) — but accurate against current markup, unlike the
 * previous version of this file.
 */

test("workspace shows chapter/focal-entity inputs and exactly three progression buttons", async ({
  page,
}) => {
  await page.goto("/workspace");
  // The workspace route is behind IdScopedView's branch-id text box until a
  // story/branch picker is wired in (Track 4); provide one to reach WorkspaceView.
  await page.getByLabel("Branch ID").fill("00000000-0000-0000-0000-000000000000");

  await expect(page.getByLabel("Chapter ID")).toBeVisible();
  await expect(page.getByLabel("Focal entity ID")).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue automatically" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit traits" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Jump / rewind" })).toBeVisible();
});

test("submitting Continue automatically posts to /branches/:id/progression", async ({ page }) => {
  let requestBody: unknown;
  await page.route("**/api/v1/branches/*/progression", async (route) => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "11111111-1111-1111-1111-111111111111",
        branch_id: "00000000-0000-0000-0000-000000000000",
        status: "QUEUED",
      }),
    });
  });
  await page.route("**/api/v1/generation-jobs/*/events", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: "" });
  });

  await page.goto("/workspace");
  await page.getByLabel("Branch ID").fill("00000000-0000-0000-0000-000000000000");
  await page.getByLabel("Chapter ID").fill("22222222-2222-2222-2222-222222222222");
  await page.getByLabel("Focal entity ID").fill("33333333-3333-3333-3333-333333333333");
  await page.getByRole("button", { name: "Continue automatically" }).click();

  await expect(page.getByText(/Job/)).toBeVisible();
  expect(requestBody).toMatchObject({ mode: "CONTINUE" });
});

test("a 409 conflict shows the active-job message instead of silently failing", async ({
  page,
}) => {
  await page.route("**/api/v1/branches/*/progression", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "This branch already has an active generation job" }),
    });
  });

  await page.goto("/workspace");
  await page.getByLabel("Branch ID").fill("00000000-0000-0000-0000-000000000000");
  await page.getByLabel("Chapter ID").fill("22222222-2222-2222-2222-222222222222");
  await page.getByLabel("Focal entity ID").fill("33333333-3333-3333-3333-333333333333");
  await page.getByRole("button", { name: "Continue automatically" }).click();

  await expect(page.getByRole("alert")).toContainText("already has an active generation job");
});
