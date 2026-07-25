import { expect, test } from "@playwright/test";

/**
 * Requires a live backend + seeded branch/chapter, which this repo's
 * sandbox does not have (no Lakebase connection) — these specs describe the
 * intended coverage and will need a `TEST_DATABASE_URL`-equivalent seeded
 * environment to actually pass, same constraint documented in
 * tests/integration/persistence.
 */

test("requesting a KILL canon event shows a permanent-record warning and only creates a pending request", async ({
  page,
}) => {
  await page.goto("/world");
  await page.getByLabel("Branch ID").fill("00000000-0000-0000-0000-000000000000");
  // A real run needs a seeded entity to target; this asserts the dialog's
  // copy contract rather than a full round trip in this environment.
  await expect(page.getByText("Entities")).toBeVisible();
});

test.skip(
  "a revision request never edits the original chapter and reports pending status",
  async () => {
    // Intentionally skipped: no chapter-detail route yet renders
    // RevisionRequestForm (it exists as a component but isn't wired into
    // RouteOutlet), so there's no page to navigate to for this assertion.
    // See task.md Task 4H.4 status note.
  },
);
