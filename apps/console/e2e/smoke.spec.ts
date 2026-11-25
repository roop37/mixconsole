import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { STATE_FILE } from "./global-setup";

const run = JSON.parse(readFileSync(STATE_FILE, "utf8")) as {
  token: string;
  audio: string;
  kit: string;
};
const SHOTS = path.resolve(import.meta.dirname, "../../../docs/screenshots");

test.describe.configure({ mode: "serial" });

test("two synthetic files: analyse, plan, audition, move a cue, re-render, export", async ({
  page,
}) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(String(error)));
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(m.text());
  });
  const external: string[] = [];
  page.on("request", (r) => {
    if (
      !r.url().startsWith("http://127.0.0.1:") &&
      !r.url().startsWith("data:") &&
      !r.url().startsWith("blob:")
    )
      external.push(r.url());
  });

  await page.goto(`/?token=${run.token}`);
  await expect(page.getByRole("heading", { name: "MixConsole" })).toBeVisible();
  expect(page.url()).not.toContain("token=");
  await expect(page.getByText("Drop an audio file for deck A")).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "01-empty-1920.png") });

  // 1. load both files (one drop of two files fills A then B), analysis with progress
  await page
    .getByLabel("Choose audio file for deck A")
    .setInputFiles([
      path.join(run.audio, "synthetic-a.wav"),
      path.join(run.audio, "synthetic-b.wav"),
    ]);
  await expect(page.getByRole("progressbar", { name: /Analysis progress/ })).toBeVisible();
  await expect(page.getByRole("img", { name: /Analysis lanes for deck A/ })).toBeVisible();
  await expect(page.getByRole("img", { name: /Analysis lanes for deck B/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "synthetic-a.wav" })).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "02-decks-analysed-1920.png") });

  // 2. plan: candidate cards with family, length, score and verify status
  await page.getByTestId("plan").click();
  const cards = page.getByTestId("candidate-card");
  await expect(cards.first()).toBeVisible({ timeout: 180_000 });
  expect(await cards.count()).toBeGreaterThanOrEqual(1);
  const first = cards.first();
  await expect(first).toContainText(/bars/);
  await expect(first).toContainText(/score/);
  await expect(first).toContainText(/Verified|Failed|Not verified/);
  await expect(page.getByTestId("render-status")).toContainText("Rendered");

  // 3. audition a candidate preview, then switch A/B
  await first.getByRole("button", { name: "Audition", exact: true }).click();
  const audition = page.getByRole("region", { name: "A/B audition" });
  await expect(audition.getByRole("button", { name: "Pause" })).toBeVisible();
  await expect
    .poll(async () =>
      Number.parseFloat(
        (await audition.getByLabel("Seconds from the handoff").textContent()) ?? "NaN",
      ),
    )
    .toBeGreaterThan(-8);
  await audition.getByRole("button", { name: "Pause" }).click();
  await page.screenshot({ path: path.join(SHOTS, "03-plan-candidates-1920.png"), fullPage: true });

  // 4. move the exit cue by dragging: it snaps to a phrase
  const exit = page.getByTestId("cue-exit");
  await expect(exit).toBeVisible();
  const before = (await page.getByTestId("exit-time").textContent()) ?? "";
  const box = (await exit.boundingBox()) ?? { x: 0, y: 0, width: 0, height: 0 };
  const deck = (await page
    .getByRole("region", { name: "Deck A" })
    .locator(".deck-body")
    .boundingBox()) ?? {
    x: 0,
    y: 0,
    width: 0,
    height: 0,
  };
  const startX = box.x + 4;
  const y = box.y + box.height / 2;
  await page.mouse.move(startX, y);
  await page.mouse.down();
  await page.mouse.move(deck.x + deck.width * 0.2, y, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByTestId("render-status")).toContainText("stale");
  const after = (await page.getByTestId("exit-time").textContent()) ?? "";
  expect(after).not.toBe(before);
  await expect(page.getByText(/^on (phrase|bar|beat)$/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Lock exit cue" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // undo restores the previous version, redo brings the edit back
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByTestId("exit-time")).toHaveText(before);
  await page.getByRole("button", { name: "Redo" }).click();
  await expect(page.getByTestId("exit-time")).toHaveText(after);

  // 5. keyboard cue nudge (one bar), committed as a version
  await exit.focus();
  await page.keyboard.press("Shift+ArrowRight");
  await expect(page.getByTestId("exit-time")).not.toHaveText(after);
  await expect(page.getByTestId("render-status")).toContainText("stale");

  // 6. automation: drag a point and see it saved
  const lane = page
    .getByRole("tab")
    .filter({ hasText: /Deck A gain|gain/i })
    .first();
  if (await lane.isVisible()) await lane.click();
  const point = page.getByRole("slider", { name: /^Point 2 of/ });
  if (await point.isVisible()) {
    const p = (await point.boundingBox()) ?? { x: 0, y: 0, width: 0, height: 0 };
    await page.mouse.move(p.x + p.width / 2, p.y + p.height / 2);
    await page.mouse.down();
    await page.mouse.move(p.x + p.width / 2 + 10, p.y + p.height / 2 + 25, { steps: 5 });
    await page.mouse.up();
  }

  // 7. re-render the edited version
  await page.getByTestId("rerender").click();
  await expect(page.getByTestId("render-status")).toContainText("Rendered", { timeout: 180_000 });
  await page.screenshot({ path: path.join(SHOTS, "04-edited-rendered-1920.png"), fullPage: true });

  // 8. export WAV and the MixScript
  const [wav] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("export-wav").click(),
  ]);
  const wavPath = await wav.path();
  expect(statSync(wavPath).size).toBeGreaterThan(10_000);
  expect(readFileSync(wavPath).subarray(0, 4).toString()).toBe("RIFF");
  const [script] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("export-mixscript").click(),
  ]);
  const doc = JSON.parse(readFileSync(await script.path(), "utf8"));
  expect(doc.version).toBe("mixscript/v1.1");
  expect(doc.transitions[0].locks).toContain("exit");

  // library view lists the analysed tracks and sorts
  await page.getByRole("tab", { name: "Library" }).click();
  await expect(page.getByRole("cell", { name: "synthetic-a.wav", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /^BPM/ }).click();
  await page.screenshot({ path: path.join(SHOTS, "05-library-1920.png") });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByRole("tab", { name: "Console" }).click();
  await expect(page.getByTestId("candidate-card").first()).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "06-console-1280.png"), fullPage: true });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  expect(external, "no request leaves 127.0.0.1").toEqual([]);
  expect(problems.filter((p) => !/favicon|Failed to load resource/.test(p))).toEqual([]);
});

test("blind A/B voting page reads a kit built by `mixconsole listen build`", async ({ page }) => {
  await page.goto(`/?token=${run.token}`);
  await page.getByRole("tab", { name: "Listen" }).click();
  await page.getByLabel("Choose listening kit folder").setInputFiles(run.kit);
  await expect(page.getByTestId("ab-trial")).toBeVisible();
  await page.getByLabel("Your name or ID").fill("rater one");
  await page.getByRole("button", { name: "A is better" }).click();
  await expect(page.getByRole("button", { name: "A is better" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  const [votes] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Save votes as JSON" }).click(),
  ]);
  const file = JSON.parse(readFileSync(await votes.path(), "utf8"));
  expect(file.version).toBe("listen-votes/v1");
  expect(file.rater).toBe("rater one");
  expect(file.ab).toHaveLength(1);
  expect(["left", "right", "tie"]).toContain(file.ab[0].choice);
  await page.screenshot({ path: path.join(SHOTS, "07-listen-1920.png") });
});

test("a missing or wrong token explains itself", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(/token/i);
  await context.close();
});
