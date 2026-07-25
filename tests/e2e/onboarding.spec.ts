import { expect, test } from "@playwright/test";

test("short seed shows a dismissable clarification prompt, never a hard block", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("What's the story about?").fill("A lighthouse");
  await expect(page.getByRole("status")).toContainText("short seed");
  const continueButton = page.getByRole("button", { name: "Continue" });
  await expect(continueButton).toBeDisabled();
  await page.getByLabel("Continue with this seed").check();
  await expect(continueButton).toBeEnabled();
});

test("no retired hidden-characteristic or hard-minimum patterns are present anywhere", async ({
  page,
}) => {
  await page.goto("/");
  const bodyText = await page.locator("body").innerText();
  for (const forbidden of ["hidden-row", "secret exists", "minimum 20 characters"]) {
    expect(bodyText.toLowerCase()).not.toContain(forbidden.toLowerCase());
  }
});

test("template picker discloses licensed-reference templates explicitly", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("What's the story about?").fill("A long enough seed to skip clarification.");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Licensed reference")).toBeVisible();
});
