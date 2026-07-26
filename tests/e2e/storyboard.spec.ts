import { expect, test } from "@playwright/test";

const branchId = "00000000-0000-0000-0000-000000000000";
const chapterId = "11111111-1111-1111-1111-111111111111";

test("creates a storyboard and preserves the original dialogue", async ({ page }) => {
  await page.addInitScript(({ branch, job }) => {
    localStorage.setItem("story-engine-active-branch", branch);
    localStorage.setItem("story-engine-active-job", job);
    localStorage.setItem(`story-engine-focal-entity-${branch}`, "22222222-2222-2222-2222-222222222222");
  }, { branch: branchId, job: "33333333-3333-3333-3333-333333333333" });

  await page.route("**/api/v1/me/preferences", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  await page.route("**/api/v1/branches/*/cast-members", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{ entity_id: "22222222-2222-2222-2222-222222222222", name: "Mira", role: "PROTAGONIST" }]),
    });
  });
  await page.route("**/api/v1/branches/*/chapters", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{ id: chapterId, chapter_index: 1, status: "PUBLISHED", published_at: null }]),
    });
  });
  await page.route("**/api/v1/me/quota", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/generation-jobs/*/events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        'event: generation-progress\ndata: {"sequence":1,"summary":"Published","agent":"director","recipient_agent":null,"status":"PUBLISHED","entity_id":null}\n\n',
        "event: generation-complete\ndata: {}\n\n",
      ].join(""),
    });
  });
  await page.route(`**/api/v1/chapters/${chapterId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: chapterId,
        branch_id: branchId,
        chapter_index: 1,
        status: "PUBLISHED",
        published_at: null,
        scenes: [{
          scene_index: 1,
          summary: "The lighthouse went dark.",
          dialogue: [{ line_index: 1, speaker_entity_id: "22222222-2222-2222-2222-222222222222", line_text: "The light went dark." }],
        }],
        choices: [],
      }),
    });
  });

  let storyboardCreated = false;
  await page.route(`**/api/v1/chapters/${chapterId}/storyboard`, async (route) => {
    if (route.request().method() === "POST") {
      storyboardCreated = true;
      await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ job_id: "44444444-4444-4444-4444-444444444444", chapter_id: chapterId, status: "QUEUED", scenes: [], error_message: null }) });
      return;
    }
    if (!storyboardCreated) {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Storyboard not created" }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "44444444-4444-4444-4444-444444444444",
        chapter_id: chapterId,
        status: "SUCCEEDED",
        error_message: null,
        scenes: [{
          scene_number: 1,
          status: "SUCCEEDED",
          image_url: "/api/v1/storyboard-assets/55555555-5555-5555-5555-555555555555",
          location: "lighthouse tower",
          action: "investigate the dark beacon",
          emotion: "tense",
          characters: [{ entity_id: "22222222-2222-2222-2222-222222222222", name: "Mira", reference_asset_id: "66666666-6666-6666-6666-666666666666" }],
          dialogue: [{ line_number: 1, speaker_entity_id: "22222222-2222-2222-2222-222222222222", speaker_name: "Mira", line_text: "The light went dark." }],
        }],
      }),
    });
  });

  await page.goto("/workspace");
  await page.getByLabel("Branch ID").fill(branchId);
  await expect(page.getByRole("button", { name: "Create comic storyboard" })).toBeVisible();
  await page.getByRole("button", { name: "Create comic storyboard" }).click();
  await expect(page.getByRole("region", { name: "Comic storyboard" })).toBeVisible();
  await expect(page.getByText("Mira:", { exact: true })).toBeVisible();
  await expect(page.getByText("The light went dark.")).toBeVisible();
});
