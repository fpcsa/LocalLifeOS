import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

const baseUrl = process.env.LOCALLIFE_WEB_URL || "http://127.0.0.1:3000";
const executablePath = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const outputDirectory = process.env.BROWSER_SMOKE_OUTPUT || path.join(process.cwd(), "data", "browser-smoke-artifacts");
const routes = ["/", "/tasks", "/calendar", "/notes", "/finance", "/goals", "/commitments", "/capacity", "/scenarios", "/timeline", "/imports", "/automation", "/settings"];
const viewports = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "tablet", width: 768, height: 900 },
  { name: "compact", width: 375, height: 812 },
];
const runId = Date.now().toString(36);
const taskName = `Browser smoke task ${runId}`;
const noteName = `Browser smoke note ${runId}`;
const accountName = `Browser smoke account ${runId}`;

function requireState(condition, message) {
  if (!condition) throw new Error(message);
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({ executablePath, headless: true });
const report = [];

try {
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
    const page = await context.newPage();
    const runtimeErrors = [];
    const externalRequests = [];
    let expectOfflineNetworkErrors = false;
    page.on("pageerror", (error) => runtimeErrors.push(`${page.url()}: ${error.message}`));
    page.on("console", (message) => {
      if (
        message.type() === "error" &&
        !(expectOfflineNetworkErrors && message.text().includes("ERR_INTERNET_DISCONNECTED"))
      ) {
        runtimeErrors.push(`${page.url()}: ${message.text()}`);
      }
    });
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (["http:", "https:"].includes(url.protocol) && !["127.0.0.1", "localhost", "::1"].includes(url.hostname)) externalRequests.push(request.url());
    });

    for (const route of routes) {
      const response = await page.goto(`${baseUrl}${route}`, { waitUntil: "networkidle" });
      requireState(response?.ok(), `${viewport.name} ${route} returned ${response?.status()}`);
      await page.locator("main").waitFor();
      requireState(await page.getByText("This route failed to render").count() === 0, `${viewport.name} ${route} hit the route error boundary`);
      requireState(await page.getByText("Couldn't load this view").count() === 0, `${viewport.name} ${route} rendered a query error state`);
      const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
      requireState(overflow <= 1, `${viewport.name} ${route} has ${overflow}px horizontal page overflow`);
      report.push(`${viewport.name} ${route}: ok`);
    }

    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.keyboard.press("Control+K");
    await page.getByRole("dialog", { name: "Command palette" }).waitFor();
    await page.getByLabel("Search and navigate").fill("Tasks");
    await page.getByRole("button", { name: "Tasks", exact: true }).click();
    await page.waitForURL("**/tasks");

    if (viewport.name === "desktop") {
      await page.getByRole("button", { name: "Task", exact: true }).click();
      const taskDialog = page.getByRole("dialog", { name: "Create task" });
      await taskDialog.getByLabel(/Title/).fill(taskName);
      await taskDialog.getByLabel("Estimate").fill("30");
      await taskDialog.getByRole("button", { name: "Create task", exact: true }).click();
      await page.getByText("Task created").waitFor();
      await page.getByText(taskName).first().waitFor();
      await page.getByLabel(`Select ${taskName}`).check();
      await page.getByRole("button", { name: "Reschedule" }).click();
      const rescheduleDialog = page.getByRole("dialog", { name: "Bulk reschedule" });
      await rescheduleDialog.getByLabel(/Starts/).fill("2026-07-16T09:00");
      await rescheduleDialog.getByLabel(/Ends/).fill("2026-07-16T10:00");
      await rescheduleDialog.getByRole("button", { name: "Reschedule", exact: true }).click();
      await page.getByText("Tasks rescheduled").waitFor();

      await page.goto(`${baseUrl}/notes`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "New note" }).click();
      const quickDialog = page.getByRole("dialog", { name: "Quick create" });
      await quickDialog.getByLabel(/Title/).fill(noteName);
      await quickDialog.getByLabel("Markdown").fill("# Local browser verification");
      await quickDialog.getByRole("button", { name: "Create note" }).click();
      await page.getByText("Note created").waitFor();
      await page.getByText(noteName).waitFor();

      await page.goto(`${baseUrl}/finance`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Account", exact: true }).click();
      const accountDialog = page.getByRole("dialog", { name: "Create account" });
      await accountDialog.getByLabel(/Name/).fill(accountName);
      await accountDialog.getByRole("button", { name: "Create account", exact: true }).click();
      await page.getByText("Account created").waitFor();
      await page.getByText(accountName).first().waitFor();

      await page.goto(`${baseUrl}/calendar`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Month" }).waitFor();
      await page.getByRole("button", { name: "Agenda" }).click();
      requireState(await page.getByText(/Accessible event list/).count() === 1, "Calendar text alternative is missing");

      await page.goto(`${baseUrl}/scenarios`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Prepare signature demo" }).click();
      await page.getByText("Signature demo prepared locally").waitFor({ timeout: 30_000 });
      await page.getByText("Physical vs remote conference").waitFor();
      requireState(await page.getByText("Berlin · physical attendance").count() >= 1, "Physical conference option is missing");
      requireState(await page.getByText("Berlin · remote attendance").count() >= 1, "Remote conference option is missing");
      requireState(await page.getByText("Cash flow", { exact: true }).count() >= 2, "Scenario financial comparison is missing");
      await page.screenshot({ fullPage: true, path: path.join(outputDirectory, "scenario-comparison-desktop.png") });

      await page.goto(`${baseUrl}/commitments`, { waitUntil: "networkidle" });
      for (const title of ["OpenAI Build Week project", "Berlin tech conference decision", "Laptop purchase"]) {
        await page.getByRole("heading", { name: title }).waitFor();
      }
      const berlinCard = page.getByRole("heading", { name: "Berlin tech conference decision" }).locator("xpath=ancestor::div[contains(@class,'group')]");
      await berlinCard.getByRole("link", { name: "Review impact" }).click();
      await page.getByRole("tab", { name: "graph", exact: true }).click();
      await page.getByLabel(/Relationship graph for Berlin tech conference decision/).waitFor();
      await page.screenshot({ fullPage: true, path: path.join(outputDirectory, "commitment-graph-desktop.png") });
      await page.getByRole("tab", { name: "time", exact: true }).click();
      await page.getByRole("button", { name: "Calculate preview" }).waitFor();

      await page.goto(`${baseUrl}/timeline`, { waitUntil: "networkidle" });
      await page.getByLabel("Commitment").selectOption({ label: "Berlin tech conference decision" });
      await page.waitForURL("**/timeline?*commitment=*");
      await page.getByRole("heading", { name: "Timeline" }).waitFor();
      requireState(await page.getByLabel("Commitment").inputValue() !== "", "Timeline commitment filter did not remain usable");

      for (const signatureRoute of ["/commitments", "/capacity", "/scenarios", "/timeline", "/imports", "/automation"]) {
        await page.goto(`${baseUrl}${signatureRoute}`, { waitUntil: "networkidle" });
        const unlabeled = await page.evaluate(() => Array.from(document.querySelectorAll("input, select, textarea")).filter((control) => {
          const id = control.getAttribute("id");
          return !control.getAttribute("aria-label") && !control.getAttribute("aria-labelledby") && !(id && document.querySelector(`label[for=\"${CSS.escape(id)}\"]`)) && !control.closest("label");
        }).length);
        requireState(unlabeled === 0, `${signatureRoute} has ${unlabeled} unlabeled form controls`);
      }
      report.push("desktop signature commitment/scenario/timeline/a11y: ok");

      await page.goto(baseUrl, { waitUntil: "networkidle" });
      await page.keyboard.press("Control+K");
      await page.getByLabel("Search and navigate").fill(taskName);
      await page.getByRole("button", { name: taskName }).waitFor();
      await page.keyboard.press("Escape");
      report.push("desktop mutations/search/calendar: ok");

      await page.goto(baseUrl, { waitUntil: "networkidle" });
      await page.evaluate(async () => {
        const registration = await navigator.serviceWorker.ready;
        if (!registration.active) throw new Error("Service worker did not activate");
        if (!navigator.serviceWorker.controller) {
          await new Promise((resolve) => navigator.serviceWorker.addEventListener("controllerchange", resolve, { once: true }));
        }
      });
      await page.reload({ waitUntil: "networkidle" });
      expectOfflineNetworkErrors = true;
      await context.setOffline(true);
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.locator("main").waitFor();
      await page.getByText(/Local connection is offline/).waitFor();
      await context.setOffline(false);
      expectOfflineNetworkErrors = false;
      report.push("desktop service-worker offline shell: ok");
    }

    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.screenshot({ fullPage: true, path: path.join(outputDirectory, `${viewport.name}.png`) });
    requireState(runtimeErrors.length === 0, `${viewport.name} runtime errors: ${runtimeErrors.join(" | ")}`);
    requireState(externalRequests.length === 0, `${viewport.name} external requests: ${externalRequests.join(", ")}`);
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(report.join("\n"));
console.log(`Screenshots: ${outputDirectory}`);
